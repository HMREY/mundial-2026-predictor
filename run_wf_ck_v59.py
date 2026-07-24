#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B walk-forward de las features v59 (dominio territorial: córners, volumen de
remates, conversión) sobre las ligas de formato 'main' (las únicas que traen
córners y remates en football-data).

Regla de adopción (la de siempre en el proyecto):
  se ADOPTA en una liga si sube la precisión >= UMBRAL_PP puntos porcentuales
  SIN degradar el log-loss (o si mejora el log-loss sin bajar la precisión).

Uso:  python run_wf_ck_v59.py [liga ...]
"""

import json
import logging
import sys

logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

UMBRAL_PP = 0.003          # +0.3 pp, el mismo listón que usó la v26/v35
SALIDA = 'resultados_ck_v59.json'


def _entrenar(clave, con_ck):
    """Entrena la liga con y sin el grupo 'ck' y devuelve sus métricas."""
    import config
    import league_engine
    cfg = config.LEAGUES[clave]
    grupos = list(cfg.get('features_extra', []))
    original = list(grupos)
    if con_ck and 'ck' not in grupos:
        grupos.append('ck')
    if not con_ck and 'ck' in grupos:
        grupos.remove('ck')
    cfg['features_extra'] = grupos
    try:
        # OJO: se entrena en el ESPACIO DE FEATURES DE PRODUCCIÓN
        # (con_ratings=False). Usar con_ratings=True añadiría VAL_LOG_RATIO de
        # Transfermarkt y el A/B mediría en un espacio que no es el desplegado.
        # Como efecto colateral se sobrescriben los artefactos: al final del
        # experimento se reentrena cada liga con su configuración adoptada.
        r = league_engine.entrenar_liga(clave, con_ratings=False)
    finally:
        cfg['features_extra'] = original
    return r


def main(ligas):
    import config
    resultados = {}
    for clave in ligas:
        cfg = config.LEAGUES.get(clave)
        if not cfg or cfg.get('formato') != 'main':
            print(f"· {clave}: omitida (solo formato 'main' trae córners).")
            continue
        try:
            base = _entrenar(clave, con_ck=False)
            nuevo = _entrenar(clave, con_ck=True)
        except Exception as e:
            print(f"· {clave}: FALLÓ ({type(e).__name__}: {e})")
            continue
        acc_b = base.get('precision_validacion') or 0
        acc_n = nuevo.get('precision_validacion') or 0
        ll_b = base.get('log_loss_validacion') or 9
        ll_n = nuevo.get('log_loss_validacion') or 9
        d_acc, d_ll = acc_n - acc_b, ll_n - ll_b
        adopta = ((d_acc >= UMBRAL_PP and d_ll <= 0.0005)
                  or (d_ll < -0.005 and d_acc >= -0.0005))
        resultados[clave] = {
            'acc_base': round(acc_b, 4), 'acc_ck': round(acc_n, 4),
            'll_base': round(ll_b, 4), 'll_ck': round(ll_n, 4),
            'delta_acc_pp': round(d_acc * 100, 2),
            'delta_logloss': round(d_ll, 4), 'adoptado': bool(adopta),
        }
        print(f"· {clave:12} acc {acc_b:.4f} → {acc_n:.4f} ({d_acc*100:+.2f} pp) · "
              f"ll {ll_b:.4f} → {ll_n:.4f} ({d_ll:+.4f}) · "
              f"{'ADOPTAR ✅' if adopta else 'descartar'}")
    with open(SALIDA, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    adoptadas = [k for k, v in resultados.items() if v['adoptado']]
    print(f"\nAdoptadas ({len(adoptadas)}/{len(resultados)}): {adoptadas or '—'}")
    print(f"Detalle en {SALIDA}")


if __name__ == '__main__':
    import config
    ligas = sys.argv[1:] or [c for c, v in config.LEAGUES.items()
                             if v.get('formato') == 'main' and v.get('disponible')]
    main(ligas)
