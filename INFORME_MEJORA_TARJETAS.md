# 🎯 Informe de Mejora — Tarjetas, Árbitros y Remates de Jugadores

**Fecha:** 2026-07-03 · **Regla aplicada:** nada entra a producción si no mejora
(o al menos no empeora) el rendimiento validado del sistema.

## 1. Auditoría del modelo de tarjetas (Fase 1)

**Referencias reales utilizadas** (agregados oficiales de torneos, fuentes
FIFA/UEFA/CONMEBOL):

| Torneo | Tarjetas totales por partido |
|---|---|
| Mundial 2022 | 3.61 (227 amarillas + 4 rojas / 64 partidos) |
| Mundial 2018 | 3.48 |
| Euro 2024 | ~3.2 |
| Copa América 2024 | ~4.7 (atípicamente duro) |
| **Banda mundialista realista** | **3.2 – 4.7, centro 3.5-3.8** |

**Resultado de la auditoría del modelo v2** (equipos medios del sistema,
AMAR_MA5 = 1.72):

| Árbitro | v2 grupos | v2 eliminatoria |
|---|---|---|
| Oliver (permisivo, 3.2 p90) | 3.51 | 3.84 |
| Promedio FIFA (3.8) | 4.19 | 4.59 |
| Ramos (estricto, 4.1) | 4.52 | 4.95 |
| Valenzuela (muy estricto, 4.5) | 5.00 | 5.47 |

**Sesgo detectado: +0.65 tarjetas (+18 %) de sobrestimación sistemática.**
Causas estructurales: (a) los factores de fase (×1.05/×1.15) se apilaban sobre
el p90 del árbitro, que YA está medido en torneos competitivos (doble conteo);
(b) el bono de bloque alto y la desviación del equipo INFLABAN el ancla en vez
de repartirla; (c) faltaba el descuento mundialista documentado (~8 % menos
tarjetas que la media general del árbitro, por las directrices FIFA de fluidez).

**Sobre `referees.json`:** los p90 provienen de la tabla oficial
FIFA/WorldReferee 2022-2025 aportada por el analista — son la mejor fuente real
disponible; el problema no eran los datos del árbitro sino cómo el modelo los
combinaba. El scraping de actualización semanal (`referee_scraper.py`) sigue
activo para refrescarlos cuando el sitio responda.

## 2. Nuevo modelo de tarjetas v3 (Fase 2) — ADOPTADO

```
total esperado = AMA_P90_árbitro × 0.92 (mundialista) × fase (1.00 grupos / 1.10 KO)
                 × media(mod_local, mod_visitante)
mod_equipo     = (1 ± 5 % por amarilla MA5 vs 2.0) × (×1.08 si bloque alto)
reparto        = proporcional a los modificadores, con el sesgo local del
                 árbitro moviendo tarjetas del local al visitante SIN tocar el total
tope           = nunca más del p90 observado del árbitro + 15 % (Fase 5.9)
```

**Resultados v3 vs v2 vs realidad:**

| Árbitro | v2 grupos | **v3 grupos** | **v3 eliminatoria** |
|---|---|---|---|
| Oliver | 3.51 | **3.08** | 3.39 |
| Promedio FIFA | 4.19 | **3.67** | 4.04 |
| Ramos | 4.52 | **3.99** | 4.39 |
| Valenzuela | 5.00 | **4.38** | 4.82 |
| **Media grupos** | 4.30 | **3.78** ✅ | — |

La media queda en la banda real (3.5-3.8), el promedio FIFA reproduce casi
exactamente el Mundial 2022 (3.67 vs 3.61), la severidad relativa de cada
árbitro se preserva y el sesgo local sigue funcionando (Tello: 1.74 vs 2.13,
reparto ×0.9/×1.1 exacto, total intacto). Verificado por prueba automatizada.

## 3. Remates por jugador (Fase 3) — AÑADIDO A LA PLANTILLA

Nueva sección **"7b. Remates por Jugador (Top 4 de cada equipo)"** con, por
jugador: remates esperados, probabilidad de rematar (≥1), remates a puerta
esperados y probabilidad de rematar a puerta (≥1).

- **Fuente**: goleadores REALES de Kaggle (24 meses) + ratios calibrados con
  StatsBomb (remates↔xG); imputación con hash estable por MATCH_ID (misma
  metodología reproducible de la corrección anterior).
- **Consistencia con la Sección 8** (requisito 3.6): la cuota de cada jugador
  es su fracción del xG del equipo aplicada al volumen total de remates del
  partido; el top-4 nunca supera el 85 % del volumen del equipo (el resto es
  de la alineación restante). Verificado: ARG suma 12.64 de 16.68 remates.
- **Límites físicos** (Fase 5.9): ≤5.5 remates y ≤3.0 a puerta por jugador,
  y a-puerta ≤ remates. Ejemplo real: Messi 5.5 remates esperados (99.6 % de
  rematar), 1.85 a puerta.

## 4. Integración con el 1X2 (Fase 4) — NO SE AÑADEN FEATURES (decisión)

Las variables `suma_remates_top4` **no** entran al clasificador: no existe un
histórico por-partido de remates de jugadores (solo la foto de 24 meses), por
lo que cualquier feature sería estática/con fuga y NO puede validarse en
walk-forward. Por la regla de oro, quedan como información de plantilla sin
tocar las probabilidades. (Mismo criterio que en mejoras previas descartadas.)

## 5. Validación global (Fase 5)

- **El clasificador 1X2 no se tocó**: verificación bit a bit — EGY vs AUS
  devuelve exactamente las mismas probabilidades (0.388/0.253/0.359) antes y
  después de la mejora; `modelos/metadata.json` sin cambios.
- **Benchmark vigente**: walk-forward 59.5 % / log-loss 0.908 (sin retrain,
  variación 0.0 pp — dentro del ±0.3 exigido por definición).
- Coherencia de árbitros: ningún total supera su p90 observado +15 %.
- UI: la plantilla renderiza la nueva sección automáticamente; login y
  render completo verificados por AppTest.

## 6. Decisión final

| Cambio | Decisión |
|---|---|
| Modelo de tarjetas v3 anclado al árbitro (+descuento mundialista) | ✅ **Producción** (corrige +18 % de sesgo) |
| Tope p90+15 % por árbitro | ✅ Producción |
| Sección 7b: top-4 rematadores por equipo | ✅ Producción (solo plantilla) |
| Features de remates de jugadores en el 1X2 | ❌ Descartado (sin datos históricos leak-free para validar) |
| Reemplazo de la tabla de árbitros | ❌ No necesario (la tabla oficial 2022-25 es la mejor fuente; el sesgo era del modelo, no de los datos) |
| ZIP / Gradient Boosting para tarjetas | ❌ Descartado: nuestro histórico de tarjetas por partido es relleno calibrado (no real), entrenar un modelo de conteos sobre él sería circular; el ancla arbitral real es superior |
