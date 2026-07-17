#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experimento MESM v24 — extensión a todas las ligas + estrategia E (spec §4).

Diferencias contra run_mesm_v23:
  1. El base de cada ventana usa la CONFIGURACIÓN ADOPTADA de la liga
     (features extra + beta calibration), no el ensemble genérico — la
     lección v23: el screening con base genérico decía "todas mejoran" y era
     un espejismo; el base debe ser tan bueno como producción.
  2. Estrategia E: el meta-modelo recibe además las 4 componentes IMT
     (diffs local−visitante) — ¿el momentum ayuda a decidir cuándo fiarse
     del mercado y cuándo del modelo?
  3. Se incluye la MLS (nueva en v24).

Por ventana de 6 meses sobre el último 40 %:
  base   = modelo config-adoptada entrenado con el 75 % inicial del train
  mesm_d = MetaEnsemble estándar (v23) ajustado con el 25 % final
  mesm_e = MetaEnsemble + componentes IMT como features extra del meta
Comparación en la MISMA validación (solo filas con cuotas): precisión,
log-loss, mercado y ROI simulado. Regla de oro por liga y por variante.

Uso: python run_mesm_v24.py [liga ...]
"""

import json
import logging
import sys
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

import feature_engineering as fe
import league_engine
import meta_ensemble as me
import momentum_tactico as mt
from config import LEAGUES
from train_tda_model import construir_ensemble, calcular_features_topologicas

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LIGAS = ['liga_mx', 'mls', 'premier', 'laliga', 'serie_a', 'bundesliga',
         'ligue_1', 'eredivisie', 'primeira']
ARCHIVO = 'resultados_mesm_v24.json'


def _modelo(clave: str):
    if LEAGUES[clave].get('calibracion') == 'beta':
        return league_engine.ModeloBetaCalibrado()
    return construir_ensemble()


def evaluar_liga(clave: str) -> dict:
    df = pd.read_csv(f'historico_{clave}.csv', parse_dates=['date'])
    ds = fe.construir_dataset_supervisado(df)
    X_df = ds['X_df'].reset_index(drop=True).copy()
    y, fechas = np.array(ds['y']), ds['fechas']
    ids = [m[3] for m in ds['meta']]

    # config adoptada de la liga (sin 'imt': el A/B del IMT es aparte)
    cols_base = [c for c in league_engine.columnas_extra(clave)
                 if c not in mt.COLS_IMT]
    if cols_base:
        extras_df, _ = league_engine.features_extra_liga(df)
        if 'mx' in LEAGUES[clave].get('features_extra', []):
            extras_df = extras_df.join(league_engine.features_mx(df))
        ext = extras_df.reindex(ids).reset_index(drop=True)
        for c in cols_base:
            X_df[c] = ext[c].values

    imt_df, _ = mt.features_imt(df)
    imt_all = imt_df.reindex(ids)[mt.COLS_IMT].values

    topo = calcular_features_topologicas(ds)
    cuotas = df.set_index('MATCH_ID').reindex(ids)[['odd_home', 'odd_draw', 'odd_away']]
    mkt = me.probs_mercado(cuotas)
    con_mkt = np.isfinite(mkt).all(axis=1)
    logger.info(f"[{clave}] {len(X_df)} partidos, cuotas en {con_mkt.mean()*100:.0f} %, "
                f"config base: {cols_base or 'genérica'}")

    cols_todas = list(fe.FEATURES_MODELO) + cols_base
    inicio_eval = fechas.quantile(0.60)
    ventanas = pd.date_range(inicio_eval.normalize(), fechas.max(), freq='6MS')
    filas = []
    for ini in ventanas:
        fin = ini + pd.DateOffset(months=6)
        m_tr = (fechas < ini).values & con_mkt
        m_va = ((fechas >= ini) & (fechas < fin)).values & con_mkt
        if m_va.sum() < 60 or m_tr.sum() < 250:
            continue
        idx_tr = np.where(m_tr)[0]
        corte = int(len(idx_tr) * 0.75)
        idx_fit, idx_meta = idx_tr[:corte], idx_tr[corte:]
        if len(idx_meta) < 80:
            continue

        # imputación de cuotas con medias del fit SOLO (sin fuga)
        Xv = X_df[cols_todas].copy()
        for c in cols_base:
            if c in league_engine.COLS_CUOTAS:
                Xv[c] = Xv[c].fillna(float(pd.to_numeric(
                    Xv.iloc[idx_fit][c], errors='coerce').mean()))
            else:
                Xv[c] = Xv[c].fillna(0.0)

        Xn_fit, _, esc = fe.normalizar_features(Xv.iloc[idx_fit], None)
        base = _modelo(clave)
        base.fit(np.hstack([Xn_fit, topo[idx_fit]]), y[idx_fit])

        def probs_de(idx):
            Xn = esc.transform(Xv.iloc[idx])
            proba = base.predict_proba(np.hstack([Xn, topo[idx]]))
            p = np.zeros((len(idx), 3))
            for k_idx, k in enumerate(base.classes_):
                p[:, int(k)] = proba[:, k_idx]
            return p / p.sum(axis=1, keepdims=True)

        p_meta_tr = probs_de(idx_meta)
        meta_d = me.MetaEnsemble().fit(y[idx_meta], p_meta_tr, mkt[idx_meta])
        meta_e = me.MetaEnsemble().fit(y[idx_meta], p_meta_tr, mkt[idx_meta],
                                       extra=imt_all[idx_meta])

        idx_va = np.where(m_va)[0]
        p_base = probs_de(idx_va)
        p_d = meta_d.predict_proba(p_base, mkt[idx_va])
        p_e = meta_e.predict_proba(p_base, mkt[idx_va], extra=imt_all[idx_va])
        y_va = y[idx_va]
        fav_mkt = mkt[idx_va, :3].argmax(axis=1)
        cuotas_va = cuotas.iloc[idx_va]

        fila = {
            'ventana': f"{ini.date()} → {fin.date()}", 'n': int(m_va.sum()),
            'acc_base': round(float(accuracy_score(y_va, p_base.argmax(1))), 4),
            'acc_mesm_d': round(float(accuracy_score(y_va, p_d.argmax(1))), 4),
            'acc_mesm_e': round(float(accuracy_score(y_va, p_e.argmax(1))), 4),
            'acc_mercado': round(float(accuracy_score(y_va, fav_mkt)), 4),
            'll_base': round(float(log_loss(y_va, p_base, labels=[0, 1, 2])), 4),
            'll_mesm_d': round(float(log_loss(y_va, p_d, labels=[0, 1, 2])), 4),
            'll_mesm_e': round(float(log_loss(y_va, p_e, labels=[0, 1, 2])), 4),
            'roi_mesm_d': me.roi_simulado(y_va, p_d, cuotas_va),
            'roi_mesm_e': me.roi_simulado(y_va, p_e, cuotas_va),
        }
        filas.append(fila)
        logger.info(f"  {clave} {ini.date()}: base {fila['acc_base']:.3f} · "
                    f"D {fila['acc_mesm_d']:.3f}/{fila['ll_mesm_d']:.3f} · "
                    f"E {fila['acc_mesm_e']:.3f}/{fila['ll_mesm_e']:.3f} · "
                    f"mercado {fila['acc_mercado']:.3f}")
    if not filas:
        return {'liga': clave, 'ventanas': []}

    def media(k):
        return round(float(np.mean([f[k] for f in filas])), 4)

    def regla(acc_v, ll_v):
        return bool((media(acc_v) - media('acc_base') >= 0.003
                     and media(ll_v) - media('ll_base') <= 0.01)
                    or (media(acc_v) > media('acc_base')
                        and media(ll_v) < media('ll_base')))

    return {'liga': clave, 'ventanas': filas,
            'acc_base': media('acc_base'), 'acc_mercado': media('acc_mercado'),
            'acc_mesm_d': media('acc_mesm_d'), 'acc_mesm_e': media('acc_mesm_e'),
            'll_base': media('ll_base'),
            'll_mesm_d': media('ll_mesm_d'), 'll_mesm_e': media('ll_mesm_e'),
            'golden_d': regla('acc_mesm_d', 'll_mesm_d'),
            'golden_e': regla('acc_mesm_e', 'll_mesm_e')}


if __name__ == '__main__':
    objetivo = [a for a in sys.argv[1:] if not a.startswith('-')] or LIGAS
    resultados = {}
    for clave in objetivo:
        try:
            resultados[clave] = evaluar_liga(clave)
        except Exception as e:
            logger.error(f"[{clave}] falló: {type(e).__name__}: {e}")
        with open(ARCHIVO, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: {kk: v[kk] for kk in
                          ('acc_base', 'acc_mesm_d', 'acc_mesm_e', 'acc_mercado',
                           'll_base', 'll_mesm_d', 'll_mesm_e',
                           'golden_d', 'golden_e') if kk in v}
                      for k, v in resultados.items()}, indent=2))
