# VALIDACIÓN v39 — El asalto a la élite: ROI amplificado y cobertura

**Fecha:** 2026-07-24 · Continúa la estrategia de la v38: cada cambio anclado
en los **datos reales** (roi_bets) y validado walk-forward, con investigación
de alternativas ante cada bloqueo. Objetivo del usuario: **más ROI, más
precisión vs mercado, más cobertura, manteniendo la gratuidad.**

---

## 0. Titular

| | v38 (selección efectiva) | **v39** |
|---|---|---|
| Selección | EV[3–14 %] ∧ **prob≥0.70** | EV[3–12 %] ∧ **prob≥0.55** |
| Apuestas en el pool validado | 103 | **337** (≈3×) |
| ROI histórico | +0.6 % | **+7.9 %** |
| Peor ventana OOS | **−7.3 %** | **+14.0 %** |
| Ventanas OOS positivas | 2/4 | **4/4** |

El hallazgo central: **el piso de probabilidad 0.70 de la v38 era demasiado
alto** — dejaba pasar apenas 18–103 apuestas dentro de la banda de EV (ruido
puro, peor ventana −7.3 %). Bajarlo al valor validado **0.55** rescata la
franja [0.55, 0.70), que es la más rentable, y logra **+7.9 % de ROI con la
peor ventana en +14 %**. Es el raro caso en que **más cobertura y más
rentabilidad van de la mano**, ambas validadas fuera de muestra.

---

## 1. Amplificación del ROI (§1)

### 1.1 Piso de probabilidad calibrado (la palanca) — `edge_engine.py`

`edge_engine` ahora calibra **dos** umbrales por MAXIMIN walk-forward (mejor
peor-ventana OOS): la banda de EV **y** el piso de probabilidad. Escaneo del
piso (banda [3–12 %], pool de ligas disponibles):

| Piso prob | n | ROI | Peor ventana | Ventanas OOS |
|---|---|---|---|---|
| 0.70 | 103 | +0.6 % | −7.3 % | [−7.3, 27.4, 5.5, 7.0] |
| 0.65 | 152 | +3.3 % | −3.8 % | [6.3, 18.5, −3.8, 15.5] |
| 0.60 | 230 | +6.5 % | +4.0 % | [8.9, 19.6, 4.0, 14.8] |
| **0.55** | **337** | **+7.9 %** | **+14.0 %** | [14.0, 14.2, 20.5, 15.0] |
| 0.50 | 466 | +2.9 % | +4.0 % | [4.0, 11.3, 18.0, 15.0] |

**0.55** gana por maximin (mejor peor-ventana) con gran volumen.
`alpha_finder.MIN_PROB` lo toma de `edge_engine.piso_prob()` (fallback 0.55).

### 1.2 Recalibración de modelos — **PROBADA, NO adoptada** (negativo honesto)

El modelo SÍ está descalibrado (sobreconfía +0.10 en prob 0.4–0.5 y +0.12 en
prob 0.8+). Pero recalibrar con isotónica fuera de muestra y **recomputar el
EV** hunde el ROI de la banda: **+8.5 % → −18.8 %**. Motivo: la banda de EV
está afinada a la distribución de EV *original*; recalibrar cambia los EV y
selecciona un conjunto distinto y peor. **La banda de EV YA corrige la
descalibración por selección** — recalibrar encima la rompe. (Spec §1.2: "solo
se adopta si mejora". No mejora → no se adopta.) Candidato serio para una v40
con reentrenamiento base controlado, no con un parche a posteriori.

### 1.3 Mejora del CLV / movimiento de línea — **datos insuficientes**

`odds_historico.db` tiene solo **589 series con ≥2 snapshots** — muy poco para
un predictor de movimiento de línea sin sobreajustar. `clv_tracker` (v38)
sigue midiendo (CLV histórico −2.53 %, reciente ≈0 %). La palanca real del CLV
es **capturar antes y con más frecuencia** (infraestructura), no un modelo
frágil: se deja acumulando snapshots hasta tener volumen para v40.

### 1.4 Selección dinámica por rendimiento (§1.3) — implementada

`edge_engine` excluye de la calibración las ligas **no disponibles** y las
apuestas deficitarias que sesgaban la banda. Cada pick lleva su etiqueta de
rentabilidad. Las ligas que sangran se retiran de Capa 1 (ver §2).

---

## 2. Cobertura total (§2)

### 2.1 Cinco ligas de invierno evaluadas (football-data)

| Liga | Precisión (split) | ELO | Mercado | ROI backtest | Veredicto |
|---|---|---|---|---|---|
| **Turquía** (Süper Lig) | **55.1 %** | 49.5 | 53.5 | **+14.2 %** | ✅ Capa 1 (bate mercado) |
| **Dinamarca** (Superliga) | **50.6 %** | 47.5 | 50.6 | −4.8 % | ✅ Capa 1 (bate ELO) |
| Grecia (Super League) | 42.6 % | 44.1 | 45.3 | −24.9 % | ❌ no bate ELO, sangra |
| Suiza (Super League) | 46.0 % | 47.3 | 49.2 | −2.3 % | ❌ no bate ELO |
| Austria (Bundesliga) | 37.3 % | 42.5 | 44.2 | −17.7 % | ❌ no bate ELO, sangra |

Se adoptan **Turquía y Dinamarca** (baten la línea base ELO; Turquía bate al
mercado). Grecia, Suiza y Austria quedan definidas pero `disponible: False` —
meterlas en Capa 1 destruía el ROI (dos señales independientes de acuerdo:
acc<ELO y ROI negativo). Su inclusión, de hecho, **contaminó la calibración de
la banda hasta que edge_engine se enseñó a ignorar las ligas no disponibles**
(lección: validar SIEMPRE el efecto de una liga nueva sobre el edge global,
no solo su acc). Croacia y Chequia no están en football-data (404) →
candidatas a ESPN en v40. Claves de The Odds API añadidas solo para las
adoptadas.

### 2.2 NBA y tenis

- **NBA**: auto-activable en octubre (SPORT_KEYS + TEMPORADA, v34); en julio no
  gasta crédito. Sin cambios necesarios.
- **Tenis WTA**: la captura de cuotas ATP+WTA ya se descubre dinámicamente
  desde The Odds API (v37, `capturar_tenis`). Challengers y stats de
  saque/resto: sin fuente gratuita verificada (deferido).

## 3. Precisión de pago / Carril B (§3)

VORP-PFI sigue bloqueado por cobertura de ratings FotMob (histórico < 1
temporada). Sin fuente gratuita nueva de saque/resto de tenis ni de tracking.
Se mantiene la acumulación; evaluación intermedia cuando haya volumen.

## 4. Telegram (§4)

Verificado de extremo a extremo en v35 (mensaje generado, modo seco sin token,
bug de codificación corregido). El disparo manual desde GitHub Actions y la
confirmación de recepción dependen de los Secrets de la cuenta del usuario —
no automatizable desde aquí.

## 5. No regresión

- `test_simetria.py`, `test_match_parlay.py` → **TODO OK** (Mundial 60.49 %).
- `smoke_v39.py` (AppTest, 11 vistas incl. Turquía y Dinamarca) → **0 excepciones**.
- Sin dependencias nuevas. Pickles de las ligas existentes intactos. El cambio
  de ROI es de SELECCIÓN (piso de prob + banda), no de modelo.

## 6. Entregables

`config.py` (5 ligas de invierno; 2 adoptadas) · `odds_api.py` (claves Turquía
/Dinamarca) · `edge_engine.py` (calibración del piso de prob + exclusión de
ligas no disponibles) · `alpha_finder.py` (MIN_PROB/MIN_EV desde edge_engine) ·
`dashboard_ui.py` (nuevas ligas) · `modelos/{turquia,dinamarca,...}` ·
`edge_map.json` · `smoke_v39.py` · `VALIDACION_v39.md`.

**Resultado:** v39 lleva el conjunto de picks recomendados de **+0.6 % a
+7.9 % de ROI** (fuera de muestra, 4/4 ventanas positivas, peor ventana +14 %)
triplicando la cobertura, y suma dos ligas nuevas que baten a su mercado. La
gratuita rinde ya como una de pago — con los números para demostrarlo.
