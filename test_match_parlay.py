#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests del asistente de parlay por partido (v15).

Ejecutar:  .venv\\Scripts\\python test_match_parlay.py
"""

import math

from match_parlay import (construir_parlay_partido, obtener_selecciones,
                          _compatibles, _correlacionadas, PERFILES,
                          HAIRCUT_CORRELACION)

FALLOS = []


def check(cond, msg):
    print(('OK  ' if cond else 'FALLO') + ' ' + msg)
    if not cond:
        FALLOS.append(msg)


def probar_motor(nombre, motor, home, away):
    print(f"\n=== {nombre}: {home} vs {away} ===")

    # 1) número exacto de selecciones y umbrales por perfil
    for perfil, umbral in PERFILES.items():
        for n in (4, 6, 8):
            r = construir_parlay_partido(motor, home, away, num_selecciones=n,
                                         perfil=perfil, excluir_alto_riesgo=False)
            if 'error' in r:
                check(False, f"{perfil}/n={n}: {r['error']}")
                continue
            esperado = min(n, r['n_selecciones'])
            check(r['n_selecciones'] == esperado and r['n_selecciones'] >= 2,
                  f"{perfil}/n={n}: devuelve {r['n_selecciones']} selecciones")
            umbral_ok = all(s['prob'] >= r['umbral_usado'] - 1e-9 for s in r['selecciones'])
            check(umbral_ok, f"{perfil}/n={n}: todas las probs >= umbral usado "
                             f"({r['umbral_usado']*100:.0f} %)")
            if r['umbral_usado'] < umbral:
                check(any('relajó' in a or 'relajo' in a for a in r['avisos']),
                      f"{perfil}/n={n}: avisa cuando relaja el umbral")

    # 2) sin conflictos entre las selecciones elegidas
    r = construir_parlay_partido(motor, home, away, num_selecciones=8,
                                 perfil='agresivo', excluir_alto_riesgo=False)
    check('error' not in r, "agresivo/8 genera parlay")
    if 'error' not in r:
        pl = motor.plantilla_club(home, away) if hasattr(motor, 'plantilla_club') \
            else motor.plantilla(home, away)
        sels = {s.apuesta: s for s in obtener_selecciones(pl)}
        elegidas = [sels[x['apuesta']] for x in r['selecciones'] if x['apuesta'] in sels]
        sin_conflicto = all(_compatibles(a, b)
                            for i, a in enumerate(elegidas) for b in elegidas[:i])
        check(sin_conflicto, "ninguna pareja elegida es incompatible")

        # 3) probabilidad conjunta = producto * haircut^n_parejas
        prod = 1.0
        for s in elegidas:
            prod *= s.prob
        n_corr = sum(1 for i, a in enumerate(elegidas) for b in elegidas[:i]
                     if _correlacionadas(a, b))
        esperada = prod * HAIRCUT_CORRELACION ** n_corr
        check(math.isclose(r['prob_conjunta'], esperada, rel_tol=1e-3),
              f"prob conjunta coherente ({r['prob_conjunta']:.4f} ~ {esperada:.4f}, "
              f"{n_corr} parejas correlacionadas)")

        # 4) aviso de EV teórico sin cuotas reales
        if not r['cuotas_reales']:
            check('teórico' in r['nota'] or 'teorico' in r['nota'],
                  "aviso de EV teórico presente sin cuotas reales")
            check(r['ev_parlay'] == 0.0, "EV = 0 con cuotas justas")


if __name__ == '__main__':
    from prediction_api import PredictionEngine
    from league_engine import ClubEngine

    probar_motor('Mundial', PredictionEngine(), 'MEX', 'ECU')

    club = ClubEngine('premier')
    if club.listo:
        e = [t for t in club.equipos if t in ('Arsenal', 'Aston Villa')]
        h, a = (e[0], e[1]) if len(e) == 2 else (club.equipos[0], club.equipos[1])
        probar_motor('Premier', club, h, a)

    print(f"\n{'='*40}\n{'TODO OK' if not FALLOS else f'{len(FALLOS)} FALLOS'}")
    raise SystemExit(1 if FALLOS else 0)
