#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestión de banca — criterio de Kelly fraccional (v19).

El criterio de Kelly maximiza el crecimiento logarítmico de la banca a largo
plazo apostando la fracción f = (p·cuota − 1) / (cuota − 1) del bankroll en
cada apuesta con valor esperado positivo. Apostar Kelly completo es muy
volátil y muy sensible a errores en p, así que se usa **¼ de Kelly**
(fracción configurable), práctica estándar entre apostadores profesionales.

Solo tiene sentido con CUOTAS REALES y probabilidades bien calibradas: con
cuotas justas del modelo (EV≈0) el stake es siempre ~0 por construcción.

Puramente informativo: no afecta al modelo ni al backtesting.
"""

FRACCION_KELLY = 0.25   # ¼ Kelly
STAKE_MAX_PCT = 0.05    # tope de seguridad: nunca sugerir >5 % del bankroll

AVISO_JUEGO_RESPONSABLE = (
    "⚠️ Esta recomendación es informativa y asume que las probabilidades del "
    "modelo están bien calibradas. Apuesta solo lo que puedas permitirte perder."
)


def calcular_stake(prob: float, cuota: float, bankroll: float,
                   fraccion: float = FRACCION_KELLY) -> dict:
    """Stake recomendado por Kelly fraccional.

    Devuelve dict con 'stake' (unidades), 'pct' (fracción del bankroll ya
    multiplicada por la fracción de Kelly) y 'kelly_pleno' (f sin fraccionar).
    Stake 0 si no hay valor (EV <= 0) o entradas inválidas.
    """
    if not (0.0 < prob < 1.0) or cuota <= 1.0 or bankroll <= 0:
        return {'stake': 0.0, 'pct': 0.0, 'kelly_pleno': 0.0}
    f = (prob * cuota - 1.0) / (cuota - 1.0)
    if f <= 0:
        return {'stake': 0.0, 'pct': 0.0, 'kelly_pleno': round(f, 4)}
    pct = min(f * fraccion, STAKE_MAX_PCT)
    return {'stake': round(bankroll * pct, 2), 'pct': round(pct, 4),
            'kelly_pleno': round(f, 4)}


if __name__ == '__main__':
    # mini-verificación: p=0.55 a cuota 2.00 -> Kelly pleno 10 %, ¼ = 2.5 %
    r = calcular_stake(0.55, 2.00, 1000)
    assert abs(r['kelly_pleno'] - 0.10) < 1e-9, r
    assert abs(r['pct'] - 0.025) < 1e-9, r
    assert abs(r['stake'] - 25.0) < 1e-9, r
    # sin valor -> stake 0
    assert calcular_stake(0.40, 2.00, 1000)['stake'] == 0.0
    # tope 5 %: p=0.80 a cuota 2.5 -> Kelly pleno 66.7 %, ¼ = 16.7 % -> 5 %
    assert calcular_stake(0.80, 2.50, 1000)['pct'] == STAKE_MAX_PCT
    print('bankroll_manager OK')
