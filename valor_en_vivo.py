#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valor en Vivo (v34 §6) — evolución del EV SIN consumir API.

RESTRICCIÓN ESTRICTA del spec: esta vista **nunca** hace peticiones HTTP.
Se alimenta solo de:
  * los snapshots ya guardados en `odds_historico.db` (los que el acelerador
    RLM captura para el backtest),
  * las probabilidades del modelo (cálculo local),
  * las cuotas justas cuando no hay snapshot.

Para cada partido con ≥2 snapshots calcula el EV en el más reciente y la
TENDENCIA (si la cuota sube, el mercado se aleja de nuestro pick; si baja,
se acerca — el clásico "line movement").
"""

import logging
import os
import sqlite3
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DB = 'odds_historico.db'


def _snapshots(horas: int = 72) -> pd.DataFrame:
    if not os.path.exists(DB):
        return pd.DataFrame()
    con = sqlite3.connect(DB)
    desde = (pd.Timestamp.utcnow() - pd.Timedelta(hours=horas)) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')
    df = pd.read_sql_query(
        "SELECT match_id, liga, capturado_utc, mercado, seleccion, cuota "
        "FROM snapshots WHERE mercado='h2h' AND capturado_utc>=? "
        "ORDER BY capturado_utc", con, params=[desde])
    con.close()
    return df


def valor_en_vivo(max_partidos: int = 25) -> Dict:
    """Tabla de EV actual y tendencia por partido (sin tocar la red)."""
    df = _snapshots()
    if df.empty:
        return {'filas': [], 'aviso': 'Sin snapshots guardados todavía: la '
                                      'vista se llena conforme el pipeline '
                                      'captura cuotas (sin gastar API extra).'}
    from league_engine import ClubEngine
    import alpha_finder
    mapa = alpha_finder._mapa_equipo_liga()
    motores: Dict[str, object] = {}
    filas = []
    for mid, g in df.groupby('match_id'):
        if len(filas) >= max_partidos:
            break
        partes = mid.split('_')
        if len(partes) != 3:
            continue
        home, away = partes[1].replace('-', ' '), partes[2].replace('-', ' ')
        liga = mapa.get(home) or mapa.get(away) or \
            alpha_finder._liga_fuzzy(home, away, mapa)
        if not liga:
            continue
        if liga not in motores:
            motores[liga] = ClubEngine(liga)
        eng = motores[liga]
        if not getattr(eng, 'listo', False) or home not in eng.stats \
                or away not in eng.stats:
            continue
        pred = eng.predecir(home, away)
        if 'error' in pred:
            continue
        probs = pred['prediction']['probabilities']
        capturas = sorted(g['capturado_utc'].unique())
        ult, prim = capturas[-1], capturas[0]
        def _cuotas(ts):
            sub = g[g['capturado_utc'] == ts]
            return {r['seleccion']: float(r['cuota']) for _, r in sub.iterrows()}
        c_ult, c_prim = _cuotas(ult), _cuotas(prim)
        for sel, prob in (('home', probs['home']), ('draw', probs['draw']),
                          ('away', probs['away'])):
            cuota = c_ult.get(sel)
            if not cuota:
                continue
            ev = cuota * prob - 1
            if ev <= 0:
                continue
            cuota0 = c_prim.get(sel, cuota)
            delta = cuota - cuota0
            tendencia = ('📈 la cuota sube (más valor)' if delta > 0.01 else
                         '📉 la cuota baja (el mercado se ajusta)'
                         if delta < -0.01 else '➖ estable')
            filas.append({
                'partido': f'{home} vs {away}', 'liga': liga,
                'mercado': {'home': f'Gana {home}', 'draw': 'Empate',
                            'away': f'Gana {away}'}[sel],
                'cuota_actual': round(cuota, 2),
                'cuota_inicial': round(cuota0, 2),
                'ev_pct': round(ev * 100, 1),
                'tendencia': tendencia,
                'snapshots': len(capturas),
                'ultima_captura': ult})
    filas.sort(key=lambda f: -f['ev_pct'])
    return {'filas': filas, 'n_partidos': df['match_id'].nunique(),
            'aviso': None if filas else
            'Sin oportunidades con EV positivo en los snapshots guardados.'}


if __name__ == '__main__':
    import json
    import warnings
    warnings.filterwarnings('ignore')
    logging.basicConfig(level=logging.INFO)
    r = valor_en_vivo()
    print(f"partidos con snapshots: {r.get('n_partidos')} · filas: {len(r['filas'])}")
    for f in r['filas'][:8]:
        print(f"  {f['liga']:<10} {f['partido'][:34]:<34} {f['mercado'][:22]:<22} "
              f"@ {f['cuota_actual']} EV {f['ev_pct']:+.1f}% {f['tendencia']}")
