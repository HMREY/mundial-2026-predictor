#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CARRIL B (v28 §3.2) — Índice de Cohesión de Jaccard.

J(A, H) = |A∩H| / |A∪H| con A = once confirmado de HOY (ESPN) y H = los 11
con más titularidades en los últimos 30 días (base sombra v19). J < 0.7
sugiere fractura táctica (rotación masiva). Feature del futuro VORP-PFI.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

UMBRAL_FRACTURA = 0.7


def once_historico(equipo: str, dias: int = 30) -> Optional[List[str]]:
    """Los 11 con más titularidades del equipo en la ventana."""
    try:
        al = pd.read_csv('alineaciones_historicas.csv', parse_dates=['fecha'])
    except Exception:
        return None
    corte = pd.Timestamp.today() - pd.Timedelta(days=dias)
    sub = al[(al['equipo'] == equipo) & (al['titular'])
             & (al['fecha'] >= corte)]
    if sub['event_id'].nunique() < 2:
        return None
    top = (sub.groupby('jugador')['event_id'].nunique()
           .sort_values(ascending=False).head(11))
    return list(top.index)


def jaccard(hoy: List[str], historico: List[str]) -> float:
    a, h = set(hoy), set(historico)
    return len(a & h) / max(len(a | h), 1)


def cohesion_partido(liga: str, home: str, away: str) -> Dict:
    """J por lado con la alineación confirmada de hoy (ESPN)."""
    import alineacion_vorp as av
    lineups = av.alineacion_hoy(liga, home, away)
    out = {}
    for lado, equipo in (('home', home), ('away', away)):
        hoy = (lineups or {}).get(lado) or []
        hist = once_historico(equipo)
        if len(hoy) >= 10 and hist:
            j = round(jaccard(hoy, hist), 3)
            out[lado] = {'jaccard': j, 'fractura': j < UMBRAL_FRACTURA}
        else:
            out[lado] = {'jaccard': None,
                         'motivo': 'sin alineación de hoy o sin historial 30d'}
    return out


if __name__ == '__main__':
    import json
    import sys
    logging.basicConfig(level=logging.INFO)
    liga, h, a = (sys.argv[1:4] + ['mundial', 'France', 'England'])[:3]
    print(json.dumps(cohesion_partido(liga, h, a), ensure_ascii=False, indent=2))
