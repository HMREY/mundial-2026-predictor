#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Walk-forward A/B del Índice de Momentum Táctico (v24, spec §3.4).

Para cada liga compara TRES variantes con ventanas idénticas de 6 meses
rodando sobre el último 40 % del histórico (mismo arnés que el panel v22):

  * base   — la configuración ADOPTADA de producción de la liga.
  * imt    — base + las 4 componentes del IMT (M, ΔxG, F, P como diffs).
  * imt_c  — base + el índice COMPUESTO IMT_DIFF con α,β,γ,δ ajustados por
             ventana SOLO con el train de esa ventana (sin fuga; spec §3.2).

Regla de oro (v16/v17): se adopta una variante si mejora la precisión media
≥ +0.3 pp sin empeorar el log-loss medio > 0.01, o si mejora ambos. Si las
dos variantes pasan, gana la de mejor log-loss. Resultado por liga en
resultados_imt_v24.json; la adopción se aplica a mano en config.LEAGUES
('imt' en features_extra) y se reentrena producción.

Uso:  python run_wf_imt_v24.py [liga ...]      # sin args: todas
"""

import json
import logging
import os
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

import feature_engineering as fe
import league_engine
import momentum_tactico as mt
from config import LEAGUES
from train_tda_model import construir_ensemble, calcular_features_topologicas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ARCHIVO = 'resultados_imt_v24.json'
MIN_PARTIDOS_VENTANA = 60
MIN_TRAIN = 250


def _dataset(clave: str):
    ruta = f'historico_{clave}.csv'
    if not os.path.exists(ruta):
        raise FileNotFoundError(ruta)
    df = pd.read_csv(ruta, parse_dates=['date'])
    ds = fe.construir_dataset_supervisado(df)
    X_df = ds['X_df'].reset_index(drop=True).copy()
    ids = [m[3] for m in ds['meta']]

    cols_base = league_engine.columnas_extra(clave)
    cols_base = [c for c in cols_base if c not in mt.COLS_IMT]  # base pura
    if cols_base:
        extras_df, _ = league_engine.features_extra_liga(df)
        if 'mx' in LEAGUES[clave].get('features_extra', []):
            extras_df = extras_df.join(league_engine.features_mx(df))
        ext = extras_df.reindex(ids).reset_index(drop=True)
        for c in cols_base:
            X_df[c] = ext[c].values

    imt_df, _ = mt.features_imt(df)
    ext_imt = imt_df.reindex(ids).reset_index(drop=True)
    for c in mt.COLS_IMT:
        X_df[c] = ext_imt[c].values

    topo = calcular_features_topologicas(ds)
    return df, imt_df, X_df, ds['y'], ds['fechas'], topo, ids, cols_base


def _modelo(clave: str):
    if LEAGUES[clave].get('calibracion') == 'beta':
        return league_engine.ModeloBetaCalibrado()
    return construir_ensemble()


def _evaluar_ventana(clave, X, y, topo, m_tr, m_va, cols):
    Xv = X[cols].copy()
    for c in cols:
        if c in league_engine.COLS_CUOTAS:
            Xv[c] = Xv[c].fillna(float(pd.to_numeric(
                Xv.loc[m_tr, c], errors='coerce').mean()))
        else:
            Xv[c] = Xv[c].fillna(0.0)
    X_tr_n, X_va_n, _ = fe.normalizar_features(Xv[m_tr], Xv[m_va])
    modelo = _modelo(clave)
    modelo.fit(np.hstack([X_tr_n, topo[m_tr]]), y[m_tr])
    proba = modelo.predict_proba(np.hstack([X_va_n, topo[m_va]]))
    return (float(accuracy_score(y[m_va], proba.argmax(axis=1))),
            float(log_loss(y[m_va], proba, labels=[0, 1, 2])))


def wf_liga(clave: str) -> dict:
    df, imt_df, X_df, y, fechas, topo, ids, cols_base = _dataset(clave)
    cols_modelo = list(fe.FEATURES_MODELO)
    inicio_wf = fechas.quantile(0.60).normalize().replace(day=1)
    ventanas = pd.date_range(inicio_wf, fechas.max(), freq='6MS')

    res = {'base': [], 'imt': [], 'imt_c': []}
    coefs = []
    for inicio in ventanas:
        fin = inicio + pd.DateOffset(months=6)
        m_tr = (fechas < inicio).values
        m_va = ((fechas >= inicio) & (fechas < fin)).values
        if m_va.sum() < MIN_PARTIDOS_VENTANA or m_tr.sum() < MIN_TRAIN:
            continue

        # composite por ventana: α,β,γ,δ del train de ESTA ventana
        rep = mt.optimizar_coeficientes(df, imt_df, hasta_fecha=inicio)
        comp = mt.indice_compuesto(imt_df, rep['coef'])
        X_df['IMT_DIFF'] = comp.reindex(ids).values
        coefs.append({'ventana': str(inicio.date()), **rep})

        variantes = {
            'base': cols_modelo + cols_base,
            'imt': cols_modelo + cols_base + mt.COLS_IMT,
            'imt_c': cols_modelo + cols_base + mt.COLS_IMT_C,
        }
        fila = {}
        for nombre, cols in variantes.items():
            acc, ll = _evaluar_ventana(clave, X_df, y, topo, m_tr, m_va, cols)
            res[nombre].append({'ventana': str(inicio.date()),
                                'n': int(m_va.sum()),
                                'acc': round(acc, 4), 'll': round(ll, 4)})
            fila[nombre] = f"{acc:.3f}/{ll:.3f}"
        logger.info(f"  [{clave}] {inicio.date()} n={m_va.sum()} :: "
                    + ' · '.join(f'{k} {v}' for k, v in fila.items()))

    if not res['base']:
        return {}

    def _media(v):
        return (round(float(np.mean([f['acc'] for f in res[v]])), 4),
                round(float(np.mean([f['ll'] for f in res[v]])), 4))

    acc_b, ll_b = _media('base')
    resumen = {'ventanas': res, 'coeficientes_por_ventana': coefs,
               'media': {v: {'acc': _media(v)[0], 'll': _media(v)[1]}
                         for v in res}}
    adoptar = None
    for v in ('imt', 'imt_c'):
        acc_v, ll_v = _media(v)
        pasa = ((acc_v - acc_b >= 0.003 and ll_v - ll_b <= 0.01)
                or (acc_v > acc_b and ll_v < ll_b))
        resumen['media'][v]['pasa_regla_de_oro'] = bool(pasa)
        if pasa and (adoptar is None
                     or ll_v < resumen['media'][adoptar]['ll']):
            adoptar = v
    resumen['adoptar'] = adoptar
    logger.info(f"[{clave}] base {acc_b}/{ll_b} · "
                f"imt {_media('imt')} · imt_c {_media('imt_c')} → "
                f"ADOPTAR: {adoptar or 'ninguna'}")
    return resumen


if __name__ == '__main__':
    objetivos = sys.argv[1:] or [c for c, cfg in LEAGUES.items()
                                 if cfg.get('disponible')]
    salida = {}
    if os.path.exists(ARCHIVO):
        with open(ARCHIVO, encoding='utf-8') as f:
            salida = json.load(f)
    for clave in objetivos:
        logger.info(f"=== IMT walk-forward {clave} ===")
        try:
            r = wf_liga(clave)
            if r:
                salida[clave] = r
        except Exception as e:
            logger.error(f"[{clave}] falló: {type(e).__name__}: {e}")
        with open(ARCHIVO, 'w', encoding='utf-8') as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: {'base': v['media']['base'],
                          'imt': v['media']['imt'],
                          'imt_c': v['media']['imt_c'],
                          'adoptar': v['adoptar']}
                      for k, v in salida.items()}, indent=2))
