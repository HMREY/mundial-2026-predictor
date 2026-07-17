# VALIDACIÓN v24 — FotMob, MLS y el Índice de Momentum Táctico

**Fecha:** 2026-07-17 · **Regla de oro:** walk-forward obligatorio; solo se
adopta lo que lo supera; lo que falla se documenta igual que lo que triunfa.

---

## 1. Investigación de fuentes (verificación empírica, no de fe)

### 1.1 Soccer24 — el supuesto del master prompt era FALSO

El master prompt v24 afirmaba que `https://www.soccer24.com/api/matches/{id}/statistics`
devuelve JSON con estadísticas defensivas. **Verificado 2026-07-17: ese
endpoint NO existe** (HTTP 404 con página de error genérica). Soccer24 es un
portal de la familia livesport/Flashscore: sus datos viajan por feeds
firmados (`d.soccer24.com/x/feed/...` + header `x-fsign`); la firma pública
histórica devuelve "0" (rechazo) y la vigente no aparece en los bundles JS
públicos — se genera en cliente (JS pesado, el mismo motivo por el que
Flashscore se descartó en v14). `soccer24_scraper.py` queda como constancia
del sondeo con un `sondear()` re-ejecutable. **Descartado.**

### 1.2 FotMob — inviable por API, ORO por __NEXT_DATA__

La API interna (`www.fotmob.com/api/*`) está blindada con el header firmado
`x-mas` (404/403 con requests planos). **PERO** las páginas Next.js incrustan
el JSON completo en `<script id="__NEXT_DATA__">` y responden HTTP 200 a un
requests con User-Agent normal:

| Página | Contenido verificado |
|---|---|
| `/leagues/{id}/overview/{slug}` | tabla, temporadas, TODOS los partidos de la temporada con id (~510 en MLS), líderes |
| `/match/{id}` | **xG REAL por equipo**, remates totales/a puerta, **defensivas (entradas, intercepciones, despejes, paradas)**, **shotmap por JUGADOR con xG por tiro**, ratings, alineaciones, clima, momentum |

Con esto FotMob cubre TAMBIÉN lo que se esperaba de Soccer24 (defensivas) y
lo que el MAT v23 no tenía (remates por jugador-partido reales).
`fotmob_scraper.py` implementa el patrón incremental del proyecto (caché
compacta commiteable en `fotmob_cache/`, ~3 KB por partido vs ~1 MB de
página; consolidación en `historico_fotmob_{liga}.csv`; paso nuevo en
`pipeline_total.py` con `max_partidos=15` por corrida).

**Limitación honesta:** la cobertura histórica arranca en cero (semilla
inicial: 26 partidos MLS + 2 Liga MX; Europa está en pretemporada). Las
features de FotMob (ratings, defensivas reales, remates por jugador para el
MAT individual) NO son backtesteables aún — se adoptarán cuando la cobertura
acumulada permita validarlas en walk-forward (mismo protocolo que el clima
v23, que con 14 % de cobertura no aportó y se dejó acumulando).

### 1.3 MLS — resuelta con football-data.co.uk (mejor que el plan)

El master prompt proponía FBref + Playwright para la MLS. Innecesario:
`https://www.football-data.co.uk/new/USA.csv` (verificado 2026-07-17) trae
**6,034 partidos desde 2012 con cuotas de CIERRE** (AvgC*/PSC*/B365C*, misma
cadena de parsing que MEX.csv), estable y accesible desde Streamlit Cloud.
FBref sigue en 403 (verificado en v22) y Playwright no corre en el cloud.

## 2. MLS operativa (liga nueva)

- `config.LEAGUES['mls']`: formato 'new', ventana 8 años, features
  `['cuotas']` — igual que el arranque de cualquier liga del proyecto.
- Split 80/20: **47.2 %** (ELO 44.7, mercado 50.1), log-loss 1.041.
- **MESM adoptado en el primer entrenamiento: 47.2 → 50.0 %** (ll 1.038) —
  la MLS empata al mercado desde el día uno vía meta-ensemble.
- Selector del dashboard: 🇺🇸 MLS.
- Walk-forward completo en §3 (arnés IMT, variante `base`).

## 3. Índice de Momentum Táctico (IMT)

### 3.1 Implementación (`momentum_tactico.py`)

IMT_i(t) = α·M(t) + β·ΔxG(t) + γ·F(t) + δ·P(t), con:

- **M(t)**: media exponencial (λ=0.7) de los últimos 8 resultados (V=1/E=0.5/D=0).
- **ΔxG(t)**: xG medio de los últimos 3 menos el de los 5 anteriores.
- **F(t)**: fatiga por congestión del equipo — `1 − min(partidos en 14 días/4, 1)`.
  Los minutos de los 3 jugadores clave NO existen gratis a escala histórica
  (limitación ya documentada en el MAT v23); se usa el proxy validable.
- **P(t)**: CON SIGNO (+1 ganar por 4+, −1 perder por 4+, 0 resto). La
  "remontada en los últimos 10 minutos" exige minuto a minuto que las
  fuentes de clubes no publican — fuera, documentado.

Decisión de diseño: las 4 componentes entran como features separadas
(variante `imt`) — el ensemble aprende α,β,γ,δ y sus interacciones, que
generaliza estrictamente al índice lineal — Y ADEMÁS se prueba el índice
compuesto (variante `imt_c`) con α,β,γ,δ ajustados por mínimos cuadrados
contra la diferencia de goles SOLO con el train de cada ventana (spec §3.2,
sin fuga). La regla de oro decide entre `base`, `imt` e `imt_c` por liga.

Sanidad verificada: sin NaN, rangos [−1,1], **invariancia al truncar el
futuro (sin fuga, diff exacta 0.0)**, round-trip de inferencia con el estado
serializado, correlación del índice lineal con la diferencia de goles ≈ 0.18
(Liga MX, train-only).

### 3.2 Walk-forward por liga (run_wf_imt_v24.py, ventanas de 6 meses)

Precisión media / log-loss medio por variante (mismas ventanas para las tres):

| Liga | base | imt (componentes) | imt_c (índice) | Decisión |
|---|---|---|---|---|
| Liga MX | 50.46 / 1.0240 | 50.33 / 1.0238 | **50.84 / 1.0253** | **ADOPTAR imt_c** (+0.38 pp) |
| MLS | 47.01 / 1.0391 | 47.05 / 1.0383 | 46.98 / 1.0391 | NO (+0.04 pp = ruido; pasa la cláusula laxa pero queda por debajo del umbral v16 de +0.3 pp — en observación) |
| Premier | 51.27 / 1.0121 | 50.41 / 1.0820 | 49.76 / 1.0887 | NO (empeora claramente) |
| LaLiga | 53.09 / 1.0328 | **53.33 / 0.9908** | 52.89 / 1.0383 | **ADOPTAR imt** (+0.24 pp y ll −0.042) |
| Serie A | 53.81 / 1.0022 | 53.50 / 0.9969 | 52.73 / 1.0058 | NO |
| Bundesliga | 49.55 / 1.0247 | 48.55 / 1.0258 | **49.81 / 1.0213** | **ADOPTAR imt_c** (+0.26 pp, mejora ambos) |
| Ligue 1 | 51.65 / 1.0873 | 51.25 / 1.0493 | 51.64 / 1.0110 | NO (ll −0.076 pero acc no supera a base por 0.01 pp — regla es regla) |
| Eredivisie | 52.21 / 1.0304 | 52.27 / 1.0371 | **52.82 / 1.0300** | **ADOPTAR imt_c** (+0.61 pp) |
| Primeira | 56.52 / 0.9699 | **57.16 / 0.9655** | 56.79 / 0.9668 | **ADOPTAR imt** (+0.64 pp, mejora ambos) |
| Champions | 57.99 / 0.9258 | 57.58 / 0.9357 | 58.97 / 0.9385 | NO (+0.98 pp pero ll +0.013 > 0.01 — falla por 0.003; candidato v25 con más histórico) |

Lecturas:
- El IMT **sí aporta** en 5 de 10 ligas, incluidas DOS de las cuatro ligas
  objetivo del prompt (Bundesliga y Eredivisie) y Liga MX.
- En ligas "eficientes" con cuotas ya en las features (Premier, Serie A) el
  momentum no añade nada que el mercado no supiera — coherente con la teoría.
- Componentes vs índice: el compuesto gana 3 veces, las componentes 2 —
  ninguna variante domina; por eso ambas están soportadas en producción
  (`features_extra: ['imt']` o `['imt_c']`).

## 4. MESM extendido (run_mesm_v24.py — base = config ADOPTADA, lección v23)

Estrategias: D = MESM estándar v23 · E = MESM + componentes IMT en el meta.

| Liga | base | mesm_D | mesm_E | mercado | Regla de oro |
|---|---|---|---|---|---|
| Liga MX | 50.95 / 1.0179 | **53.15 / 0.9928** | 52.55 / 0.9953 | 52.84 | D ✓ (ya adoptado v23) |
| MLS | 45.96 / 1.0446 | **48.61 / 1.0310** | 47.90 / 1.0360 | 48.25 | D ✓ — **bate al mercado** |
| Premier | 46.29 / 1.0395 | **51.30 / 1.0348** | 49.09 / 1.0449 | 50.50 | D ✓ — **bate al mercado** (v23 lo descartaba) |
| LaLiga | 53.56 / 1.0296 | 52.63 / 0.9798 | 52.61 / 0.9853 | 54.75 | ✗ (pierde precisión) |
| Serie A | 52.80 / 0.9907 | 53.01 / 0.9805 | 53.41 / 0.9860 | 55.02 | D ✓ (ya adoptado v23) |
| Bundesliga | 48.55 / 1.0435 | **49.08 / 1.0186** | 48.38 / 1.0329 | 51.79 | D ✓ (v23 lo descartaba) |
| Ligue 1 | 53.94 / 1.0332 | 53.57 / 0.9919 | 52.62 / 1.0068 | 53.92 | ✗ |
| Eredivisie | 51.12 / 1.0608 | **53.46 / 0.9774** | 51.14 / 0.9916 | 53.95 | D ✓ (ya adoptado v23) |
| Primeira | 55.70 / 0.9535 | **58.11 / 0.9104** | 56.92 / 0.9175 | 58.21 | D ✓ (ya adoptado v23) |

**Estrategia E: DESCARTADA en todas las ligas.** El IMT nunca mejora al MESM
estándar a nivel meta (donde es señal útil, ya entró por las features del
modelo base; duplicarla en el meta solo añade varianza). Fracaso documentado.

La adopción FINAL del MESM la decide `entrenar_liga` validando contra el
modelo de PRODUCCIÓN (protocolo v23) en cada reentrenamiento — ver §5.

## 5. Producción reentrenada (split 80/20; MESM validado contra PRODUCCIÓN)

| Liga | Modelo | ELO | Mercado | MESM | Estado |
|---|---|---|---|---|---|
| Liga MX (+imt_c) | 51.6 / 1.001 | 50.3 | 53.5 | **55.4 / 0.970 ADOPTADO** | 🏆 **BATE AL MERCADO y cruza el objetivo ≥55 %** (v23: 54.9) |
| Primeira (+imt) | 54.2 / 0.960 | 53.1 | 56.1 | **56.2 / 0.942 ADOPTADO** | 🏆 **bate al mercado** |
| Eredivisie (+imt_c) | 51.0 / 1.111 | 49.7 | 53.4 | **53.0 / 0.985 ADOPTADO** | a 0.4 pp del mercado (v23: 53.7 con otro corte) |
| LaLiga (+imt) | 53.4 / 0.999 | 47.5 | 55.0 | descartado (52.6 < prod) | mejora ll de producción |
| Bundesliga (+imt_c) | 53.3 / 0.987 | 53.3 | 55.0 | descartado (52.0 < prod) | el screening D decía "golden" y la validación contra producción lo tumbó — la lección v23 del base débil se repitió y se respetó el protocolo |
| Premier (sin cambios) | 47.3 / 1.058 | 43.2 | 45.9 | descartado (44.5 < prod) | ídem — el screening D (51.3) era espejismo del base débil de ventana |
| MLS (nueva) | 47.2 / 1.041 | 44.7 | 50.1 | **50.0 / 1.038 ADOPTADO** | empata al mercado en su primer día |

Ligas sin cambio de config (serie_a, ligue_1, champions, mundial): intactas.
El Mundial sigue en 60.49 % — NO se tocó (regla de oro).

Smokes: ClubEngine (MLS + retrocompatibilidad) ✓ · test_simetria ✓ ·
test_match_parlay ✓ · AppTest dashboard (Mundial/MLS/Liga MX) ✓.

## 6. Áreas de mejora propuestas (v25)

1. **Champions + IMT compuesto**: quedó a 0.003 de log-loss de la regla de
   oro con +0.98 pp — con una temporada más de histórico FBref probablemente
   pase. Reintentar en v25.
2. **Cobertura FotMob**: el pipeline acumula ~15 partidos/liga/corrida. Con
   ~1 temporada de cobertura (≈300 partidos/liga) se podrán validar:
   ratings pre-partido (sin sesgo de anticipación, guardando el rating ANTES
   de cada jornada), defensivas reales para el MAT, y **remates por
   jugador-partido para el MAT individual** (el deliverable pospuesto).
3. **MLS**: 47.2 % de modelo puro es bajo (liga de alta paridad + viajes
   larguísimos). Probar features geográficas tipo `mx` (distancia/husos
   horarios/altitud Denver-Salt Lake) en v25.
4. **Ligue 1**: imt_c mejoró el ll en −0.076 pero falló la regla por 0.01 pp
   de precisión. Vale la pena reintentarlo con la temporada 2026-27.

## 7. Reglas de oro respetadas

- El Mundial (60.49 %) NO se tocó.
- Solo sube a producción lo que superó walk-forward.
- Fuentes gratuitas y accesibles desde Streamlit Cloud.
- Fracasos documentados: Soccer24 inviable; API FotMob blindada (se rodea
  por __NEXT_DATA__); cobertura FotMob insuficiente para features aún.
