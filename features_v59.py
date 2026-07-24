#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Features v59 — DOMINIO TERRITORIAL y EFICIENCIA REMATADORA.

Hallazgo de la auditoría v59: football-data.co.uk ya nos da, en las ligas de
formato 'main', los CÓRNERS (HC/AC) y el VOLUMEN TOTAL de remates (HS/AS), y el
modelo NO los usaba — solo remates a puerta (HST/AST). Son señales tácticas
distintas y disponibles a coste cero (ya se descargan):

  · CÓRNERS a favor / en contra → presión territorial sostenida. Un equipo que
    genera muchos córners empuja al rival a su área aunque no remate a puerta.
  · VOLUMEN de remates (a puerta + fuera) → intención ofensiva total; separa al
    equipo que crea mucho y falla del que crea poco y acierta.
  · CONVERSIÓN (goles / remates a puerta) → eficiencia rematadora. Regresa a la
    media, así que una conversión muy alta reciente suele anticipar caída.

Todas las ventanas son ROLLING de 5 partidos y se calculan con el estado
ANTERIOR al partido (pase cronológico) → sin fuga de información.

Se adoptan SOLO en las ligas donde el walk-forward demuestre mejora (regla de
oro del proyecto). El grupo se activa con `features_extra: ['ck']`.
"""

import logging
from collections import defaultdict, deque
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

COLS_CK = ['DIFF_CK_MA5', 'DIFF_CKC_MA5', 'DIFF_SHOTS_MA5', 'DIFF_CONV_MA5']
N_VENTANA = 5


def _media(v: List[float], defecto: float) -> float:
    return float(np.mean(v)) if len(v) else defecto


def features_ck(df: pd.DataFrame):
    """(DataFrame por MATCH_ID con COLS_CK, estado final serializable).

    Devuelve NaN-free: si una liga no trae córners/remates (formato 'new'), las
    columnas salen a 0 y el grupo simplemente no aporta señal (no rompe)."""
    ck_f: Dict[str, deque] = defaultdict(lambda: deque(maxlen=N_VENTANA))
    ck_c: Dict[str, deque] = defaultdict(lambda: deque(maxlen=N_VENTANA))
    sh_f: Dict[str, deque] = defaultdict(lambda: deque(maxlen=N_VENTANA))
    gol_f: Dict[str, deque] = defaultdict(lambda: deque(maxlen=N_VENTANA))
    sot_f: Dict[str, deque] = defaultdict(lambda: deque(maxlen=N_VENTANA))

    tiene_ck = 'home_corners' in df.columns
    tiene_sh = 'home_shots_off' in df.columns and 'home_shots_on' in df.columns

    filas = []
    for f in df.itertuples(index=False):
        h, a = f.home_team, f.away_team

        def _lado(eq):
            conv_sot = _media(list(sot_f[eq]), 3.5)
            conv = (_media(list(gol_f[eq]), 1.2) / conv_sot) if conv_sot > 0 else 0.3
            return {
                'ck': _media(list(ck_f[eq]), 5.0),
                'ckc': _media(list(ck_c[eq]), 5.0),
                'sh': _media(list(sh_f[eq]), 12.0),
                'conv': float(np.clip(conv, 0.0, 1.0)),
            }

        lh, la = _lado(h), _lado(a)
        filas.append({
            'MATCH_ID': f.MATCH_ID,
            # normalizados a rangos ~[-1,1] como el resto de features del modelo
            'DIFF_CK_MA5': float(np.clip((lh['ck'] - la['ck']) / 4.0, -1, 1)),
            'DIFF_CKC_MA5': float(np.clip((lh['ckc'] - la['ckc']) / 4.0, -1, 1)),
            'DIFF_SHOTS_MA5': float(np.clip((lh['sh'] - la['sh']) / 8.0, -1, 1)),
            'DIFF_CONV_MA5': float(np.clip((lh['conv'] - la['conv']) / 0.3, -1, 1)),
        })

        # ---- actualización del estado (después de registrar la fila) ----
        if tiene_ck:
            hc = float(getattr(f, 'home_corners', np.nan) or 0)
            ac = float(getattr(f, 'away_corners', np.nan) or 0)
            if np.isfinite(hc) and np.isfinite(ac):
                ck_f[h].append(hc); ck_c[h].append(ac)
                ck_f[a].append(ac); ck_c[a].append(hc)
        if tiene_sh:
            for eq, on, off in ((h, getattr(f, 'home_shots_on', np.nan),
                                 getattr(f, 'home_shots_off', np.nan)),
                                (a, getattr(f, 'away_shots_on', np.nan),
                                 getattr(f, 'away_shots_off', np.nan))):
                on = float(on or 0); off = float(off or 0)
                if np.isfinite(on) and np.isfinite(off):
                    sh_f[eq].append(max(on + off, 0.0))
                if np.isfinite(on):
                    sot_f[eq].append(max(on, 0.0))
        gol_f[h].append(float(f.home_goals))
        gol_f[a].append(float(f.away_goals))

    estado = {eq: {'ck': list(ck_f[eq]), 'ckc': list(ck_c[eq]),
                   'sh': list(sh_f[eq]), 'sot': list(sot_f[eq]),
                   'gol': list(gol_f[eq])}
              for eq in set(list(ck_f) + list(gol_f))}
    return pd.DataFrame(filas).set_index('MATCH_ID'), estado


def vector_ck(estado: Dict, home: str, away: str) -> Dict[str, float]:
    """Reproduce las features en INFERENCIA desde el estado guardado."""
    def _lado(eq):
        e = (estado or {}).get(eq, {})
        sot = _media(e.get('sot', []), 3.5)
        conv = (_media(e.get('gol', []), 1.2) / sot) if sot > 0 else 0.3
        return {'ck': _media(e.get('ck', []), 5.0),
                'ckc': _media(e.get('ckc', []), 5.0),
                'sh': _media(e.get('sh', []), 12.0),
                'conv': float(np.clip(conv, 0.0, 1.0))}
    lh, la = _lado(home), _lado(away)
    return {
        'DIFF_CK_MA5': float(np.clip((lh['ck'] - la['ck']) / 4.0, -1, 1)),
        'DIFF_CKC_MA5': float(np.clip((lh['ckc'] - la['ckc']) / 4.0, -1, 1)),
        'DIFF_SHOTS_MA5': float(np.clip((lh['sh'] - la['sh']) / 8.0, -1, 1)),
        'DIFF_CONV_MA5': float(np.clip((lh['conv'] - la['conv']) / 0.3, -1, 1)),
    }
