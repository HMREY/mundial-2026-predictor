#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Índice de Momentum Táctico — IMT (v24).

## Formalización (spec v24 §3.2)

Para cada equipo i antes del partido t:

    IMT_i(t) = α·M(t) + β·ΔxG(t) + γ·F(t) + δ·P(t)

  * M(t)   — momentum de resultados: media ponderada exponencial (λ=0.7) de
             los últimos 8 partidos con V=1, E=0.5, D=0. Sin historia → 0.5.
  * ΔxG(t) — tendencia de rendimiento: xG medio de los últimos 3 partidos
             menos el xG medio de los 5 anteriores. Con <6 partidos → 0.
  * F(t)   — factor de fatiga ∈ [0,1] (1 = fresco). Los minutos individuales
             de los 3 jugadores clave NO existen gratis a escala histórica
             (misma limitación documentada del MAT v23), así que se usa el
             proxy validable: congestión de calendario del EQUIPO,
             F = 1 − min(partidos en los 14 días previos / 4, 1).
  * P(t)   — impacto psicológico del último resultado. La spec lo define
             binario; aquí se implementa CON SIGNO (la dirección importa y
             el modelo no puede recuperarla de un binario):
             +1 si viene de ganar por 4+, −1 si viene de perder por 4+, 0 resto.
             La "remontada de 2+ goles en los últimos 10 minutos" exige
             minuto a minuto que las fuentes de clubes no publican → fuera.

## Decisión de diseño: componentes en vez de índice fijo

Los coeficientes α,β,γ,δ NO se fijan a mano: las CUATRO componentes entran
como features separadas (diferencia local − visitante) y el ensemble aprende
la combinación — que generaliza estrictamente al índice lineal (si la
combinación lineal fuese lo óptimo, el modelo la encuentra; si hay
interacciones no lineales, también). `optimizar_coeficientes()` ajusta el
índice lineal contra la diferencia de goles SOLO con datos de entrenamiento,
para reportar α,β,γ,δ interpretables y su correlación (spec §3.2), y el A/B
del walk-forward compara además la variante de índice compuesto ('imt_c')
contra la de componentes ('imt') — la regla de oro decide (§3.4).

Sin fuga: pase cronológico estricto — las features del partido t solo ven
partidos ANTERIORES; el estado final por equipo se persiste para reproducir
el cálculo en inferencia (mismo patrón que features_extra_liga v17).
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

LAMBDA_DECAY = 0.7      # decaimiento exponencial del momentum (spec §3.2)
N_MOMENTUM = 8          # partidos que alimentan M(t)
VENTANA_FATIGA_DIAS = 14
PARTIDOS_FATIGA_MAX = 4.0
UMBRAL_EXTREMO = 4      # goles de margen que activan P(t)

COLS_IMT = ['IMT_M_DIFF', 'IMT_DXG_DIFF', 'IMT_FAT_DIFF', 'IMT_PSI_DIFF']
COLS_IMT_C = ['IMT_DIFF']           # variante índice compuesto (A/B §3.4)

_PESOS_M = LAMBDA_DECAY ** np.arange(N_MOMENTUM)   # reciente primero


def _momentum(resultados: List[float]) -> float:
    """M(t): media exponencial de los últimos 8 resultados (reciente primero)."""
    if not resultados:
        return 0.5
    r = np.array(resultados[-N_MOMENTUM:][::-1], dtype=float)
    w = _PESOS_M[:len(r)]
    return float(np.dot(r, w) / w.sum())


def _delta_xg(xgs: List[float]) -> float:
    """ΔxG(t): media de los últimos 3 menos media de los 5 anteriores."""
    if len(xgs) < 6:
        return 0.0
    ult3 = np.mean(xgs[-3:])
    prev = np.mean(xgs[-8:-3])
    return float(ult3 - prev)


def _fatiga(fechas: List[pd.Timestamp], hoy: pd.Timestamp) -> float:
    """F(t) ∈ [0,1]: 1 = plantilla fresca (proxy de congestión de calendario)."""
    inicio = hoy - pd.Timedelta(days=VENTANA_FATIGA_DIAS)
    n = sum(1 for f in fechas if inicio <= f < hoy)
    return 1.0 - min(n / PARTIDOS_FATIGA_MAX, 1.0)


def _psicologico(ultimo_margen: Optional[float]) -> float:
    """P(t) con signo: subidón (+1) o bajón (−1) tras resultado extremo."""
    if ultimo_margen is None:
        return 0.0
    if ultimo_margen >= UMBRAL_EXTREMO:
        return 1.0
    if ultimo_margen <= -UMBRAL_EXTREMO:
        return -1.0
    return 0.0


def _componentes(st: Dict, fecha: pd.Timestamp) -> Tuple[float, float, float, float]:
    return (_momentum(st['resultados']), _delta_xg(st['xgs']),
            _fatiga(st['fechas'], fecha), _psicologico(st['ultimo_margen']))


def _fila_diff(ch: Tuple, ca: Tuple) -> Dict[str, float]:
    """Diferencias local − visitante, normalizadas a escalas ~[-1, 1]."""
    return {
        'IMT_M_DIFF': ch[0] - ca[0],
        'IMT_DXG_DIFF': float(np.clip((ch[1] - ca[1]) / 3.0, -1, 1)),
        'IMT_FAT_DIFF': ch[2] - ca[2],
        'IMT_PSI_DIFF': (ch[3] - ca[3]) / 2.0,
    }


def features_imt(df: pd.DataFrame):
    """Componentes del IMT por MATCH_ID en un pase cronológico SIN fuga,
    más el estado final por equipo para reproducirlas en inferencia.

    Requiere columnas: date, home_team, away_team, home_goals, away_goals,
    home_xg, away_xg (el relleno determinista del proyecto garantiza xg)."""
    estado: Dict[str, Dict] = {}

    def _st(eq):
        return estado.setdefault(eq, {'resultados': [], 'xgs': [], 'fechas': [],
                                      'ultimo_margen': None})

    filas = []
    for f in df.itertuples(index=False):
        h, a, fecha = f.home_team, f.away_team, f.date
        ch = _componentes(_st(h), fecha)
        ca = _componentes(_st(a), fecha)
        filas.append({'MATCH_ID': f.MATCH_ID, **_fila_diff(ch, ca)})

        # actualizar DESPUÉS de emitir las features (sin fuga)
        gh, ga = float(f.home_goals), float(f.away_goals)
        xh = float(getattr(f, 'home_xg', np.nan))
        xa = float(getattr(f, 'away_xg', np.nan))
        for eq, propios, rival, xg in ((h, gh, ga, xh), (a, ga, gh, xa)):
            st = _st(eq)
            st['resultados'].append(1.0 if propios > rival else
                                    (0.5 if propios == rival else 0.0))
            st['xgs'].append(xg if np.isfinite(xg) else propios)
            st['fechas'].append(fecha)
            st['ultimo_margen'] = propios - rival
            # memoria acotada: lo que las componentes pueden llegar a mirar
            st['resultados'] = st['resultados'][-N_MOMENTUM:]
            st['xgs'] = st['xgs'][-N_MOMENTUM:]
            st['fechas'] = [d for d in st['fechas']
                            if d >= fecha - pd.Timedelta(days=45)]

    # estado final serializable (para team_stats_{liga}.json['estado_imt'])
    estado_out = {}
    for eq, st in estado.items():
        estado_out[eq] = {
            'resultados': st['resultados'],
            'xgs': [round(x, 3) for x in st['xgs']],
            'fechas': [d.strftime('%Y-%m-%d') for d in st['fechas']],
            'ultimo_margen': st['ultimo_margen'],
        }
    return pd.DataFrame(filas).set_index('MATCH_ID'), estado_out


def vector_imt(estado_imt: Dict, home: str, away: str,
               fecha: Optional[pd.Timestamp] = None) -> Dict[str, float]:
    """Reproduce en inferencia las features IMT desde el estado guardado."""
    fecha = fecha or pd.Timestamp.today().normalize()

    def _st(eq):
        e = (estado_imt or {}).get(eq)
        if not e:
            return {'resultados': [], 'xgs': [], 'fechas': [], 'ultimo_margen': None}
        return {'resultados': list(e.get('resultados') or []),
                'xgs': list(e.get('xgs') or []),
                'fechas': [pd.Timestamp(d) for d in e.get('fechas') or []],
                'ultimo_margen': e.get('ultimo_margen')}

    ch = _componentes(_st(home), fecha)
    ca = _componentes(_st(away), fecha)
    return _fila_diff(ch, ca)


def optimizar_coeficientes(df: pd.DataFrame, imt_df: pd.DataFrame,
                           hasta_fecha=None) -> Dict:
    """α,β,γ,δ del índice lineal (spec §3.2): mínimos cuadrados de la
    diferencia de goles sobre las 4 componentes, SOLO con partidos anteriores
    a `hasta_fecha` (sin fuga). Devuelve coeficientes y correlación de
    IMT_local − IMT_visitante con la diferencia de goles real."""
    d = df.set_index('MATCH_ID').join(imt_df, how='inner')
    if hasta_fecha is not None:
        d = d[d['date'] < pd.Timestamp(hasta_fecha)]
    X = d[COLS_IMT].values
    yy = (d['home_goals'] - d['away_goals']).values
    if len(d) < 100:
        return {'coef': dict(zip(('alpha', 'beta', 'gamma', 'delta'), [0.0] * 4)),
                'correlacion': 0.0, 'n': int(len(d))}
    coef, *_ = np.linalg.lstsq(np.column_stack([X, np.ones(len(X))]), yy, rcond=None)
    imt = X @ coef[:4]
    corr = float(np.corrcoef(imt, yy)[0, 1]) if np.std(imt) > 0 else 0.0
    return {'coef': {k: round(float(c), 4) for k, c in
                     zip(('alpha', 'beta', 'gamma', 'delta'), coef[:4])},
            'intercepto': round(float(coef[4]), 4),
            'correlacion': round(corr, 4), 'n': int(len(d))}


def valor_compuesto(valores: Dict[str, float], coef: Dict[str, float]) -> float:
    """IMT_DIFF de un solo partido a partir de sus componentes (inferencia)."""
    c = np.array([coef.get('alpha', 0), coef.get('beta', 0),
                  coef.get('gamma', 0), coef.get('delta', 0)])
    v = np.array([valores[k] for k in COLS_IMT])
    return float(v @ c / max(float(np.abs(c).sum()), 1e-6))


def indice_compuesto(imt_df: pd.DataFrame, coef: Dict[str, float]) -> pd.Series:
    """IMT_DIFF = combinación lineal de las componentes con α,β,γ,δ dados
    (variante 'imt_c' del A/B; los coeficientes vienen de train-only)."""
    c = np.array([coef.get('alpha', 0), coef.get('beta', 0),
                  coef.get('gamma', 0), coef.get('delta', 0)])
    escala = max(float(np.abs(c).sum()), 1e-6)
    return pd.Series(imt_df[COLS_IMT].values @ c / escala,
                     index=imt_df.index, name='IMT_DIFF')
