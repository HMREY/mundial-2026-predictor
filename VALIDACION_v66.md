# VALIDACIÓN v66 — El modelo internacional pasa de 49 a 200 selecciones

**Fecha:** 2026-07-25 · **Entorno:** `.venv` Python 3.12 · **Histórico:** 32.400
partidos reales (1990-01-12 → 2026-07-15, Kaggle martj42 vía kagglehub).

---

## 0. Resumen ejecutivo

| Qué | Antes (v65) | Después (v66) |
|---|---|---|
| Selecciones seleccionables en la UI | 49 | **200** |
| Fixtures de ESPN que enlazan con el modelo | 30 de 163 | **163 de 163** |
| Precisión validación (protocolo de producción) | 0.5986 | **0.6008** |
| Log-loss validación (protocolo de producción) | 0.8756 | **0.8697** |
| Precisión sobre las 49 originales (comparable) | 0.5000 | **0.5023** |
| Log-loss sobre las 49 originales | 0.9863 | **0.9824** |
| Walk-forward (5 ventanas 2024-2026) | 0.5960 / 0.8716 | **0.5967 / 0.8683** |
| Walk-forward sobre las 49 originales | 0.4661 / 1.0125 | **0.4770 / 1.0082** |

**Veredicto: se despliega.** El universo ampliado **no degrada ninguna métrica**
y mejora el log-loss en todas. El objetivo del encargo (30 → 120-150 fixtures
enlazables) se supera: enlazan **los 163**, sin un solo nombre sin mapear.

---

## 1. EL HALLAZGO QUE CAMBIA EL PLANTEAMIENTO

El encargo asumía que ampliar el universo metería 150 selecciones débiles en el
conjunto de entrenamiento y validación, con riesgo de bajar la precisión. **Eso
ya había pasado: el modelo llevaba versiones entrenándose con las 326.**

Verificado en el código, no por inferencia:

* `data_fetcher.download_kaggle_results()` **no filtra por `TEAMS`**. El filtro
  `isin(TEAMS)` que menciona el encargo está en `download_kaggle_goalscorers()`
  (goles), no en los resultados. El histórico guarda TODOS los partidos
  internacionales desde 1990.
* `feature_engineering.construir_dataset_supervisado()` recorre el histórico
  entero; el único requisito es que ambos equipos tengan ≥3 partidos previos.
* `train_tda_model.entrenar()` pasa el histórico completo a esa función.

Medido: el dataset supervisado tiene **31.648 filas**, de las cuales sólo
**5.344 (17 %) tienen a las dos selecciones dentro de las 49**. El 83 % del
entrenamiento y de la validación ya era "resto del mundo".

**Consecuencia:** `TEAMS` nunca fue un filtro de datos. Era un filtro de
**superficie**: qué selecciones aparecen en `team_stats.json`, en el selector de
la UI y en el mapeo de fixtures. Ampliarlo abre esas tres puertas sin tocar el
conjunto de entrenamiento — por eso el riesgo de §7 del encargo no se
materializa.

### 1.1 Segundo hallazgo: el 60,38 % no significa lo que parecía

Al desglosar la validación por universo aparece una diferencia enorme:

| Subconjunto de validación | n | Precisión | Log-loss |
|---|---|---|---|
| Ambos equipos entre las 49 del Mundial 2026 | 444 | **0.5023** | 0.9824 |
| Resto del universo | 2.204 | **0.6207** | 0.8470 |
| Global (lo que publica la app) | 2.648 | 0.6008 | 0.8697 |

La cifra de portada está dominada por partidos con desnivel grande
(Alemania-Malta), que son fáciles. **Entre selecciones de nivel comparable el
modelo acierta ~50 %, no ~60 %.** No es una regresión de v66 — es como ha sido
siempre; v66 sólo lo hace visible. Ahora `modelos/metadata.json` publica los tres
números (`validacion_mundial_2026`, `validacion_resto_universo` y el global) para
que la comparación entre versiones no se vuelva a hacer contra una métrica cuya
composición cambia.

---

## 2. Criterio del universo y cómo se genera

`generar_universo_selecciones.py` (nuevo) deriva todo del histórico, sin listas
a mano:

* **Criterio:** ≥ 100 partidos desde 1990 → **exactamente 200 selecciones**.
  Distribución medida: 153 con ≥200 partidos, 200 con ≥100, 224 con ≥50, 326 en
  total. El corte en 100 es el que da ~200 y deja fuera sólo colas muy finas
  (Mongolia 99, Aruba 95, Sudán del Sur 78).
* **`TEAM_NAMES_EN`:** nombre EXACTO tal y como lo publica Kaggle (es la clave
  del mapeo con ESPN). Se lee del propio histórico, no se teclea.
* **`TEAM_STYLE`:** `bloque_alto` si el ELO final está en el cuartil superior
  (corte 1689,8), si no `bloque_bajo` → 50 / 150. **Antes, las 277 selecciones
  fuera de la lista caían todas en el default `bloque_alto` de `.get()`, lo que
  dejaba la feature `CHOQUE_ESTILOS` en 0 para el 72 % de los partidos**
  (8.926 de 31.648 filas la tenían distinta de 0).
* **`TEAM_NAMES_ES`, `TEAM_PARTIDOS`, `TEAM_ELO`, `TEAM_ALIAS`:** generados en
  el mismo paso.

Salida: `config_selecciones.py` (generado, no editar a mano). `config.py` lo
importa con degradación limpia: si el fichero falta, vuelve a las 49 de siempre.

**Interruptor de emergencia:** `MUNDIAL_UNIVERSO=v65` en el entorno devuelve el
proyecto entero a las 49 selecciones sin tocar código. Es lo que hace comparable
el A/B de abajo y sirve de rollback inmediato en producción.

---

## 3. A/B del modelo — mismo histórico, mismo protocolo

Las dos ramas corren sobre el **mismo `historico_partidos.csv`** y el mismo
pipeline; lo único que cambia es el universo (`MUNDIAL_UNIVERSO`). Así se evita
el confound que el encargo advierte en §6.4: no hay ninguna feature extra
colándose por la puerta de atrás.

### 3.1 Protocolo de producción (`--corte 2024-01-01`, n = 2.648)

| Métrica | v65 (49) | v66 (200) | Δ |
|---|---|---|---|
| Precisión global | 0.5986 | **0.6008** | +0.22 pp |
| Log-loss global | 0.8756 | **0.8697** | −0.0059 ✅ |
| **Precisión 49 originales** | 0.5000 | **0.5023** | **+0.23 pp** ✅ |
| **Log-loss 49 originales** | 0.9863 | **0.9824** | **−0.0039** ✅ |
| Precisión resto | 0.6184 | **0.6207** | +0.23 pp |
| Log-loss resto | 0.8533 | **0.8470** | −0.0063 ✅ |

### 3.2 Split por percentil 80 (`corte 2019-11-07`, n = 6.331)

| Métrica | v65 (49) | v66 (200) | Δ |
|---|---|---|---|
| Precisión global | 0.6039 | **0.6040** | +0.01 pp |
| Log-loss global | 0.8858 | **0.8789** | −0.0069 ✅ |
| Precisión 49 originales | 0.5044 | 0.5044 | = |
| Log-loss 49 originales | 0.9998 | **0.9956** | −0.0042 ✅ |

### 3.3 Walk-forward (5 ventanas de 6 meses, 2024-2026)

| Métrica | v65 (49) | v66 (200) | Δ |
|---|---|---|---|
| Precisión media | 0.5960 | **0.5967** | +0.07 pp |
| Log-loss medio | 0.8716 | **0.8683** | −0.0033 ✅ |
| **Precisión media 49 originales** | 0.4661 | **0.4770** | **+1.09 pp** ✅ |
| Log-loss medio 49 originales | 1.0125 | **1.0082** | −0.0043 ✅ |

**Ninguna métrica se degrada. La regla de oro se cumple con margen.**

### 3.4 ¿Y el 60,38 % que estaba desplegado?

El modelo en producción reportaba 0.6038 / 0.8712 sobre 2.640 partidos. La rama
v65 reproducida aquí da 0.5986 / 0.8756 sobre 2.648. La diferencia (−0.5 pp de
precisión, +0.004 de log-loss) **no viene de v66**: viene de que el histórico se
regeneró con datos más frescos (32.400 partidos hasta el 15-jul vs. 32.386 hasta
el 12-jul) y de que los partidos de las 151 selecciones nuevas ahora traen el
desglose real de minutos de gol. Sobre datos idénticos, v66 ≥ v65 en todo.

---

## 4. Lo que se probó y NO se adoptó

### 4.1 Feature de "nivel de datos" (alternativa §7.1 del encargo)

Se implementó `NIVEL_DATOS_MIN` / `NIVEL_DATOS_DIF` (partidos acumulados de cada
selección ANTES del partido, en escala log; sin fuga temporal). Requirió añadir
un contador `n_total` a `EstadoRodante`, porque las ventanas existentes están
topadas a 5/10 partidos y no sirven para medir cuánta historia hay.

**Resultado: NO se adopta.** Los números, contra la rama v66 sin la feature:

| Protocolo | Métrica | v66 | v66 + NIVEL_DATOS | Δ |
|---|---|---|---|---|
| corte 2024-01-01 | precisión global | **0.6008** | 0.5990 | −0.18 pp ❌ |
| corte 2024-01-01 | log-loss global | 0.8697 | **0.8674** | −0.0023 ✅ |
| corte 2024-01-01 | precisión 49 orig. | 0.5023 | **0.5135** | +1.12 pp ✅ |
| percentil 80 | precisión global | **0.6040** | 0.6033 | −0.07 pp ❌ |
| percentil 80 | log-loss global | 0.8789 | **0.8775** | −0.0014 ✅ |
| percentil 80 | precisión 49 orig. | 0.5044 | **0.5121** | +0.77 pp ✅ |
| walk-forward | precisión media | 0.5967 | **0.5980** | +0.13 pp ✅ |
| walk-forward | log-loss medio | 0.8683 | **0.8660** | −0.0023 ✅ |
| walk-forward | precisión 49 orig. | **0.4770** | 0.4768 | −0.02 pp ≈ |

Lectura honesta: **el log-loss mejora en los tres protocolos, pero la precisión
va en direcciones distintas** (baja en los dos splits, sube en el walk-forward).
La ganancia sobre las 49 originales (+1.12 pp) suena bien pero está dentro del
ruido: con n = 444 el error estándar ronda 2.4 pp, y el walk-forward — que es el
protocolo con más ventanas — no la reproduce (−0.02 pp). Es exactamente el
patrón de comparaciones múltiples que tumbó el ELO ataque/defensa en v33 y el
CDI de Conference League en v35.

Se deja fuera por coherencia con ese criterio. Matiz para el futuro: en una
plataforma de apuestas el log-loss pesa más que el argmax, porque las
probabilidades alimentan el EV. Si se quiere resolver la duda, el juez adecuado
no es la precisión sino un backtest de ROI/EV sobre los picks — pendiente para
una versión con ese banco de pruebas montado, no una decisión que tomar aquí.

El código queda en el repo detrás de `MUNDIAL_NIVEL_DATOS=1` (apagado por
defecto) y el contador `N_TOTAL` se mantiene siempre, así que reactivarlo o
reevaluarlo con más datos no cuesta nada.

### 4.2 Alternativas que NO hizo falta probar

El encargo proponía, si la precisión se degradaba: ponderar el entrenamiento por
volumen/torneo, subir el corte a ≥200 partidos, o mantener dos modelos separados
(§7.2-§7.4). **Ninguna se probó porque la premisa no se cumplió**: la métrica
comparable mejora en los tres protocolos. Probarlas habría sido optimizar contra
ruido. El interruptor `MUNDIAL_UNIVERSO=v65` cubre el caso de que el usuario
quiera volver atrás.

---

## 5. Escala: `update_team_stats.py`

Medido en la misma máquina, mínimo de 3 ejecuciones (`_v66_medir_team_stats.py`):

| Escenario | Selecciones | Parejas H2H | `team_stats.json` | `build_team_stats` | `build_key_players` |
|---|---|---|---|---|---|
| v65 (49) | 49 | 745 | 85,1 KB | 11,2 s | 1,13 s |
| v66 (200) sin optimizar | 200 | 5.006 | 385,4 KB | 12,68 s | 3,22 s |
| **v66 (200) optimizado** | 200 | 5.006 | **385,4 KB** | **11,30 s** | **3,16 s** |

**Conclusión sobre el riesgo del encargo:** el bucle O(n²) **no era el cuello de
botella real**. Pasar de 1.176 a 19.900 parejas sólo costaba ~1,4 s, porque el
grueso de los 11 s es el replay del estado rodante sobre los 32.400 partidos —
que ya recorría las 326 selecciones antes de v66. El coste de escala real es
`build_key_players` (×2,8), y aun así son 2 segundos.

`team_stats.json` crece ×4,5 pero **385 KB no afectan al arranque de Streamlit
Cloud** (es un `json.load` que se cachea con `@st.cache_resource`). No hizo falta
guardar el H2H bajo demanda ni recortar el universo.

**Equivalencia verificada:** la versión optimizada y la original con el mismo
universo producen `team_stats.json` **idéntico** — 0 claves H2H distintas,
0 valores distintos y 0 campos de equipo distintos (ELO, medias móviles,
reacción, `PARTIDOS_30D`). La optimización es puro coste, no cambia resultados.

Lo que sí gana la optimización es **memoria y futuro**: el bucle antiguo creaba
~19.000 entradas vacías en el `defaultdict` de H2H, y a 326 selecciones serían
52.975 parejas. El nuevo recorrido es lineal en cruces reales.

### 5.1 Qué se optimizó

1. **H2H O(n²) → lineal.** El bucle recorría las n(n−1)/2 parejas posibles
   (1.176 con 49 selecciones, **19.900 con 200**, 52.975 si algún día se cubren
   las 326). Ahora recorre el índice de cruces REALES. La salida es idéntica: el
   bucle antiguo ya descartaba `balance == 0.0` y `prediction_api.h2h_balance()`
   resuelve la pareja en cualquier orden.
   *Efecto secundario corregido:* `estado.h2h` es un `defaultdict`, así que
   consultar una pareja inexistente **creaba** la entrada — el bucle antiguo
   dejaba ~19.000 deques vacíos en memoria.
2. **Métricas de reacción:** se indexan los goles por equipo una sola vez en vez
   de filtrar el DataFrame completo 200 veces. Además, "¿respondió tras
   encajar?" pasa de un doble bucle por gol a comparar con el máximo minuto
   propio del partido (equivalencia exacta: `any(propios > m)` ⟺ `max(propios) > m`).
3. **`PARTIDOS_30D`:** un único `value_counts` en lugar de 200 filtros.
4. **`build_key_players`:** índice por equipo precalculado, y orden total
   determinista (`date` + `MATCH_ID`): con `sort_values('date')` a secas los
   empates de fecha quedaban a merced del algoritmo de ordenación y
   `ultimos5_ids` podía variar entre ejecuciones.

La misma optimización de H2H se aplicó al camino de respaldo de
`prediction_api.PredictionEngine._cargar()` (el que se usa si falta
`team_stats.json`).

---

## 6. Mapeo de fixtures: 30 → 163 de 163

`fixtures_espn.fixtures_selecciones()` devuelve 163 partidos programados
(amistosos, Nations League y clasificatorias; ventana de 210 días).

| | Antes | Después |
|---|---|---|
| Fixtures programados | 163 | 163 |
| Enlazan con el modelo | **30** | **163** |
| Nombres sin mapear | 39 | **0** |

Los 39 que quedaban fuera (Andorra, Malta, Kosovo, Liechtenstein, Georgia,
Gales, Chequia, Türkiye, Bosnia-Herzegovina, Irlanda…) están todos cubiertos.
Verificado uno a uno: **60 nombres distintos → 60 códigos únicos, sin colisiones
y sin un solo mapeo incorrecto.**

### 6.1 El riesgo real del mapeo con 200 selecciones (y cómo se cerró)

Con 49 selecciones nunca coexistían nombres contenidos unos en otros. Con 200 sí:
Congo / RD Congo, Guinea / Guinea Ecuatorial / Guinea-Bisáu, Sudán / Sudán del
Sur, Irlanda / Irlanda del Norte, Corea del Sur / Corea del Norte. Dos defectos
reales que eso destapó:

1. **`name_mapper.mapear()`** devolvía el **primer** candidato por contención de
   subcadena — con un catálogo grande, una lotería. Ahora recoge todos los
   candidatos por contención y devuelve el más parecido. Verificado: los 12
   pares ambiguos resuelven correctamente.
2. **`prediction_api.detectar_equipos()`** (consultas en texto libre) recorría
   los alias en orden de diccionario, así que "RD Congo vs Guinea Ecuatorial"
   podía devolver Congo y Guinea. Ahora busca de nombre más largo a más corto y
   tacha el trozo ya consumido.

Además, `TEAM_ALIAS` da coincidencia **exacta** (antes del fuzzy) para los
nombres alternativos de cada fuente: "Czechia", "Türkiye", "Republic of
Ireland", "Korea Republic", "China PR", "Chinese Taipei", "Holland"…

---

## 7. Otros cambios necesarios para la escala

* **`correlated_synthetic_generator.tier_equipo()`** (nuevo). `TEAM_TIER` está
  calibrado a mano sólo para las 49; las 151 nuevas caían todas en el default
  0.5, así que el aumento sintético generaba partidos irrealmente parejos (San
  Marino "igual que" Suecia). Ahora, para las que no tienen tier manual, se
  estima con la recta *tier ~ percentil de ELO* ajustada por mínimos cuadrados
  sobre las 49 calibradas, acotada a [0.15, 0.97]. Se trabaja en percentil y no
  en ELO crudo porque las anclas se concentran en la mitad alta del rango y una
  recta sobre el ELO bruto extrapola a valores negativos.
* **Orden de la UI:** `PredictionEngine.equipos` se ordena por el nombre
  mostrado en español, no por código. Con 49 daba igual; con 200, ordenar por
  código ponía "Argelia" (ALG) antes que "Andorra" (AND).
* **Transparencia en la UI:** el selector indica cuántos de los fixtures
  programados enlazan, y un desplegable lista los que no, explicando por qué
  (menos de 100 partidos en el histórico).

---

## 8. Consumidores de `TEAMS` revisados (§4.5 del encargo)

| Módulo | Efecto de pasar a 200 | Acción |
|---|---|---|
| `betexplorer_scraper.py` | `if home not in TEAMS` → acepta más partidos | ninguna (mejora) |
| `correlated_synthetic_generator.py` | tier por defecto 0.5 para 151 | **corregido** (§7) |
| `data_manager.py` | sólo flujo sintético de respaldo | ninguna |
| `fbref_scraper_v2.py` | 4× peticiones… pero es opt-in (`--fbref`) | documentado |
| `goleadores.py` | no usa `TEAMS` | ninguna |
| `live_worldcup.py` | filtro OR → acepta más partidos | ninguna (mejora) |
| `prediction_api.py` | selector, H2H de respaldo, texto libre | **corregido** (§5, §6.1) |
| `data_fetcher.py` | `goleadores.csv` pasa de 489 KB a 762 KB | ninguna (más cobertura real de minutos de gol) |

---

## 9. Tests de no regresión

Ejecutados sobre el modelo y el `team_stats.json` ya regenerados con 200
selecciones:

| Test | Resultado |
|---|---|
| `test_simetria.py` | ✅ TODO OK — 10 cruces, probabilidades y goles esperados espejados; la localía no depende del orden |
| `test_match_parlay.py` | ✅ TODO OK — compatibilidad de picks, un pick por mercado, probabilidad conjunta coherente, EV = 0 con cuotas justas |
| `smoke_botones.py` | ✅ TODO OK — 5 vistas cargan y **todos los botones responden**, incluido «Proponer parlays» de 🌍 Partidos Internacionales |

En la corrida de `smoke_botones.py` el log confirma la vista internacional
alimentándose de ESPN: `[selecciones] 163 próximos partidos de selecciones`.

Comprobaciones adicionales específicas de v66:

* `team_stats.json` regenerado: **200 selecciones, 5.006 parejas H2H**, hasta
  2026-07-15.
* `jugadores_clave.csv`: de 49 a **163 selecciones** con artilleros reales
  (1.020 jugadores).
* Mapeo de fixtures: 60 nombres distintos → 60 códigos únicos, revisados uno a
  uno, sin colisiones.
* `MUNDIAL_UNIVERSO=v65` verificado: devuelve `len(TEAMS) == 49` y
  `TEAM_STYLE` de 49 entradas.

---

## 10. Entregables

* `generar_universo_selecciones.py` — generador reproducible del universo.
* `config_selecciones.py` — 200 selecciones (generado).
* `config.py` — importa el universo, conserva `TEAMS_MUNDIAL_2026` y añade
  `TEAM_ALIAS` / `ALIAS_TO_FIFA`; interruptor `MUNDIAL_UNIVERSO=v65`.
* `update_team_stats.py` — optimizado para 200 selecciones.
* `train_tda_model.py` — métrica del subconjunto de 49 en el split y en el
  walk-forward, y `--salida` para entrenar sin pisar producción.
* `feature_engineering.py` — contador `N_TOTAL` y features `NIVEL_DATOS_*`
  (apagadas por defecto).
* `name_mapper.py`, `prediction_api.py`, `dashboard_ui.py`,
  `correlated_synthetic_generator.py` — correcciones de escala.
* `modelos/` reentrenado + `metadata.json` v12 con el desglose por universo.
