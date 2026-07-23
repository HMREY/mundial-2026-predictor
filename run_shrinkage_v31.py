#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B del Decaimiento Inter-Temporada (v31 §3.2) en MLB.

Al arrancar la temporada, las medias móviles arrastran ruido (pocos juegos) o
la forma de la campaña anterior. Se encoge hacia la media de la LIGA:

    valor_ajustado = α·media_móvil + (1−α)·media_liga,  α = min(t/N, 1)

con t = juegos del equipo en la temporada actual y N = 20 (MLB, §3.2).
Walk-forward con y sin decaimiento; se adopta si supera la regla de oro.
"""
import json
import logging
import warnings

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, log_loss
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
logger = logging.getLogger(__name__)

MA, N_SHRINK = 10, 20


def _ens():
    vc = VotingClassifier([
        ('x', XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, verbosity=0)),
        ('l', LGBMClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, verbose=-1)),
        ('r', RandomForestClassifier(n_estimators=200, max_depth=8, random_state=42))], voting='soft')
    return CalibratedClassifierCV(vc, method='isotonic', cv=3)


def dataset(df: pd.DataFrame, shrink: bool):
    """Mismas features que MLBEngine, con/sin encogimiento a la media de liga."""
    df = df.sort_values('date').reset_index(drop=True)
    elo, rs, ra, streak, ultf, pit, cnt_temp = {}, {}, {}, {}, {}, {}, {}
    temporada = None
    X, y, fechas = [], [], []
    MEDIA_LIGA = 4.5          # carreras por equipo-juego (estable en MLB)
    for r in df.itertuples(index=False):
        h, a = r.home_team, r.away_team
        if r.date.year != temporada:
            temporada = r.date.year
            cnt_temp = {}
        eh, ea = elo.get(h, 1500.0), elo.get(a, 1500.0)

        def _m(d, k, dv):
            v = d.get(k, [])
            base = np.mean(v[-MA:]) if v else dv
            if shrink:
                alpha = min(cnt_temp.get(k, 0) / N_SHRINK, 1.0)
                return alpha * base + (1 - alpha) * MEDIA_LIGA
            return base
        rs_h, rs_a = _m(rs, h, 4.5), _m(rs, a, 4.5)
        ra_h, ra_a = _m(ra, h, 4.5), _m(ra, a, 4.5)
        rest_h = min((r.date - ultf[h]).days, 7) if h in ultf else 3
        rest_a = min((r.date - ultf[a]).days, 7) if a in ultf else 3
        pr_h = np.mean(pit.get(r.home_pitcher, [])[-5:]) if pit.get(r.home_pitcher) else 4.5
        pr_a = np.mean(pit.get(r.away_pitcher, [])[-5:]) if pit.get(r.away_pitcher) else 4.5
        if all(len(rs.get(t, [])) >= 5 for t in (h, a)):
            X.append([(eh - ea) / 100.0, (rs_h - rs_a) / 3.0, (ra_h - ra_a) / 3.0,
                      (streak.get(h, 0) - streak.get(a, 0)) / 5.0,
                      (rest_h - rest_a) / 5.0, (pr_h - pr_a) / 3.0,
                      (rs_h + rs_a) / 9.0, (ra_h + ra_a) / 9.0, (pr_h + pr_a) / 9.0])
            y.append(int(r.home_runs > r.away_runs))
            fechas.append(r.date)
        gh, ga = float(r.home_runs), float(r.away_runs)
        rs.setdefault(h, []).append(gh); ra.setdefault(h, []).append(ga)
        rs.setdefault(a, []).append(ga); ra.setdefault(a, []).append(gh)
        pit.setdefault(r.home_pitcher, []).append(ga)
        pit.setdefault(r.away_pitcher, []).append(gh)
        for eq, gano in ((h, gh > ga), (a, ga > gh)):
            streak[eq] = max(streak.get(eq, 0), 0) + 1 if gano else min(streak.get(eq, 0), 0) - 1
            cnt_temp[eq] = cnt_temp.get(eq, 0) + 1
        e_h = 1 / (1 + 10 ** ((ea - eh) / 400))
        s_h = 1.0 if gh > ga else 0.0
        elo[h] = eh + 20 * (s_h - e_h); elo[a] = ea + 20 * ((1 - s_h) - (1 - e_h))
        ultf[h] = ultf[a] = r.date
    return np.array(X), np.array(y), pd.Series(fechas)


def main():
    df = pd.read_csv('historico_mlb.csv', parse_dates=['date'])
    res = {}
    for shrink in (False, True):
        X, y, fechas = dataset(df, shrink)
        ini = fechas.quantile(0.60).normalize().replace(day=1)
        accs, lls, accs_ini = [], [], []
        for w in pd.date_range(ini, fechas.max(), freq='6MS'):
            fin = w + pd.DateOffset(months=6)
            mtr = (fechas < w).values
            mva = ((fechas >= w) & (fechas < fin)).values
            if mva.sum() < 200 or mtr.sum() < 1000:
                continue
            sc = StandardScaler().fit(X[mtr])
            mod = _ens().fit(sc.transform(X[mtr]), y[mtr])
            p = mod.predict_proba(sc.transform(X[mva]))[:, list(mod.classes_).index(1)]
            accs.append(accuracy_score(y[mva], (p >= 0.5).astype(int)))
            lls.append(log_loss(y[mva], np.column_stack([1 - p, p]), labels=[0, 1]))
            # subconjunto de INICIO de temporada (abril-mayo), donde el
            # decaimiento debería notarse más
            temprano = mva & (fechas.dt.month <= 5).values
            if temprano.sum() > 100:
                pt = mod.predict_proba(sc.transform(X[temprano]))[:, list(mod.classes_).index(1)]
                accs_ini.append(accuracy_score(y[temprano], (pt >= 0.5).astype(int)))
        res['con' if shrink else 'sin'] = {
            'acc': round(float(np.mean(accs)), 4),
            'll': round(float(np.mean(lls)), 4),
            'acc_inicio_temporada': round(float(np.mean(accs_ini)), 4) if accs_ini else None}
        logger.info(f"  shrink={shrink}: {res['con' if shrink else 'sin']}")
    a, b = res['sin'], res['con']
    res['adoptar'] = bool((b['acc'] - a['acc'] >= 0.003 and b['ll'] - a['ll'] <= 0.01)
                          or (b['acc'] > a['acc'] and b['ll'] < a['ll']))
    with open('resultados_shrinkage_v31.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=2)
    logger.info(f"[shrinkage MLB] {'ADOPTAR' if res['adoptar'] else 'descartado'}")
    return res


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
