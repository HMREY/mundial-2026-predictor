# VALIDACIÓN v37 — Rentabilidad, parlays inteligentes y explotación de correlaciones

**Fecha:** 2026-07-24 · Implementa la spec "PROMPT MAESTRO v36" (el usuario la
numera v37; se respeta su numeración). Cambio de paradigma: **de "no perder" a
"ganar sistemáticamente"** — el criterio rey pasa a ser la probabilidad real
de acertar (PFP), no el EV teórico.

---

## 0. Resumen ejecutivo

| § | Entregable | Estado |
|---|---|---|
| 1 | Explotación de correlaciones positivas (SGP+) | ✅ `senal_sgp_plus` + `construir_sgp_plus`, blindado contra EV+ ilusorio |
| 2 | PFP + umbral 45 % | ✅ se muestra siempre; bloquea solo en perfiles seguros |
| 3 | Mercados alternativos + perfil Super Seguro | ✅ lista blanca de alta probabilidad |
| 4 | Límite dinámico de patas por bankroll | ✅ 4→3→2→simple según capital |
| 5 | Plan de ataque temporal (oleadas) | ✅ Oleada 1/2/resto por fecha |
| 6 | Sección destacada BTTS | ✅ conf > 70 % + EV > 3 % |
| 7 | Informe mensual de rendimiento | ✅ `resumen_mensual.py` + UI |
| 8 | Props MLB / scraping de casas | ⚠️ **NO viable hoy** (sin feed gratuito de props) — documentado |

Validación núcleo: la matriz de correlación φ predice la frecuencia conjunta
real con **error 0.0028 fuera de muestra vs 0.0493 bajo independencia (94.3 %
mejor)** — la base empírica del SGP+.

---

## 1. §1 — SGP+ (correlaciones positivas asimétricas)

### 1.1 Diseño

Un SGP con dos patas positivamente correlacionadas (φ>0) tiene prob conjunta
REAL mayor que el producto. Las casas suelen preciar el SGP como *producto ×
recorte genérico* sin medir la correlación exacta de esa pareja. Cuando
nuestra φ empírica dice que la correlación es más fuerte que la que el recorte
genérico asume, el SGP está infravalorado.

- `sgp_correlation.factor_par` (TRUNCADO ≤1) sigue precificando parlays de
  forma conservadora (no se toca su prudencia).
- `sgp_correlation.factor_par_real` (SIN truncar) y `senal_sgp_plus`
  **detectan** el edge sin usarlo para inflar precios de parlays normales.
- `match_parlay.construir_sgp_plus` arma el mejor par de 2 patas del partido.

### 1.2 Blindaje contra EV+ ilusorio (lección crítica)

La primera versión producía señales absurdas: "Más de 5.5 goles" (2 %) + "Local
+2.5 goles" (8 %) con **EV +830 %**. Causa: con probabilidades extremas la
cópula gaussiana de primer orden dispara el factor (σσ/(pa·pb)→∞) — la misma
trampa que motivó el truncado en la v25. Correcciones aplicadas:

1. **Solo cuotas REALES de mercado** (con cuotas justas el EV degenera en un
   artefacto). `construir_sgp_plus` exige `cuota_fuente == 'real'`.
2. **Rango sano de probabilidad por pata** (0.20 ≤ p ≤ 0.92).
3. **Conjunta acotada** a `[pa·pb, min(pa,pb)]` (cota de Fréchet: una conjunta
   nunca supera la marginal más pequeña).
4. **φ ≥ 0.985 se descarta** (identidad: misma apuesta con otro nombre).

Tras el blindaje, las señales son creíbles: `BTTS Sí + Over 1.5` (φ=0.607)
→ conjunta 0.523 vs producto 0.385, EV **+9.5 %**; `Gana local + local marca 2+`
(φ=0.59) → EV **+27.5 %**.

### 1.3 Honestidad sobre la validación

**No existe feed gratuito de precios HISTÓRICOS de SGP**, así que no se puede
backtestear el ROI del SGP+ directamente. Lo que SÍ se valida
(`sgp_correlation.backtest`, fuera de muestra) es que φ predice la frecuencia
conjunta real: **error 0.0028 vs 0.0493 (independencia), 94.3 % mejor**. La
señal SGP+ es por tanto "esta pareja está correlacionada de forma que las
casas tienden a infrapreciar — búscala en tu libro". La UI lo dice explícito.

`parlay_builder.py` (multi-partido): los pares del MISMO partido ahora usan el
factor empírico φ en vez del haircut fijo 0.95, y se expone el PFP.

---

## 2. §2 — PFP (Parlay Force Point)

- `match_parlay` devuelve `pfp` (= prob conjunta real ajustada por correlación)
  y `cumple_pfp` en **todos** los parlays; la UI lo muestra destacado con
  semáforo ✅/⚠️.
- **Filtro del 45 %**: bloquea solo los perfiles cuya razón de ser es la
  seguridad (**Super Seguro, Conservador**). Elegir **Medio/Agresivo** ya es
  optar por el riesgo — son el "modo avanzado" del spec §2.2, donde el PFP se
  avisa pero no oculta. Así el headline de seguridad no rompe los perfiles de
  cuota alta (que por diseño tienen PFP<45 %).
- Apuestas simples (1 pata) exentas.

## 3. §3 — Mercados alternativos + perfil Super Seguro

Nuevo perfil `super_seguro`: prioriza la lista blanca `MERCADOS_ALTA_PROB`
(doble oportunidad, hándicap +0.5, BTTS, over 0.5/1.5) para maximizar el PFP.
Si no hay ≥2 mercados de alta prob, cae a la lista completa (no se queda sin
parlay). Es el perfil por defecto en la UI (coherente con el paradigma "ganar").

## 4. §4 — Límite dinámico de patas

`limite_patas_por_bankroll`: bankroll < 50 → máx 2 patas; < 150 → máx 3; resto
sin recorte. Verificado: con bankroll 40 y petición de 6 patas, el parlay se
limita a 2 con el aviso "tu bankroll favorece apuestas de menor riesgo". 100 %
stateless (solo `st.session_state`), sin base de datos de usuarios.

## 5. §5 — Oleadas temporales

`_oleadas` agrupa la Capa 1 por fecha: 🔴 Oleada 1 (hoy), 🟡 Oleada 2 (mañana),
📋 resto. La UI muestra el conteo y el mejor pick de cada oleada, con el aviso
"no inviertas más del 50 % del bankroll en una sola oleada".

## 6. §6 — Sección BTTS

`_seccion_btts`: picks de BTTS con confianza > 70 % y (si hay cuota real) EV >
+3 %. Aprovecha la calibración Weibull (v27). Sección propia en la UI.

## 7. §7 — Informe mensual

`resumen_mensual.py` sobre `rendimiento_real.db`: tasa de acierto, ROI real,
EV prometido vs. real, desglose por deporte y capa, serie mensual y bankroll
acumulado (stake plano de 1 u). Cero peticiones, cero estado nuevo. Hoy no hay
picks liquidados → lo dice con transparencia en vez de inventar cifras.

## 8. §8 — Props MLB y scraping de casas (investigación)

**Regla de Cero Bloqueos aplicada** — se investigó y se documenta el bloqueo:

- **The Odds API**: el endpoint de eventos de MLB responde 200, pero el mercado
  `pitcher_strikeouts` devuelve **0 casas** en el tier disponible (los player
  props exigen un plan de pago). Sin cuotas de props no hay EV computable.
- **`pybaseball`**: no instalado; aunque diera features históricas de ponches,
  **seguiría faltando el feed gratuito de cuotas de props** contra el que
  apostar → sin EV.
- **Conclusión (spec §8.1):** NO viable hoy. Alternativa propuesta: usar
  métricas agregadas del equipo (K/9 del abridor, ya en el motor MLB) como
  proxy analítico, sin apuesta directa hasta que aparezca una fuente gratuita.
- Scraping de casas (Playdoit/DraftKings): no necesario — The Odds API y
  Betexplorer cubren las ligas activas; queda como eslabón futuro de la cadena
  de resiliencia si una fuente principal cae.

---

## 9. No regresión

- `test_simetria.py` → **TODO OK** (Mundial 60.49 % intacto).
- `test_match_parlay.py` → **TODO OK** (actualizado: los perfiles seguros
  pueden avisar en vez de sugerir un parlay flojo).
- `smoke_v37.py` (AppTest, 9 vistas incl. Apuestas del Día con oleadas + BTTS +
  informe mensual) → **0 excepciones**.
- Sin dependencias nuevas. Los pickles no se tocaron.

## 10. Entregables

`sgp_correlation.py` (factor real + SGP+) · `match_parlay.py` (PFP, filtro
45 %, mercados alternativos, patas dinámicas, `construir_sgp_plus`) ·
`parlay_builder.py` (factor φ mismo-partido + PFP) · `alpha_finder.py`
(sección BTTS + oleadas) · `resumen_mensual.py` · `dashboard_ui.py` (perfil
Super Seguro, PFP destacado, SGP+, oleadas, BTTS, informe mensual) ·
`test_match_parlay.py` · `smoke_v37.py` · `VALIDACION_v37.md`.
