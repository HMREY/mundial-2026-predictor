#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoría de modelos (v43 §1) — cada liga contra su mercado de cierre.

Para cada liga con historial de apuestas reales (roi_bets, que ya traen la
cuota apostada, el cierre de Pinnacle y el resultado), calcula:
  · precisión del modelo vs. la implícita del cierre (¿batimos al mercado?),
  · ROI simulado con la cuota de cierre,
  · CLV medio (cuota nuestra vs. cierre de Pinnacle),
  · un semáforo 🟢/🟡/🔴 y un diagnóstico de por qué falla si no bate.

Es la "matriz de rendimiento" del spec: da al usuario transparencia total
(en qué modelo confiar) y a nosotros la lista de modelos a mejorar. Se
precalcula (cero cómputo en el frontend) y se guarda en model_audit.json.
"""

import glob
import json
import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

ARCHIVO = 'model_audit.json'


def _apuestas(liga: str) -> List[Dict]:
    try:
        return [b for b in json.load(open(f'roi_bets_{liga}.json', encoding='utf-8'))
                if b.get('cuota') and b.get('gano') is not None]
    except Exception:
        return []


def _diagnostico(n: int, roi: float, clv: float, bate: bool) -> str:
    if bate and roi > 0:
        return "Bate al mercado y es rentable."
    causas = []
    if n < 150:
        causas.append("pocos datos históricos")
    if clv is not None and clv < -1:
        causas.append(f"CLV negativo ({clv:+.1f} %): apostamos peor que el cierre")
    if not bate:
        causas.append("mercado muy eficiente (no superamos su implícita)")
    if roi < 0 and not causas:
        causas.append("varianza / calibración en los extremos")
    return "No bate: " + ", ".join(causas) + "." if causas else "Rendimiento marginal."


def auditar(guardar: bool = True) -> Dict:
    from config import LEAGUES
    filas = []
    for liga, cfg in LEAGUES.items():
        bs = _apuestas(liga)
        if not bs:
            continue
        n = len(bs)
        roi = 100 * sum((b['cuota'] - 1) if b['gano'] else -1 for b in bs) / n
        acc = sum(b['gano'] for b in bs) / n
        # implícita del cierre (Pinnacle si está, si no la cuota apostada)
        con_pin = [b for b in bs if b.get('cuota_pin')]
        clv = (100 * np.mean([b['cuota'] / b['cuota_pin'] - 1 for b in con_pin])
               if con_pin else None)
        # ¿batimos la precisión implícita del mercado? proxy: acc del modelo vs
        # la tasa implícita media de sus propias selecciones (1/cuota_cierre)
        ref = [1.0 / b.get('cuota_pin', b['cuota']) for b in bs]
        acc_mercado = float(np.mean(ref))
        bate = acc >= acc_mercado
        semaforo = ('🟢' if (bate and roi > 0) else
                    '🟡' if (roi > -3 or bate) else '🔴')
        filas.append({
            'liga': liga, 'nombre': cfg.get('nombre', liga),
            'disponible': bool(cfg.get('disponible')),
            'n': n, 'precision': round(acc, 3),
            'precision_mercado': round(acc_mercado, 3),
            'bate_mercado': bool(bate), 'roi_pct': round(roi, 2),
            'clv_pct': round(float(clv), 2) if clv is not None else None,
            'semaforo': semaforo,
            'diagnostico': _diagnostico(n, roi, clv, bate),
        })
    filas.sort(key=lambda f: -f['roi_pct'])
    salida = {'generado': __import__('pandas').Timestamp.today().strftime('%Y-%m-%d'),
              'n_ligas': len(filas),
              'ligas_rentables': sum(1 for f in filas if f['roi_pct'] > 0),
              'ligas': filas}
    if guardar:
        with open(ARCHIVO, 'w', encoding='utf-8') as f:
            json.dump(salida, f, ensure_ascii=False, indent=1)
    logger.info(f"[audit] {len(filas)} ligas · "
                f"{salida['ligas_rentables']} rentables")
    return salida


def cargar() -> Dict:
    try:
        with open(ARCHIVO, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    r = auditar()
    print(f"{r['ligas_rentables']}/{r['n_ligas']} ligas rentables\n")
    for f in r['ligas']:
        print(f"  {f['semaforo']} {f['nombre']:22s} n={f['n']:4d} "
              f"ROI={f['roi_pct']:+6.1f}% acc={f['precision']:.3f} "
              f"CLV={f['clv_pct']}")
