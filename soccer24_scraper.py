#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Soccer24 — INVIABLE con requests planos (verificado 2026-07-16, v24).

El master prompt v24 afirmaba que Soccer24 expone una "API interna no
documentada pero accesible" en:

    https://www.soccer24.com/api/matches/{matchId}/statistics

**FALSO, verificado empíricamente** (transparencia obligatoria, regla de oro):

  1. Ese endpoint devuelve 404 con una página HTML genérica de error: la ruta
     /api/ NO existe en soccer24.com.
  2. Soccer24 es un portal de la familia livesport/Flashscore. Sus datos
     reales viajan por feeds firmados (d.soccer24.com/x/feed/...) que exigen
     el header `x-fsign`; la firma pública histórica (SW9D1eZo) devuelve
     cuerpo "0" (rechazado) y la firma vigente no aparece en los bundles JS
     públicos (constants/loader/runtime revisados) — se genera en cliente.
  3. La portada tampoco server-renderiza ids de partido (g_1_*): todo se
     monta en cliente desde los feeds firmados. Scraping = JS pesado, el
     mismo motivo por el que Flashscore se descartó en v14.

Conclusión v24: lo que se esperaba de Soccer24 (estadísticas defensivas:
entradas, intercepciones, despejes) **lo publica FotMob** en el JSON
__NEXT_DATA__ de cada partido, accesible con requests planos — ver
fotmob_scraper.py (grupo "Defence": Tackles, Interceptions, Blocks,
Clearances, Keeper saves). Este módulo queda como constancia del sondeo y
para re-verificar si Soccer24 abre sus feeds en el futuro.

Uso:  python soccer24_scraper.py   # re-ejecuta el sondeo y reporta
"""

import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)

UA = {'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                     'AppleWebKit/537.36 (KHTML, like Gecko) '
                     'Chrome/126.0.0.0 Safari/537.36')}


def sondear() -> Dict[str, str]:
    """Re-verifica los tres hallazgos del sondeo v24. Si algún día el
    endpoint /api/ o los feeds respondieran, este será el primer aviso."""
    pruebas = {
        'api_statistics': ('https://www.soccer24.com/api/matches/1/statistics', None),
        'feed_firmado': ('https://d.soccer24.com/x/feed/f_1_0_1_en_1',
                         {'x-fsign': 'SW9D1eZo'}),
        'portada': ('https://www.soccer24.com/', None),
    }
    resultado = {}
    for nombre, (url, extra) in pruebas.items():
        h = dict(UA)
        if extra:
            h.update(extra)
        try:
            r = requests.get(url, headers=h, timeout=20)
            viable = (r.status_code == 200 and len(r.text) > 10
                      and nombre != 'portada')
            resultado[nombre] = (f"HTTP {r.status_code}, {len(r.text)} bytes"
                                 + (' — ¡REVISAR, puede haberse abierto!' if viable else ''))
        except Exception as e:
            resultado[nombre] = f'{type(e).__name__}: {e}'
    return resultado


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    for k, v in sondear().items():
        print(f'{k}: {v}')
