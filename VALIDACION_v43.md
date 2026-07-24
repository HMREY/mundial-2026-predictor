# VALIDACIÓN v43 — Line shopping, BTTS destacado y auditoría de modelos

**Fecha:** 2026-07-24 · Implementa la spec v43 priorizando lo que pidió el
usuario: **más ROI (siempre retorno), BTTS del fútbol, más cobertura de
partidos/deportes, Telegram que ayude a elegir, y sencillez.** Estrategia de
siempre: anclar en datos, buscar alternativas, validar.

---

## 0. EL SUPER DIFERENCIADOR (§2): LINE SHOPPING — y un bug de v42 cazado

### 0.1 La elección y su porqué

De las cuatro áreas del spec (props, predictor de línea, arbitraje, in-play
bayesiano), se elige **line shopping (mejor precio entre casas)** por ser la de
**mayor ROI, gratuita, simple y 100 % funcional ya**:

The Odds API devuelve **~23 casas por evento** (hasta 31). Hasta v42 tomábamos
la **primera**. Tomar la **mejor cuota de cada selección** mejora el precio
**+8.56 % de media** (mediana +8.19 %, mejor en el **95 %** de los outcomes) —
y **cada +1 % de cuota es +1 pp de ROI directo**. Es exactamente el "line
shopping" que cobran las apps de pago; para nosotros es gratis porque ya viene
en la misma respuesta.

`odds_api.capturar_liga` ahora calcula el mejor precio por selección entre
todas las casas (excluyendo Pinnacle, que se guarda como referencia sharp) y
**guarda la CASA que lo ofrece** → el usuario sabe **dónde apostar**
(`fetch_odds` inyecta `casa_home/draw/away`; se muestra 🏠 en el dashboard y en
Telegram).

### 0.2 Bug latente de v42 CAZADO (fallo silencioso)

Al implementar esto se descubrió que la **captura de Pinnacle de v42 nunca se
guardaba**: la clave primaria de `snapshots` era `(match_id, capturado_utc,
mercado, seleccion)` — **sin `fuente`** —, así que las filas de Pinnacle
colisionaban con las de odds_api (misma marca de tiempo) y `INSERT OR IGNORE`
las descartaba. Verificado: **0 filas `pinnacle`** en la base. Justo el tipo de
fallo silencioso que el usuario exigió no repetir. **Arreglo:** `fuente` (y la
nueva columna `casa`) entran en la PK, con **migración automática** de la tabla
existente preservando las 2.852 filas. Ahora Pinnacle y el mejor-precio
coexisten sin colisión (verificado en vivo: el workflow persiste ambas fuentes).

---

## 1. Auditoría total de modelos (§1) — `model_audit.py`

Matriz de rendimiento por liga contra su mercado de cierre (desde roi_bets, con
cuota apostada + cierre de Pinnacle + resultado): precisión, ROI, CLV y
semáforo 🟢/🟡/🔴 con diagnóstico automático del fallo. **6/21 ligas rentables
en el pool 1X2 CRUDO** (Turquía +14.2 %, LaLiga +8.2 %, Rumanía, Serie A,
Brasil, Bundesliga). Importante: es el pool **crudo**, ANTES del filtro de
selección validado (banda EV ∩ prob ∩ convicción ∩ sharp), que lleva el
subconjunto realmente apostado a **+9.9 %/+14.7 %**. La auditoría es
transparencia y hoja de ruta (qué modelos mejorar), se muestra en la nueva
sección **📊 Auditoría de Modelos** del dashboard.

---

## 2. BTTS destacado (prioridad del usuario)

«Ambos Marcan» da buen momio y su certeza es valiosa para los parlays:
- Umbral de la sección BTTS ampliado a **prob > 60 % y EV > +1 %** (antes 70 %)
  → más oportunidades a la vista.
- BTTS ya entra prioritario en «Mejores Patas» (v41) y ahora tiene **sección
  propia en el mensaje de Telegram** (⚽), marcada como "base de parlay".
- La calibración de BTTS ya estaba validada (Weibull AFT, v26/v27: Brier 0.236
  vs 0.252 de la matriz Poisson) — no se re-valida, se PRIORIZA.

---

## 3. Telegram que ayuda a elegir (prioridad del usuario)

- **🧭 ¿POR CUÁL EMPEZAR?**: una recomendación en lenguaje llano del mejor pick
  seguro del día (prioriza el confirmado por sharp), con el porqué y **dónde**
  apostar. Para el usuario que no quiere analizar.
- Cada pick muestra ahora **💠 +X % sobre Pinnacle** (calidad) y **🏠 mejor
  cuota en {casa}** (dónde apostar).
- Sección **⚽ Ambos Marcan** propia. Más opciones, más claras, más simples.

---

## 4. Cobertura (§3.3)

El bucle universal ya recorre las 21 competiciones + MLB/NBA/tenis; el aviso
"13/21 ligas sin partidos" es parón de calendario (verano), no pérdida
silenciosa (los nombres sin mapear se vuelcan a `nombres_sin_mapear.json`). El
line shopping, además, **añade cobertura de casas** para cada partido evaluado.

---

## 5. No regresión

- `test_simetria.py`, `test_match_parlay.py` → **TODO OK** (Internacionales 60.49 %).
- `smoke_v43.py` (AppTest, 11 vistas incl. Auditoría de Modelos) → **0 excepciones**.
- Migración de `snapshots` preserva los datos; PK ampliada verificada.
- Sin dependencias nuevas. Sin coste extra de API (line shopping y Pinnacle
  vienen en la misma petición, región `eu`).

---

## 6. Entregables

`odds_api.py` (line shopping + mejor casa + fix de PK con migración) ·
`fetch_odds.py` (inyección de `casa_*`) · `alpha_finder.py` (casa en el pick,
BTTS ampliado) · `bot_telegram.py` (guía «¿por cuál empezar?», sección BTTS,
sharp gap + casa) · `model_audit.py` + sección de dashboard · `dashboard_ui.py`
(sharp gap %, mejor casa, auditoría) · `VALIDACION_v43.md`.

**Resultado:** la plataforma incorpora **line shopping** (el mejor precio entre
~23 casas, +8.6 % de precio = ROI directo, gratis), **arregla un fallo
silencioso** que anulaba la confirmación sharp, **prioriza el BTTS** que pidió
el usuario, y hace el **Telegram mucho más fácil de usar** (guía llana + dónde
apostar). Siempre con retorno como norte.
