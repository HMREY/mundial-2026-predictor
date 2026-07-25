#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cuotas AUTOMÁTICAS por partido (v64) — sin pegar nada, sin clave, sin scraping.

Fuente: el endpoint `core` de ESPN por evento, el mismo dominio público que ya
usamos para fixtures y rosters. Verificado 2026-07-24 (proveedor DraftKings):

  · 1X2 (moneyline)                     → 1.444 / 4.90 / 6.00
  · Over/Under con su línea             → 2.5: 1.556 / 2.35
  · HÁNDICAP con su línea y cuota       → −1.5: 2.15 / 1.606
  · ~229 PROPS por partido              → First/Last/Anytime Goalscorer,
    To Score 2+/3+, Both Teams To Score, 1st Half Moneyline/Total,
    Team Total Goals, Odd/Even, Assists/Tackles Milestones...

Todo con cuota DECIMAL real. Este módulo las etiqueta con el mismo vocabulario
que la plantilla del modelo y reutiliza el cruce de `cuotas_manual` para
calcular el EV accionable de cada mercado.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# prop de ESPN → etiqueta equivalente en nuestra plantilla (cuando existe)
_PROP_DIRECTO = {
    'Both Teams To Score': 'Ambos equipos marcan: Sí',
    'Total Goals - Odd/Even': 'Total de goles PAR (0 cuenta)',
}


def _nombres_jugadores(clave: str, home: str, away: str) -> Dict[str, str]:
    """id de atleta → nombre, desde el roster ya cacheado por goleadores.py
    (evita una petición por jugador)."""
    nombres: Dict[str, str] = {}
    try:
        import goleadores
        for equipo in (home, away):
            tid = goleadores._buscar_team_id(clave, equipo)
            if not tid:
                continue
            for j in goleadores.plantilla_equipo(clave, tid):
                nombres[str(j['id'])] = j['nombre']
    except Exception as e:
        logger.warning(f"[cuotas_auto] nombres no disponibles: {e}")
    return nombres


def _etiquetas_desde_odds(o: Dict, home: str, away: str) -> List[Dict]:
    """Convierte las cuotas del evento en filas {etiqueta, cuota} con el
    vocabulario de la plantilla, para poder cruzarlas."""
    filas: List[Dict] = []

    def _add(etq, cuota):
        if cuota and cuota > 1.0:
            filas.append({'etiqueta': etq, 'cuota': round(float(cuota), 3)})

    _add(f'Gana {home}', o.get('odd_home'))
    _add('Empate', o.get('odd_draw'))
    _add(f'Gana {away}', o.get('odd_away'))
    linea = o.get('ou_linea')
    if linea:
        _add(f'Más de {linea} goles', o.get('odd_over'))
        _add(f'Menos de {linea} goles', o.get('odd_under'))
    # HÁNDICAP: la línea de ESPN es del LOCAL (negativa = favorito). Nuestra
    # plantilla lo nombra «{equipo} −X» / «{equipo} +X».
    ah = o.get('ah_linea')
    if ah is not None:
        signo_local = '−' if ah < 0 else '+'
        signo_visit = '+' if ah < 0 else '−'
        v = abs(float(ah))
        _add(f'{home} {signo_local}{v}', o.get('odd_ah_home'))
        _add(f'{away} {signo_visit}{v}', o.get('odd_ah_away'))
    return filas


def _etiquetas_desde_props(props: List[Dict], home: str, away: str) -> List[Dict]:
    filas: List[Dict] = []
    for p in props:
        tipo, atleta, cuota = p.get('tipo'), p.get('atleta'), p.get('cuota')
        if not cuota or cuota <= 1.0:
            continue
        if tipo in _PROP_DIRECTO:
            filas.append({'etiqueta': _PROP_DIRECTO[tipo], 'cuota': cuota})
        elif tipo == 'Anytime Goalscorer' and atleta:
            # la plantilla lo nombra «{jugador} marca ({equipo})»; el cruce es
            # difuso, así que basta con el nombre y la palabra clave.
            filas.append({'etiqueta': f'{atleta} marca', 'cuota': cuota})
        elif tipo == 'To Score 2+ Goals' and atleta:
            filas.append({'etiqueta': f'{atleta} marca 2 o más', 'cuota': cuota})
    return filas


def cuotas_reales(clave: str, home: str, away: str, event_id: str,
                  con_props: bool = True) -> List[Dict]:
    """Todas las cuotas reales del partido, etiquetadas y listas para cruzar."""
    import fixtures_espn
    o = fixtures_espn.odds_evento(clave, event_id)
    if not o:
        return []
    filas = _etiquetas_desde_odds(o, home, away)
    if con_props:
        nombres = _nombres_jugadores(clave, home, away)
        props = fixtures_espn.props_evento(clave, event_id, nombres=nombres)
        filas += _etiquetas_desde_props(props, home, away)
    for f in filas:
        f['casa'] = o.get('casa', 'ESPN')
    return filas


def evaluar(clave: str, home: str, away: str, event_id: str, pl: Dict,
            con_props: bool = True) -> List[Dict]:
    """Cuotas reales × probabilidades del modelo → EV accionable por mercado.
    Reutiliza el cruce difuso ya probado de `cuotas_manual`."""
    import cuotas_manual
    filas = cuotas_reales(clave, home, away, event_id, con_props=con_props)
    if not filas:
        return []
    res = cuotas_manual.cruzar_con_plantilla(filas, pl)
    casa = filas[0].get('casa', 'ESPN')
    # dedup: algunos props (p. ej. las dos caras de «Both Teams To Score»)
    # cruzan contra el MISMO mercado del modelo; se conserva el de mejor EV.
    mejor: Dict[str, Dict] = {}
    for r in res:
        r['casa'] = casa
        prev = mejor.get(r['apuesta'])
        if prev is None or r['ev'] > prev['ev']:
            mejor[r['apuesta']] = r
    return sorted(mejor.values(), key=lambda r: -r['ev'])


def buscar_event_id(clave: str, home: str, away: str) -> str:
    """event_id del fixture que corresponde a este par de equipos (mapeo por
    nombre, ya que la plantilla usa los nombres del modelo)."""
    import fixtures_espn
    import name_mapper
    fixtures = fixtures_espn.fixtures_liga(clave)
    if not fixtures:
        return ''
    catalogo = {f"{f['home']}|{f['away']}": f for f in fixtures}
    # coincidencia directa por fuzzy de ambos nombres
    for clave_fx, f in catalogo.items():
        h_fx, a_fx = clave_fx.split('|')
        h_ok = name_mapper.mapear(h_fx, [home], contexto='evid')
        a_ok = name_mapper.mapear(a_fx, [away], contexto='evid')
        if h_ok and a_ok:
            return f.get('event_id') or ''
    return ''
