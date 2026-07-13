# VALIDACIÓN v19 — Liga MX reforzada, Kelly, cuotas AH y alineaciones sombra (2026-07-13)

Regla de oro: walk-forward obligatorio; ≥ +0.3 pp sin empeorar log-loss
> 0.01 (o mejora en ambas / mejor calibración >70 %). Fuentes gratuitas,
legales y reproducibles en Streamlit Cloud. El Mundial no se toca.

---

## 1. Liga MX — hacia el mercado

Baseline v18 (cuotas + isotónica): **50.7 % / 1.010** (mercado de cierre: 53.5 %).

| Candidato (walk-forward) | Acc | Log-loss | Veredicto |
|---|---|---|---|
| **cuotas + features MX + beta calibration** | **51.7 %** | 1.011 | ✅ ADOPTADO (+1.0 pp, Δll +0.0015 ≤ 0.01) |
| cuotas + beta | 51.3 % | 1.017 | pasa, pero peor que con features MX |
| cuotas + MX + extras + beta | 50.8 % | 1.012 | ✗ bajo umbral |
| Poisson puro + cuotas + beta | 50.2 % | 1.031 | ✗ descartado |

Features MX (`GEO_MX` en league_engine): altitud de la sede y diferencia con
la altitud habitual del visitante, distancia de viaje (haversine entre
sedes), liguilla (binaria por calendario) y apertura/clausura. Computables
al vuelo en inferencia (`_fila_mx`).

**Transparencia sobre los umbrales de la especificación**: la mejora pasa la
regla de oro general con claridad (+1.0 pp), pero se queda a 0.3 pp del
umbral aspiracional de 52.0 % del §1.1.1 en walk-forward (el split del
modelo desplegado sí lo supera: 52.4 % / 0.998) y el mercado (53.5 %) sigue
sin batirse. Se adopta el mejor modelo obtenido y se documenta, como prevé
el propio plan (§1.2.6).

## 2. Poisson puro para 1X2 — descartado con evidencia

| Liga | Poisson+beta WF | Modelo desplegado WF | Veredicto |
|---|---|---|---|
| Serie A | 49.0 % / 1.013 | 52.2 % / 0.998 | ✗ muy inferior |
| Bundesliga | 45.5 % / 1.054 | 50.3 % / 1.027 | ✗ muy inferior |
| Liga MX | 50.2 % / 1.031 | 51.7 % / 1.011 | ✗ inferior |

La hipótesis (§4: "el mercado eficiente favorece al Poisson") no se sostiene:
el ensemble de clasificación calibrado gana en las tres ligas probadas.

## 3. Gestión de banca — ¼ Kelly ✅ (funcional)

- `bankroll_manager.py`: `calcular_stake(prob, cuota, bankroll, fraccion=¼)`
  con **tope de seguridad del 5 % del bankroll** por apuesta (¼ Kelly puede
  sugerir fracciones enormes cuando el modelo cree tener mucha ventaja — el
  tope protege contra errores de calibración). Verificación numérica
  incluida en el módulo (p=0.55 @ 2.00 → Kelly pleno 10 %, ¼ = 2.5 %).
- UI: input "💵 Mi bankroll" en la barra lateral (default 1000), columna
  "Stake ¼ Kelly" en la tabla de EV (solo con EV > 0; '—' en el resto) y
  stake del parlay cuando tiene cuotas reales y EV positivo. Aviso de juego
  responsable siempre visible.

## 4. Ampliación de cobertura de cuotas

- **Hándicap asiático ±0.5** ✅: `fixtures.csv` de football-data trae la
  línea (`AHh`) y las cuotas B365 de ambos lados (`B365AHH/B365AHA`) — sin
  scraping. Se capturan en `odds_actuales.json` y se mapean a los campos de
  la plantilla SOLO cuando la línea es exactamente ±0.5 (que es lo que la
  plantilla publica); EV y Kelly funcionan igual que en el 1X2.
- **BTTS** 📋 POSPUESTO: ninguna fuente gratuita estructurada lo publica
  (fixtures.csv no trae columnas BTTS; scrapear Bet365 viola sus ToS y el
  requisito de legalidad del proyecto; Betexplorer solo lista 1X2 en su HTML
  estático). Documentado para v20.

## 5. Alineaciones confirmadas en MODO SOMBRA ✅

- Hallazgo que desbloquea lo que Flashscore impedía: **el JSON público de
  ESPN publica los rosters con el once titular** (posición incluida) vía el
  endpoint `summary` — la misma fuente sin clave que ya usamos para
  resultados en vivo. Cobertura: las 8 ligas + Mundial (códigos eng.1,
  esp.1, ita.1, ger.1, fra.1, ned.1, por.1, mex.1, fifa.world).
- `lineup_collector.py`: acumula titulares/suplentes por partido en
  `alineaciones_historicas.csv`, con dedupe por event_id y backfill
  (`--dias-atras N`). Integrado como paso de `pipeline_total.py`.
  **No toca las predicciones** (modo sombra).
- Verificado con datos reales: 4 partidos del Mundial (9-11 julio, 203
  filas; p. ej. Francia-Marruecos con los 11 titulares y posiciones).
- Evaluación del impacto: al cierre de la temporada 2026-27
  (VALIDACION_v20.md), cruzando con la base de jugadores.

## 6. No-regresión

- Mundial intacto (60.4 % / 0.871).
- Serie A, Premier, Bundesliga, LaLiga, Ligue 1, Eredivisie, Primeira: sin
  cambios (v18/v17).
- Liga MX desplegada: 52.4 % / 0.998 en split (v18: 51.1 / 1.003), con
  `ModeloBetaCalibrado` + 9 features extra.
- Tests: AppTest (Mundial/Serie A, ambos modos, parlays) y
  test_match_parlay en verde; cadena de cuotas corre sin errores (0 filas
  hoy por receso — comportamiento correcto).
