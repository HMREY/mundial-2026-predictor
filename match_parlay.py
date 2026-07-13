#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Asistente de Parlay POR PARTIDO (v15) — agnóstico de competición.

Extrae todas las selecciones apostables de la plantilla del partido (Mundial:
`motor.plantilla`; clubes: `motor.plantilla_club`), filtra por el umbral del
perfil de riesgo, descarta combinaciones lógicamente incompatibles o
redundantes, aplica un haircut de correlación (0.95 por pareja correlacionada)
y devuelve el parlay del tamaño pedido (4-8) que maximiza el EV (con cuotas
reales) o la probabilidad conjunta (con cuotas justas).

El parlay multi-partido del fixture (parlay_builder.py) queda intacto.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

PERFILES = {'conservador': 0.65, 'medio': 0.55, 'agresivo': 0.50}
HAIRCUT_CORRELACION = 0.95
CUOTA_MAXIMA_COMBINADA = 1000.0

# ---------------------------------------------------------------------------
# Semántica de los campos de la plantilla
# ---------------------------------------------------------------------------
# grupo   -> solo UNA selección por grupo (opciones mutuamente excluyentes)
# familia -> selecciones de familias distintas de la MISMA macro-familia se
#            consideran correlacionadas (haircut); p. ej. 1X2 con hándicap.
# Los ids no listados aquí se clasifican por heurística de prefijo.
_RESULTADO = 'resultado'      # macro-familia: todo lo que depende del ganador
_GOLES = 'goles'              # macro-familia: volumen de goles
_CORNERS = 'corners'
_TARJETAS = 'tarjetas'

CAMPOS = {
    # --- comunes (Mundial y clubes) ---
    'home_win_prob': ('1x2', _RESULTADO), 'draw_prob': ('1x2', _RESULTADO),
    'away_win_prob': ('1x2', _RESULTADO),
    # doble oportunidad (Mundial usa *_or_*; clubes usa dc_*)
    'home_or_draw_prob': ('dc', _RESULTADO), 'home_or_away_prob': ('dc', _RESULTADO),
    'draw_or_away_prob': ('dc', _RESULTADO),
    'dc_1x': ('dc', _RESULTADO), 'dc_12': ('dc', _RESULTADO), 'dc_x2': ('dc', _RESULTADO),
    # total de goles
    'over25_prob': ('ou_goles_25', _GOLES), 'under25_prob': ('ou_goles_25', _GOLES),
    'over05': ('ou_goles_05', _GOLES), 'over15': ('ou_goles_15', _GOLES),
    'over25': ('ou_goles_25', _GOLES), 'over35': ('ou_goles_35', _GOLES),
    'over45': ('ou_goles_45', _GOLES), 'over55': ('ou_goles_55', _GOLES),
    'over15_goles': ('ou_goles_15', _GOLES), 'over35_goles': ('ou_goles_35', _GOLES),
    # btts / momentos de gol / paridad
    'btts_yes_prob': ('btts', _GOLES), 'btts_no_prob': ('btts', _GOLES),
    'btts_si': ('btts', _GOLES), 'btts_no': ('btts', _GOLES),
    'sin_goles': ('btts', _GOLES),
    'primer_gol_home': ('primer_gol', _GOLES), 'primer_gol_away': ('primer_gol', _GOLES),
    'ultimo_gol_home': ('ultimo_gol', _GOLES),
    'total_par': ('paridad', _GOLES), 'total_impar': ('paridad', _GOLES),
    # córners
    'over65_corners': ('ou_ck_65', _CORNERS), 'over75_corners': ('ou_ck_75', _CORNERS),
    'over85_corners': ('ou_ck_85', _CORNERS), 'over95_corners': ('ou_ck_95', _CORNERS),
    'ck_o85': ('ou_ck_85', _CORNERS), 'ck_o95': ('ou_ck_95', _CORNERS),
    'ck_o105': ('ou_ck_105', _CORNERS),
    'corners_par_prob': ('ck_paridad', _CORNERS),
    'corners_1h_par_prob': ('ck_paridad_1h', _CORNERS),
    'first_corner_home_prob': ('primer_ck', _CORNERS),
    'last_corner_home_prob': ('ultimo_ck', _CORNERS),
    'last_corner_1h_home_prob': ('ultimo_ck_1h', _CORNERS),
    # tarjetas
    'over35_tarjetas': ('ou_cards_35', _TARJETAS), 'over55_tarjetas': ('ou_cards_55', _TARJETAS),
    'cards_over45_prob': ('ou_cards_45', _TARJETAS),
    'cards_o35': ('ou_cards_35', _TARJETAS), 'cards_o45': ('ou_cards_45', _TARJETAS),
    'penalty_prob': ('penalty', _TARJETAS),
}

_PREFIJOS = [
    # (prefijo, grupo_base, familia). El grupo usa el id completo cuando el
    # prefijo agrupa opciones NO excluyentes entre sí (p. ej. líneas o/u).
    ('ah_', 'ah', _RESULTADO), ('h1x2_', 'h1x2', _RESULTADO),
    ('home_plus', 'ah', _RESULTADO), ('home_minus', 'ah', _RESULTADO),
    ('away_plus', 'ah', _RESULTADO), ('away_minus', 'ah', _RESULTADO),
    ('score_', 'score', _RESULTADO), ('mv_', 'margen', _RESULTADO),
    ('htft_', 'htft', _RESULTADO),
    ('th_o', 'th', _GOLES), ('ta_o', 'ta', _GOLES),
    ('multi_', 'multi', _GOLES),
    ('player_', 'goleador', _GOLES), ('shooter_', 'rematador', _GOLES),
]

# Parejas EQUIVALENTES entre grupos (misma apuesta con otro nombre): nunca
# juntas; se queda la de mayor probabilidad. AH ±0.5 == 1X2/DC.
EQUIVALENCIAS = [
    ({'home_minus05_prob', 'ah_home_1'}, {'home_win_prob'}),
    ({'away_minus05_prob'}, {'away_win_prob'}),
    ({'home_plus05_prob', 'ah_home_mas05'}, {'home_or_draw_prob', 'dc_1x'}),
    ({'away_plus05_prob', 'ah_away_mas05'}, {'draw_or_away_prob', 'dc_x2'}),
]

# 1X2 vs doble oportunidad CONTRADICTORIAS (estrictamente incompatibles)
CONTRADICCIONES = [
    ({'home_win_prob'}, {'draw_or_away_prob', 'dc_x2'}),
    ({'draw_prob'}, {'home_or_away_prob', 'dc_12'}),
    ({'away_win_prob'}, {'home_or_draw_prob', 'dc_1x'}),
    ({'btts_si', 'btts_yes_prob'}, {'sin_goles', 'under25_prob'}),  # btts≥2 goles
    ({'btts_si', 'btts_yes_prob'}, {'over05', 'over15', 'over15_goles'}),  # redundante
]


@dataclass
class Seleccion:
    id: str
    mercado: str          # título de la sección
    apuesta: str          # etiqueta legible del campo
    prob: float           # 0-1
    cuota: float
    cuota_fuente: str     # 'justa' | 'real'
    grupo: str
    familia: str
    ev: float = 0.0


def _clasificar(id_: str):
    if id_ in CAMPOS:
        return CAMPOS[id_]
    for prefijo, grupo, familia in _PREFIJOS:
        if id_.startswith(prefijo):
            # líneas o/u y marcadores: cada id es su propio grupo salvo los
            # explícitamente excluyentes (score_, mv_, htft_, h1x2_ = 1 por grupo)
            if grupo in ('score', 'margen', 'htft', 'h1x2', 'ah', 'multi'):
                return grupo, familia
            return id_, familia
    return None, None


def _cuotas_reales_del_partido(pl: Dict) -> Dict[str, float]:
    """Cuotas reales de odds_actuales.json para ESTE partido, por campo.

    El MATCH_ID lleva fecha, que la plantilla no fija: se busca por sufijo
    de nombres de equipo. Cubre 1X2 y over/under 2.5 (lo que publican las
    fuentes gratuitas).
    """
    if not os.path.exists('odds_actuales.json'):
        return {}
    try:
        with open('odds_actuales.json', encoding='utf-8') as f:
            cuotas = json.load(f).get('cuotas', {})
    except Exception:
        return {}
    cod = pl.get('codigos', {})
    h = str(cod.get('home', '')).replace(' ', '-')
    a = str(cod.get('away', '')).replace(' ', '-')
    if not h or not a:
        return {}
    sufijo = f"_{h}_{a}"
    for mid, o in cuotas.items():
        if mid.endswith(sufijo):
            reales = {}
            if o.get('odd_home'):
                reales['home_win_prob'] = float(o['odd_home'])
                reales['draw_prob'] = float(o['odd_draw'])
                reales['away_win_prob'] = float(o['odd_away'])
            if o.get('odd_over25'):
                reales['over25_prob'] = reales['over25'] = float(o['odd_over25'])
            if o.get('odd_under25'):
                reales['under25_prob'] = float(o['odd_under25'])
            return reales
    return {}


def obtener_selecciones(pl: Dict) -> List[Seleccion]:
    """Convierte la plantilla (Mundial o club) en selecciones apostables."""
    reales = _cuotas_reales_del_partido(pl)
    out: List[Seleccion] = []
    for seccion in pl.get('secciones', []):
        for c in seccion.get('campos', []):
            if c.get('tipo') != 'pct':
                continue
            grupo, familia = _clasificar(c['id'])
            if grupo is None:
                continue
            try:
                prob = float(c['valor']) / 100.0
            except (TypeError, ValueError):
                continue
            if not (0.0 < prob < 1.0):
                continue
            if c['id'] in reales:
                cuota, fuente = reales[c['id']], 'real'
            else:
                cuota, fuente = round(1.0 / prob, 2), 'justa'
            out.append(Seleccion(
                id=c['id'], mercado=seccion.get('titulo', ''),
                apuesta=c.get('etiqueta', c['id']), prob=prob,
                cuota=cuota, cuota_fuente=fuente,
                grupo=grupo, familia=familia,
                ev=round(cuota * prob - 1.0, 3),
            ))
    return out


def _ids_en(par_conjuntos, id_a: str, id_b: str) -> bool:
    for lado_a, lado_b in par_conjuntos:
        if (id_a in lado_a and id_b in lado_b) or (id_b in lado_a and id_a in lado_b):
            return True
    return False


def _compatibles(a: Seleccion, b: Seleccion) -> bool:
    if a.grupo == b.grupo:
        return False                       # opciones excluyentes del mismo grupo
    if _ids_en(CONTRADICCIONES, a.id, b.id):
        return False
    if _ids_en(EQUIVALENCIAS, a.id, b.id):
        return False                       # misma apuesta con otro nombre
    return True


def _correlacionadas(a: Seleccion, b: Seleccion) -> bool:
    """Correlación no excluyente -> haircut. Misma macro-familia."""
    return a.familia == b.familia


def _riesgo_partido(pl: Dict) -> str:
    try:
        with open('risk_flags.json', encoding='utf-8') as f:
            flags = json.load(f)
        cod = pl.get('codigos', {})
        h, a = cod.get('home', ''), cod.get('away', '')
        return flags.get(f"{h}|{a}") or flags.get(f"{a}|{h}") or 'bajo'
    except Exception:
        return 'bajo'


def construir_parlay_partido(motor, home: str, away: str,
                             num_selecciones: int = 6,
                             perfil: str = 'medio',
                             usar_cuotas_reales: bool = True,
                             excluir_alto_riesgo: bool = True) -> Dict:
    """Parlay óptimo dentro de UN partido. Ver docstring del módulo."""
    num_selecciones = max(4, min(8, int(num_selecciones)))
    umbral = PERFILES.get(perfil, PERFILES['medio'])

    # plantilla según el tipo de motor (clubes primero: ClubEngine no tiene .plantilla)
    if hasattr(motor, 'plantilla_club'):
        pl = motor.plantilla_club(home, away)
    else:
        pl = motor.plantilla(home, away)
    if 'error' in pl:
        return {'error': pl['error']}

    riesgo = _riesgo_partido(pl)
    if riesgo == 'alto' and excluir_alto_riesgo:
        return {'error': '🔴 Este partido tiene riesgo de mercado ALTO '
                         '(divergencia/liquidez en mercados de predicción). '
                         'Desactiva la exclusión de riesgo si aun así quieres el parlay.'}

    todas = obtener_selecciones(pl)
    if not usar_cuotas_reales:
        for s in todas:
            if s.cuota_fuente == 'real':
                s.cuota, s.cuota_fuente = round(1.0 / s.prob, 2), 'justa'
                s.ev = 0.0

    candidatas = [s for s in todas if s.prob >= umbral]
    aviso_umbral = None
    umbral_usado = umbral
    # relajar el umbral solo lo necesario para completar el parlay
    for umbral_relajado in (0.50, 0.45, 0.40):
        if len({s.grupo for s in candidatas}) >= num_selecciones or umbral <= umbral_relajado:
            break
        candidatas = [s for s in todas if s.prob >= umbral_relajado]
        umbral_usado = umbral_relajado
        aviso_umbral = (f"⚠️ No había suficientes mercados con prob ≥ {umbral*100:.0f} %: "
                        f"el umbral se relajó a {umbral_relajado*100:.0f} % para completar el parlay.")

    if len(candidatas) < 2:
        return {'error': 'Este partido no tiene suficientes mercados con la '
                         'probabilidad mínima del perfil elegido.'}

    hay_reales = any(s.cuota_fuente == 'real' for s in candidatas)
    # greedy: mayor EV (si hay cuotas reales) o mayor probabilidad, añadiendo
    # solo selecciones compatibles con las ya elegidas
    clave = (lambda s: (s.ev, s.prob)) if hay_reales else (lambda s: s.prob)
    orden = sorted(candidatas, key=clave, reverse=True)
    elegidas: List[Seleccion] = []
    for s in orden:
        if len(elegidas) >= num_selecciones:
            break
        if all(_compatibles(s, e) for e in elegidas):
            elegidas.append(s)

    aviso_cantidad = None
    if len(elegidas) < num_selecciones:
        aviso_cantidad = (f"⚠️ Solo hay {len(elegidas)} selecciones compatibles "
                          f"(pediste {num_selecciones}).")
    if len(elegidas) < 2:
        return {'error': 'No hay suficientes selecciones compatibles en este partido.'}

    prob_conjunta = 1.0
    cuota_combinada = 1.0
    n_haircuts = 0
    for i, s in enumerate(elegidas):
        prob_conjunta *= s.prob
        cuota_combinada *= s.cuota
        for e in elegidas[:i]:
            if _correlacionadas(s, e):
                n_haircuts += 1
    prob_conjunta *= HAIRCUT_CORRELACION ** n_haircuts
    cuota_combinada = min(cuota_combinada, CUOTA_MAXIMA_COMBINADA)

    ev_parlay = round(cuota_combinada * prob_conjunta - 1.0, 3) if hay_reales else 0.0

    return {
        'partido': pl.get('partido', f'{home} vs {away}'),
        'perfil': perfil, 'umbral_usado': umbral_usado,
        'riesgo_partido': riesgo,
        'selecciones': [{
            'mercado': s.mercado, 'apuesta': s.apuesta,
            'prob': round(s.prob, 3), 'cuota': s.cuota,
            'cuota_fuente': s.cuota_fuente, 'ev': s.ev,
        } for s in elegidas],
        'n_selecciones': len(elegidas),
        'cuota_combinada': round(cuota_combinada, 2),
        'prob_conjunta': round(prob_conjunta, 4),
        'n_parejas_correlacionadas': n_haircuts,
        'ev_parlay': ev_parlay,
        'cuotas_reales': hay_reales,
        'avisos': [a for a in (aviso_umbral, aviso_cantidad) if a],
        'nota': ('EV calculado con cuotas reales de mercado.' if hay_reales else
                 '⚠️ EV teórico (cuotas justas del modelo) — no accionable; '
                 'compara contra las cuotas de tu casa para encontrar valor.'),
    }
