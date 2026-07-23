#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest de Markowitz vs Kelly simultáneo (v34 §5) con datos REALES.

Usa las apuestas simuladas de la validación de todas las ligas
(roi_bets_*.json: probabilidad, cuota de cierre y resultado real), agrupadas
por DÍA para reconstruir carteras diarias. Compara:

  * Kelly simultáneo ⅛ con cap del 20 % (el actual)
  * Markowitz de máximo Sharpe con covarianza diagonal entre ligas

Métricas: ROI acumulado, drawdown máximo y volatilidad diaria.
Adopción (§5): solo si Markowitz reduce el drawdown >5 % sin penalizar el ROI.
"""
import glob
import json
import logging
from collections import defaultdict

import numpy as np

import kelly_simultaneo as ks
import portfolio_optimizer as po

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def cargar_por_dia():
    dias = defaultdict(list)
    for ruta in glob.glob('roi_bets_*.json'):
        liga = ruta[len('roi_bets_'):-len('.json')]
        try:
            with open(ruta, encoding='utf-8') as f:
                for b in json.load(f):
                    dias[b['fecha']].append({
                        'liga': liga, 'fecha': b['fecha'],
                        'partido': f"{liga}-{b['fecha']}-{len(dias[b['fecha']])}",
                        'apuesta': 'pick', 'prob': b['prob'],
                        'cuota': b['cuota'], 'gano': b['gano']})
        except Exception:
            continue
    return dias


def _simular(dias, estrategia: str):
    capital, serie, pico, maxdd = 1.0, [], 1.0, 0.0
    for fecha in sorted(dias):
        picks = dias[fecha]
        if estrategia == 'kelly':
            pesos = [s['stake_pct'] for s in ks.stakes_jornada(picks, 1.0)]
        else:
            opt = po.optimizar(picks, exposicion_total=0.20)
            mapa = {(p['partido']): p['peso_pct'] / 100
                    for p in opt.get('pesos', [])}
            pesos = [mapa.get(p['partido'], 0.0) for p in picks]
        ret = sum(w * ((p['cuota'] - 1) if p['gano'] else -1)
                  for w, p in zip(pesos, picks))
        capital *= (1 + ret)
        pico = max(pico, capital)
        maxdd = max(maxdd, 1 - capital / pico)
        serie.append(ret)
    return {'roi_total_pct': round((capital - 1) * 100, 2),
            'drawdown_max_pct': round(maxdd * 100, 2),
            'volatilidad_diaria_pct': round(float(np.std(serie)) * 100, 3),
            'dias': len(serie)}


def main():
    dias = cargar_por_dia()
    multi = {d: p for d, p in dias.items() if len(p) >= 2}
    logger.info(f"{len(dias)} días con picks ({len(multi)} con ≥2 simultáneos)")
    # v34: control adicional — el MISMO capital aplicando el filtro de EV
    # extremo validado en v32 (>15 % = zona descalibrada). Sirve para saber
    # si la pérdida viene de la estrategia de stake o de los picks.
    filtrados = {d: [p for p in ps if (p['cuota'] * p['prob'] - 1) <= 0.15]
                 for d, ps in dias.items()}
    filtrados = {d: ps for d, ps in filtrados.items() if ps}
    r = {'n_dias': len(dias), 'n_dias_multipick': len(multi),
         'kelly_simultaneo': _simular(dias, 'kelly'),
         'markowitz': _simular(dias, 'markowitz'),
         'kelly_con_filtro_ev_v32': _simular(filtrados, 'kelly'),
         'markowitz_con_filtro_ev_v32': _simular(filtrados, 'markowitz')}
    k, m = r['kelly_simultaneo'], r['markowitz']
    reduce_dd = k['drawdown_max_pct'] - m['drawdown_max_pct']
    r['reduccion_drawdown_pp'] = round(reduce_dd, 2)
    r['adoptar'] = bool(reduce_dd > 5 and m['roi_total_pct'] >= k['roi_total_pct'] * 0.9)
    logger.info(f"kelly {k} · markowitz {m} → "
                f"{'ADOPTAR como opción' if r['adoptar'] else 'NO se adopta'}")
    with open('resultados_markowitz_v34.json', 'w', encoding='utf-8') as f:
        json.dump(r, f, indent=2)
    return r


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
