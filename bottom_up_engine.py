#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARRIL B (v28 §3) — Laboratorio Bottom-Up: PFI por ratings de FotMob.

⚠️ EXPERIMENTAL Y AISLADO: vive en la rama experimento/bottom-up; nada del
pipeline de producción lo importa. Se fusionará solo si el VORP-PFI supera
el walk-forward (§3.3).

PFI (Player Form Index) = EMA(ratings FotMob, α=0.3) de los últimos 10
partidos del jugador. Los ratings por JUGADOR no estaban en el extracto
compacto de fotmob_cache (solo la media de equipo): `acumular_ratings()`
re-visita las páginas de partido cacheadas por id y añade el detalle a
ratings_historicos.csv (incremental, cortesía 1.5 s).

Estado de datos 2026-07-19: ~28 partidos con página disponible (MLS/Liga
MX) — MUY por debajo de la temporada completa que exige el PFI. El VORP-PFI
sobre Champions 2022-25 que pide la spec es IMPOSIBLE hoy: FotMob no expone
ratings históricos de esas temporadas vía __NEXT_DATA__ para backfill
masivo, y nuestra caché nació en v24. Este módulo deja la infraestructura
lista y la validación queda condicionada a la cobertura (protocolo clima
v23 / FotMob v24).
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RATINGS_CSV = 'ratings_historicos.csv'
ALPHA = 0.3
N_PARTIDOS = 10


def _ratings_de_pagina(match_id: str) -> Optional[List[Dict]]:
    """Ratings por jugador desde la página del partido (1 request)."""
    import fotmob_scraper as fs
    data = fs._next_data(f'https://www.fotmob.com/match/{match_id}')
    if not data:
        return None
    pp = data['props']['pageProps']
    gen = pp.get('general') or {}
    lineup = (pp.get('content') or {}).get('lineup') or {}
    filas = []
    for lado, equipo in (('home', 'homeTeam'), ('away', 'awayTeam')):
        eq = lineup.get(equipo) or {}
        nombre_eq = (gen.get(f'{lado}Team') or {}).get('name')
        for grupo in ('starters', 'subs'):
            for j in eq.get(grupo) or []:
                rating = ((j.get('performance') or {}).get('rating')
                          or j.get('rating'))
                try:
                    rating = float(rating)
                except (TypeError, ValueError):
                    continue
                filas.append({'match_id': str(match_id),
                              'fecha': (gen.get('matchTimeUTCDate') or '')[:10],
                              'equipo': nombre_eq,
                              'jugador': j.get('name') or j.get('shortName'),
                              'titular': grupo == 'starters',
                              'rating': rating})
    return filas or None


def acumular_ratings(max_nuevos: int = 30) -> pd.DataFrame:
    """Consolida ratings por jugador de los partidos en fotmob_cache."""
    hechos = set()
    if os.path.exists(RATINGS_CSV):
        hechos = set(pd.read_csv(RATINGS_CSV)['match_id'].astype(str))
    ids = [f[:-5] for f in os.listdir('fotmob_cache')
           if f.endswith('.json')] if os.path.isdir('fotmob_cache') else []
    nuevos, filas = 0, []
    for mid in ids:
        if mid in hechos or nuevos >= max_nuevos:
            continue
        r = _ratings_de_pagina(mid)
        nuevos += 1
        time.sleep(1.5)
        if r:
            filas.extend(r)
    if filas:
        df_new = pd.DataFrame(filas)
        if os.path.exists(RATINGS_CSV):
            df_new = pd.concat([pd.read_csv(RATINGS_CSV), df_new],
                               ignore_index=True)
        df_new.to_csv(RATINGS_CSV, index=False)
        logger.info(f"[pfi] ratings_historicos.csv: {len(df_new)} filas "
                    f"({nuevos} partidos nuevos)")
    return pd.read_csv(RATINGS_CSV) if os.path.exists(RATINGS_CSV) \
        else pd.DataFrame()


def pfi_jugadores() -> pd.DataFrame:
    """PFI por jugador: EMA(α=0.3) de sus últimos 10 ratings."""
    if not os.path.exists(RATINGS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(RATINGS_CSV).sort_values('fecha')
    filas = []
    for (jug, eq), g in df.groupby(['jugador', 'equipo']):
        r = g['rating'].tail(N_PARTIDOS).values
        if len(r) == 0:
            continue
        ema = r[0]
        for x in r[1:]:
            ema = ALPHA * x + (1 - ALPHA) * ema
        filas.append({'jugador': jug, 'equipo': eq, 'pfi': round(float(ema), 3),
                      'n_partidos': len(r)})
    return pd.DataFrame(filas).sort_values('pfi', ascending=False)


def correlacion_pfi_xg() -> Dict:
    """Validación intermedia (§3.1): ¿el PFI es complementario al xG/90?"""
    from difflib import SequenceMatcher
    pfi = pfi_jugadores()
    if pfi.empty or not os.path.exists('jugadores_xg.csv'):
        return {'veredicto': 'sin datos suficientes', 'n': 0}
    xg = pd.read_csv('jugadores_xg.csv')
    pares = []
    for r in pfi.itertuples(index=False):
        mejor, ratio = None, 0.0
        for x in xg.itertuples(index=False):
            s = SequenceMatcher(None, str(r.jugador).lower(),
                                str(x.nombre).lower()).ratio()
            if s > ratio:
                mejor, ratio = x, s
        if ratio >= 0.85:
            pares.append((r.pfi, mejor.xg90_estimado))
    if len(pares) < 15:
        return {'veredicto': f'solo {len(pares)} jugadores cruzables '
                             '(bases distintas: FotMob clubes vs xG '
                             'internacionales) — repetir cuando la cobertura '
                             'crezca', 'n': len(pares)}
    a = np.array(pares)
    corr = float(np.corrcoef(a[:, 0], a[:, 1])[0, 1])
    return {'n': len(pares), 'correlacion_pfi_xg90': round(corr, 3),
            'veredicto': ('complementaria (|r|<0.5): aporta señal nueva'
                          if abs(corr) < 0.5 else 'parcialmente redundante')}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    df = acumular_ratings()
    print(f"ratings: {len(df)} filas · jugadores: "
          f"{df['jugador'].nunique() if not df.empty else 0}")
    top = pfi_jugadores()
    if not top.empty:
        print(top.head(8).to_string(index=False))
    print(json.dumps(correlacion_pfi_xg(), ensure_ascii=False, indent=2))
