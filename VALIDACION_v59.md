# VALIDACIÓN v59 — Features de dominio territorial + próximos partidos multideporte

**Fecha:** 2026-07-24

## 1. Features v59 (córners, volumen de remates, conversión)

**Hallazgo:** football-data ya nos da CÓRNERS (HC/AC) y VOLUMEN de remates
(HS/AS) en las ligas 'main', y el modelo NO los usaba (solo remates a puerta).
`features_v59.py` los convierte en 4 features rodantes de 5 partidos, sin fuga
(pase cronológico): DIFF_CK_MA5, DIFF_CKC_MA5, DIFF_SHOTS_MA5, DIFF_CONV_MA5.

### Error metodológico detectado y corregido (importante)

La PRIMERA corrida del A/B usó `entrenar_liga(con_ratings=True)` para no
sobrescribir artefactos — pero ese flag AÑADE la feature VAL_LOG_RATIO de
Transfermarkt, así que medía en un espacio que **no es el de producción**.
Daba 4 adopciones. Repetido en el espacio real (`con_ratings=False`), el
resultado se invierte casi por completo:

| Liga | acc base → ck | Δ pp | ll base → ck | Δ ll | Veredicto |
|------|---------------|------|--------------|------|-----------|
| **laliga** | 0.5282 → 0.5362 | **+0.80** | 1.0679 → 0.9726 | **−0.0953** | ✅ ADOPTAR |
| **primeira** | 0.5423 → 0.5473 | **+0.50** | 0.9604 → 0.9519 | **−0.0085** | ✅ ADOPTAR |
| turquia | 0.5505 → 0.5051 | −4.54 | +0.0115 | | ❌ |
| premier | 0.4727 → 0.4455 | −2.72 | −0.0068 | | ❌ |
| ligue_1 | 0.5167 → 0.4954 | −2.13 | +0.1013 | | ❌ |
| bundesliga | 0.5497 → 0.5364 | −1.33 | −0.0014 | | ❌ |
| eredivisie | 0.5134 → 0.5067 | −0.67 | +0.0039 | | ❌ |
| serie_a | 0.5479 → 0.5479 | 0.00 | +0.0031 | | ❌ |

**Solo 2 de 8 ligas mejoran.** LaLiga se confirmó repitiendo la corrida
(números idénticos → entrenamiento determinista). Se adopta `'ck'` ÚNICAMENTE
en laliga y primeira; en el resto se descarta (regla de oro: solo se lanza lo
positivo).

Interpretación honesta: 4 features extra sobre un modelo de ~20 en unos pocos
miles de partidos añaden varianza; solo compensa donde el histórico es más
profundo y la señal territorial es estable.

### Reentrenamiento de saneamiento

El A/B con `con_ratings=False` SOBRESCRIBE artefactos, dejando modelos
entrenados con features que su config no declaraba (desajuste modelo/config).
Se reentrenaron las 8 ligas 'main' con su configuración final y se verificó que
las no adoptantes recuperan exactamente sus métricas previas:

turquia 0.5505 · premier 0.4727 · serie_a 0.5479 · bundesliga 0.5497 ·
ligue_1 0.5167 · eredivisie 0.5134 · **laliga 0.5362 (ck)** · **primeira 0.5473 (ck)**

## 2. Próximos partidos en TODOS los deportes

- **Fútbol** (v58): ya estaba, vía `fixtures_espn.fixtures_liga`.
- **MLB / NBA** (v59): `fixtures_espn.fixtures_deporte()` sobre el mismo
  scoreboard de ESPN. Verificado: MLB 57 partidos programados; NBA 0 (fuera de
  temporada, correcto). El de MLB mapea con `codigo_mlb`.
- **Tenis** (v59): partidos del día vía Betexplorer (la fuente que ya usa el
  barrido), emparejando ambos jugadores con el modelo.

Todos con caché de 30 min → **se refrescan automáticamente**, y un botón
«Cargar» que autorrellena los selectores.

## 3. FIX de producción (v58.1)

`UnboundLocalError: AVISO_JUEGO_RESPONSABLE` al pulsar «Proponer parlays»: el
símbolo se importaba más abajo DENTRO de la misma función, volviéndolo local en
todo el cuerpo. Corregido importándolo al inicio (mismo patrón en «Combinadas
del Día»). Chequeo AST: no quedan más usos-antes-de-import-local.

**Lección de proceso:** los smoke tests solo CARGABAN las páginas, y el fallo
vivía dentro de `if st.button(...)`. Se añade `smoke_botones.py`, que PULSA los
botones críticos de cada vista. Es ahora parte de la batería previa a desplegar.

## No regresión
- `test_simetria.py` → TODO OK · `test_match_parlay.py` → TODO OK
- `smoke_botones.py` (carga + clic) → TODO OK
- Inferencia verificada en laliga/primeira/premier (14 secciones).
