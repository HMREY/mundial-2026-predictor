# VALIDACIÓN v47 + v48

**Fecha:** 2026-07-24
**Objetivo:** resolver las quejas concretas del usuario (Capa 1 desaparecida,
tenis sin información, jerga "sobre Pinnacle", pocas opciones, refresco al
abrir, envío a Telegram) y ampliar cobertura de ligas con modelos REALES.

---

## v47 — UX y cobertura de mercados (todo probado end-to-end)

### 1. Tenis: 19 mercados derivados + Parlay del Día
- **Problema:** en tenis solo salía "Gana X SIN cuota real". El motor ya
  calculaba 19 mercados en `TennisEngine.plantilla()` (ganador, totales de
  juegos, hándicaps, sets 2-0/2-1, "ambos ganan un set") pero `_picks_tenis()`
  nunca los exponía.
- **Solución:** `_picks_tenis()` adjunta `mercados_tenis` a cada pick y alimenta
  `_construir_parlay_tenis()`, que arma una combinada con el mercado más seguro
  de cada partido (uno por evento → diversifica).
- **Verificado (barrido real 2026-07-24):**
  - Rublev A.: "gana al menos un set 91% · −2.5 juegos 88% · gana 77% · <26.5
    juegos 71% · −4.5 juegos 66%".
  - Parlay del Día (tenis): 4 patas, cuota combinada **1.94**, prob **52%**.
- Se muestra en dashboard (tabla expandible por partido + sección de parlay),
  Telegram y export TXT.

### 2. "Sobre Pinnacle" → lenguaje llano
- `traductor_quant.frase_sharp()` / `sello_sharp()`: en modo Principiante,
  "💠 +6% sobre Pinnacle (confirmado sharp)" pasa a
  **"🔥 apuesta más segura (respaldo profesional, +6% de valor)"**.
- En modo Pro se conserva la versión técnica (`+6 pp vs Pinnacle`).
- Aplicado en dashboard, Telegram y TXT.

### 3. La Capa 1 nunca queda vacía
- Nuevo `seleccion_dia`: si hoy ningún 1X2 con cuota real pasa los filtros de
  élite, se promueven las mejores oportunidades por convicción (prob×EV) con
  aviso honesto ("mejor valor del día, sin confirmación sharp, stake prudente").
- (El 2026-07-24 la Capa 1 tenía 2 picks reales, así que el fallback no se
  disparó — comportamiento correcto.)

### 4. Refresco automático al abrir
- En Streamlit Cloud el proceso se comparte entre visitantes y el caché de
  datos puede venir de otra sesión. En una sesión nueva se limpia el caché de
  datos una vez (`st.cache_data.clear()`), garantizando datos frescos al entrar.
  Se conserva el caché de modelos (`cache_resource`). Botón "🔄 Actualizar ahora"
  añadido para refresco manual.

### 5. Botón "Enviar a Telegram ahora"
- En Apuestas del Día: envía el resumen completo bajo demanda (además del envío
  diario por GitHub Actions). Sin credenciales, muestra vista previa.

---

## v48 — Nuevas ligas con modelos REALES (regla de oro §2.2)

Hallazgo: football-data.co.uk **sí** publica CHN/POL/SWZ en formato 'new'
(la nota de v34 era incorrecta para China). Entrenadas con el pipeline existente:

| Liga | Precisión | ELO base | Mercado | Veredicto |
|------|-----------|----------|---------|-----------|
| **China** (Chinese Super League) | **0.562** | 0.501 | 0.529 | ✅ bate mercado → Capa 1 · EN TEMPORADA |
| **Polonia** (Ekstraklasa) | **0.461** | 0.391 | 0.437 | ✅ bate mercado → Capa 1 · reanuda agosto |
| Suiza (Super League) | 0.460 | 0.473 | 0.492 | ❌ no bate ELO → `disponible: False` (informativa) |

- China cubre el hueco asiático del verano (último partido 18/07/2026).
- Claves de The Odds API añadidas para China y Polonia (Suiza excluida para no
  gastar créditos). Cuarentena de pretemporada (v32) degrada solas las ligas en
  parón hasta que reanuden.

---

## No regresión
- `test_simetria.py` → TODO OK
- `test_match_parlay.py` → TODO OK
- Smoke `dashboard_ui.py` (Apuestas del Día, Tenis ATP/WTA) → OK
- `bot_telegram.py --dry-run` (barrido universal completo) → OK
