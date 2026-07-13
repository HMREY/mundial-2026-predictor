# VALIDACIÓN v18 — Serie A recuperada, Liga MX con cuotas, EV en la UI (2026-07-13)

Regla de oro: adoptar solo con ≥ +0.3 pp de precisión sin empeorar log-loss
> 0.01 (o mejora en ambas / mejor calibración >70 %), confirmado en
walk-forward. Fuentes gratuitas y reproducibles en Streamlit Cloud.

---

## M1 — Serie A: recuperar la ganancia de las cuotas sin degradar log-loss ✅

Problema v17: cuotas de cierre daban +4.4 pp pero log-loss +0.015 (>0.01) —
no adoptado. Estrategias probadas en walk-forward (mismas ventanas v17):

| Estrategia | Acc | Log-loss | vs baseline 49.0 % / 1.047 | Veredicto |
|---|---|---|---|---|
| **Beta calibration** (cuotas + ensemble sin isotónica + beta one-vs-rest sobre el último 20 % del train) | 52.2 % | **0.998** | **+3.2 pp / −0.049** | ✅ ADOPTADA |
| Blend meta 50/50 (base + cuotas) | 52.6 % | 1.012 | +3.6 pp / −0.035 | pasa, pero peor log-loss que beta |
| Cuotas + isotónica (referencia v17) | 53.4 % | 1.062 | +4.4 pp / +0.015 | falla ll |
| Gate por overround < 0.05 | 49.0 % | 1.049 | sin efecto | descartada |

Con dos estrategias sobre el umbral, se eligió la de mejor log-loss (regla de
la especificación): **beta calibration**. Diagnóstico: la isotónica (a
escalones, cv=3 no cronológico) sobreajusta cuando las features de cuotas
concentran la señal; la beta (paramétrica, 2 grados de libertad por clase,
calibrada en el tramo final del train) generaliza mejor.

Implementación: `league_engine.ModeloBetaCalibrado` (picklea limpio — clase a
nivel de módulo) + `LEAGUES['serie_a']['calibracion']='beta'` +
`features_extra=['cuotas']`.

## M2 — Liga MX: cuotas de cierre desbloqueadas sin scraping ✅/📋

**Hallazgo**: `MEX.csv` de football-data SIEMPRE tuvo cuotas de cierre
(`AvgCH/AvgCD/AvgCA`, cobertura 100 % en 4,655 filas) — el parser v12 leía
las columnas de APERTURA (`AvgH/PH`), inexistentes en el formato 'new'. Con
el fix (cadena AvgCH→PSCH→B365CH→AvgH→PH), Liga MX gana además su línea base
de mercado, pendiente desde v12. Betexplorer (plan B de la especificación)
resultó innecesario: su HTML estático no sirve resultados históricos (JS).

Experimentos walk-forward (cuotas, features MX: altitud de sede/diferencia
con la altitud habitual del visitante, liguilla, apertura-clausura):

| Candidato | Acc WF | Log-loss WF | vs baseline 49.0 % / 1.038 | Veredicto |
|---|---|---|---|---|
| **cuotas de cierre** | 50.7 % | **1.010** | **+1.7 pp / −0.028** | ✅ ADOPTADO |
| cuotas + features MX | 52.0 % | 1.033 | +3.0 pp / −0.005 | pasa, pero peor log-loss que cuotas solas — mismo desempate que Serie A; candidato v19 |
| features MX solas (altitud/liguilla/clausura) | 49.1 % | 1.031 | +0.1 pp | ✗ bajo umbral |

Además, con el fix del parser la Liga MX reporta por primera vez su línea
base de mercado: favorito del cierre 53.5 % — el modelo (51.1 % en split)
aún no lo bate, y así se muestra con transparencia en la UI.

**Cuotas MX en vivo**: fixtures.csv no cubre México, así que sin más fuente
la feature quedaría siempre imputada a la media en producción. Se añadió
`betexplorer_scraper.cuotas_clubes_hoy()`: la página diaria de Betexplorer
lista los partidos del día (Liga MX incluida) con cuotas; se emparejan
contra `team_stats_{liga}.json` (fuzzy, cutoff 0.85) y alimentan
`odds_actuales.json` en cada corrida de `fetch_odds`. En días de jornada MX
las predicciones usan cuotas reales del día.

**Flashscore para posesión/tiros MX**: descartado — el HTML de Flashscore se
renderiza por JavaScript (verificado en v14); el supuesto de la
especificación ("HTML estático") no se cumple desde esta red.

## M3 — Cuotas reales + EV en la UI ✅ (funcional, sin backtesting)

- Nueva sección "💰 Cuotas reales y valor (EV)" en la plantilla del Mundial y
  de las 8 ligas: mercado, probabilidad del modelo, cuota real (decimal y
  americana), EV % e indicador 🟢 (>+5 %) / 🟡 (0-5 %) / ⚪ (≈0) / 🔴 (<0).
- Fuente: `odds_actuales.json` (fixtures.csv a diario en temporada;
  Betexplorer para el Mundial en días de partido). Sin cuota → "N/D" con
  explicación. El emparejamiento por mercado reutiliza el mapeo de
  `match_parlay` (1X2 y over/under 2.5, que es lo que publican las fuentes
  gratuitas).
- El asistente de parlay ya calculaba EV real desde v15; el aviso "EV
  teórico — no accionable" se mantiene cuando no hay cuotas.

## M4 — Alineaciones confirmadas 📋 POSPUESTA (igual que v17)

Sin cambios en los hechos: no existen alineaciones históricas gratuitas
(backtest imposible sin inventar datos) y las páginas de partido de
Flashscore/LiveScore son JS desde esta red. Además el insumo clave de la
especificación (xG/90 por jugador) no es computable con Kaggle goalscorers
(trae minuto del gol, no minutos jugados). Queda para v19: recolectar
alineaciones EN VIVO durante la temporada 2026-27 y medir en producción,
como propone la propia especificación.

## Gestión de banca (Kelly) — visible en §1.2 de la especificación

No entró en el alcance ejecutado de v18 (la especificación la lista como
oportunidad, sin plan detallado en las mejoras 1-4). Candidata natural a
v19 junto con el EV ya expuesto en la UI.

## No-regresión

- Mundial intacto (60.4 % / 0.871) — ningún cambio toca su pipeline.
- Resto de ligas: sin cambios de diseño; Serie A y Liga MX reconstruidas con
  sus adopciones.
