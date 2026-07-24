#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Informe mensual de rendimiento e inversión (v37 §7).

Lee rendimiento_real.db (los picks REALES que el sistema publicó y que ya se
liquidaron) y produce, por mes natural:
  · tasa de acierto,
  · ROI real con la cuota registrada (cuota de cierre disponible al publicar),
  · EV medio prometido vs. resultado real (calibración de la rentabilidad),
  · evolución del bankroll asumiendo stake plano de 1 unidad por pick.

Todo se calcula desde la base ya existente — cero peticiones, cero estado de
usuario nuevo (arquitectura serverless del spec). Si no hay datos liquidados,
lo dice con transparencia en vez de inventar cifras.
"""

import logging
import os
import sqlite3
from typing import Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

DB = 'rendimiento_real.db'


def _picks_liquidados() -> pd.DataFrame:
    if not os.path.exists(DB):
        return pd.DataFrame()
    con = sqlite3.connect(DB)
    try:
        df = pd.read_sql_query(
            "SELECT fecha, deporte, liga, partido, apuesta, prob, cuota, ev, "
            "capa, resultado FROM picks WHERE resultado IS NOT NULL", con)
    except Exception as e:
        logger.warning(f"[resumen_mensual] lectura fallida: {e}")
        df = pd.DataFrame()
    finally:
        con.close()
    if df.empty:
        return df
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    df = df.dropna(subset=['fecha'])
    df['mes'] = df['fecha'].dt.strftime('%Y-%m')
    df['cuota'] = pd.to_numeric(df['cuota'], errors='coerce')
    df['ganancia'] = df.apply(
        lambda r: (r['cuota'] - 1) if r['resultado'] else -1.0, axis=1)
    return df


def informe_mes(mes: str = None) -> Dict:
    """Informe de un mes natural ('YYYY-MM'). Sin arg → mes en curso."""
    df = _picks_liquidados()
    mes = mes or pd.Timestamp.today().strftime('%Y-%m')
    if df.empty:
        return {'mes': mes, 'n': 0,
                'aviso': 'Aún no hay picks liquidados para informar.'}
    sub = df[df['mes'] == mes]
    if sub.empty:
        return {'mes': mes, 'n': 0,
                'aviso': f'Sin picks liquidados en {mes}.'}
    n = len(sub)
    aciertos = int(sub['resultado'].sum())
    ganancia = float(sub['ganancia'].sum())
    con_cuota = sub[sub['cuota'].notna() & (sub['cuota'] > 1)]
    return {
        'mes': mes, 'n': n, 'aciertos': aciertos,
        'tasa_acierto': round(aciertos / n, 4),
        'roi_pct': round(100 * ganancia / n, 2),
        'ganancia_unidades': round(ganancia, 2),
        'ev_medio_prometido': (round(float(sub['ev'].dropna().mean()), 4)
                               if sub['ev'].notna().any() else None),
        'prob_media_prometida': round(float(sub['prob'].dropna().mean()), 4),
        'cuota_media': (round(float(con_cuota['cuota'].mean()), 2)
                        if not con_cuota.empty else None),
        'por_deporte': _desglose(sub, 'deporte'),
        'por_capa': _desglose(sub, 'capa'),
    }


def _desglose(sub: pd.DataFrame, col: str) -> List[Dict]:
    out = []
    for valor, g in sub.groupby(col):
        n = len(g)
        out.append({col: valor, 'n': n,
                    'tasa_acierto': round(int(g['resultado'].sum()) / n, 3),
                    'roi_pct': round(100 * float(g['ganancia'].sum()) / n, 2)})
    return sorted(out, key=lambda d: -d['n'])


def serie_mensual() -> pd.DataFrame:
    """Un renglón por mes con tasa de acierto, ROI y bankroll acumulado
    (stake plano de 1 unidad por pick)."""
    df = _picks_liquidados()
    if df.empty:
        return pd.DataFrame()
    g = df.groupby('mes').agg(
        picks=('resultado', 'size'),
        aciertos=('resultado', 'sum'),
        ganancia=('ganancia', 'sum'),
        ev_prometido=('ev', 'mean')).reset_index()
    g['tasa_acierto'] = (g['aciertos'] / g['picks']).round(4)
    g['roi_pct'] = (100 * g['ganancia'] / g['picks']).round(2)
    g['bankroll_acumulado'] = g['ganancia'].cumsum().round(2)
    return g


def meses_disponibles() -> List[str]:
    df = _picks_liquidados()
    return sorted(df['mes'].unique().tolist(), reverse=True) if not df.empty else []


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(informe_mes(), indent=2, ensure_ascii=False))
