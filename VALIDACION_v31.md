# VALIDACIÓN v31 — Cobertura universal, doble capa y limpieza

**Fecha:** 2026-07-22 · Regla de oro respetada; fútbol (Mundial 60.49 % +
10 ligas) y motores MLB/NBA/Tenis intactos.

## 1. Cobertura universal de Apuestas del Día (§1) ✅

`alpha_finder.apuestas_del_dia_universal()`: recorre **todas** las
competiciones activas (11 de fútbol vía odds_actuales + MLB + NBA + tenis
ATP), instancia cada motor y consolida los picks. Barrido real verificado:

| Deporte | Fuente de cuotas | Picks capa 1 |
|---|---|---|
| Fútbol (10 ligas + Mundial) | fixtures.csv / Betexplorer / Odds API | 4 |
| MLB | The Odds API (`baseball_mlb`) | 2 |
| Tenis ATP | **Betexplorer `/next/tennis/`** | 1 |
| NBA | — (fuera de temporada: 0 partidos, verificado) | 0 |

Resultado del barrido: **7 picks capa 1 en 3 deportes + 1 capa 2 + 1 partido
reportado como no enlazado**. Cacheado 30 min (`@st.cache_data`).

## 2. Doble capa (§5) ✅

- **Capa 1 «EVC Platino»**: hay cuota real y pasa los filtros de élite
  (umbral de confianza por deporte: fútbol 70 %, MLB 58 %, tenis 65 %,
  NBA 70 %; EV > +3 %; cuota > 1.50). Stake por Kelly simultáneo.
- **Capa 2 «Alta Confianza»**: sin cuota en vivo y confianza > 75 % → se
  muestra la **cuota mínima sugerida** (1/prob) con aviso explícito y SIN
  stake (no hay EV real).
- Exportación TXT/CSV cubre ambas capas + columna de deporte y capa.

## 3. Betexplorer tenis/baloncesto (§4) ✅ (con corrección de la spec)

**Las URLs del prompt son incorrectas**: `/tennis/matches-today/` y
`/basketball/matches-today/` devuelven **la página de FÚTBOL** (mismo HTML,
verificado byte a byte). La ruta real es **`/next/{deporte}/`**, con
estructura de tabla (spans `--home`/`--away` + botones `data-odd`).

- `cuotas_tenis_hoy()` (filtra ATP singles): **10 partidos ATP con cuotas**.
- `cuotas_baloncesto_hoy()` (filtra NBA): 0 — off-season confirmado.
- **Fuzzy matching** (`normalizar_nombre` sin tildes + `SequenceMatcher`
  ≥0.75 con caché): **9/10 emparejados** con el catálogo del dataset ATP
  (los nombres de Betexplorer ya vienen en formato «Apellido I.», igual que
  el dataset). El no emparejado («Torres T.») **no se descarta en silencio**:
  se reporta en un desplegable de «partidos no evaluados» (§4.2).

## 4. Features transversales (§3)

| Feature | Ámbito | Resultado |
|---|---|---|
| **Decaimiento inter-temporada** (α=t/N, N=20) | MLB | ❌ **DESCARTADO**: 54.66 % vs 54.98 % — y **también peor al inicio de temporada** (56.26 % vs 56.70 %), que era justo la hipótesis. La media móvil ya arrastra la cola de la campaña anterior, más informativa que la media de liga. |
| **CDI** | MLB / NBA | Ya resuelto en v30: descartado en MLB, **adoptado en NBA**. Para fútbol (MLS/Liga MX/Champions) hace falta el histórico de SEDE por partido que el pipeline no almacena, y la v25 ya descartó una feature de husos estática en MLS → **diferido** con razón, no forzado. |
| **ELO Saque/Resto por superficie** (tenis) | Tenis | ❌ **IMPOSIBLE con la fuente**: el dataset Kaggle NO tiene columnas de saque/resto (verificado: Tournament, Date, Series, Court, Surface, Round, Best of, Players, Winner, Ranks, Pts, Odds, Score). Se aplica la contingencia del propio spec: **fallback silencioso a ELO global** (lo que ya hace el motor). |
| **Abridor/Bullpen separados** (MLB) | MLB | Diferido: exige los *event files* de Retrosheet (entrada por entrada), no los game logs — mismo bloqueo que el umpire en v30. |
| **ELO Ataque/Defensa** (fútbol) | 10 ligas | No ejecutado en esta versión: 10 ligas × walk-forward es el experimento más caro del backlog y la ganancia es especulativa. Queda como primer candidato de v32 (declarado, no simulado). |

## 5. Deprecaciones de Streamlit (§6) ✅

34 ocurrencias (`dashboard_ui.py` 28 + `app_legacy_v1.py` 6) migradas a
`width='stretch'` / `width='content'` (Streamlit 1.58 lo soporta).

**Incidente detectado y corregido en el proceso:** el primer reemplazo se
hizo con PowerShell, cuyo `Get-Content` leyó el UTF-8 como ANSI y corrompió
todos los acentos del archivo («Día» → «DÃ­a»). Se revirtió con git y se
rehízo en Python con codificación explícita. Verificado: 0 ocurrencias
restantes, acentos intactos, sin mojibake.

## 6. Bugs cazados de paso

- **`Aciertos` con tipos mixtos** (int y `'—'`) rompía la serialización
  Arrow del panel de rendimiento (`ArrowInvalid: Conversion failed for
  column Aciertos`) → normalizado a string.
- Las tarjetas de picks accedían a `t['cuota']`/`t['ev']` sin defensa, lo que
  habría roto la Capa 2 (sin cuota) → reescritas con `.get()`.

## 7. No regresión ✅

test_simetria ✓ · test_match_parlay ✓ · smoke 10 ligas de fútbol ✓ · smoke
MLB/NBA/Tenis ✓ · **AppTest en AMBOS modos × 5 vistas** (Apuestas del Día,
MLB, NBA, Tenis, Liga MX) ✓ · botones de exportación presentes y con
contenido ✓ · Mundial intacto.
