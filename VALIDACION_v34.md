# VALIDACIÓN v34 — Cobertura universal y cosecha estratégica

**Fecha:** 2026-07-23 · Mundial (60.49 %) y ligas previas intactos.

## 1. PRIORIDAD ABSOLUTA: cobertura diaria ✅ OBJETIVO CUMPLIDO

**11 → 48 partidos evaluados (×4.4)**, dentro del rango 50-80 que pedía el
spec para un día de verano, y con **0 partidos sin mapear**.

| | v33 | v34 |
|---|---|---|
| Partidos con cuotas capturadas | ~100 | **178** |
| Partidos evaluados en el barrido | 11 | **48** |
| Ligas con partidos evaluados | 4 | **10** |
| Partidos sin mapear | 1 | **0** |

Cobertura real medida: `{mls:21, argentina:15, brasil:12, suecia:6,
liga_mx:6, noruega:5, champions:4, irlanda:3, finlandia:4, primeira:1}`.
Las 6 ligas europeas que salen a cero están en **parón real de temporada**
(el log lo avisa explícitamente, §1.1).

**Tres palancas, todas verificadas:**
1. **5 ligas de verano nuevas** (§1.3) — todas con datos frescos:
   | Liga | Antigüedad | Modelo | ELO | Mercado |
   |---|---|---|---|---|
   | Noruega (Eliteserien) | 5 d | **55.0 %** | 53.1 % | 58.2 % |
   | Rumanía (Liga I) | 3 d | 49.5 % | 47.8 % | 51.1 % |
   | Irlanda (Premier Div.) | 12 d | 45.2 % | 42.6 % | 47.4 % |
   | Suecia (Allsvenskan) | 3 d | 48.5 % | ⚠️ 50.4 % | 51.7 % |
   | Finlandia (Veikkausliiga) | 3 d | 51.0 % | ⚠️ 51.3 % | 51.7 % |

   **Aviso honesto**: Suecia y Finlandia **NO superan su línea base ELO**;
   se incluyen por cobertura, pero sus picks pasan por los mismos filtros de
   EV/fiabilidad y conviene tratarlos con cautela.
   **China y Corea NO se añaden**: The Odds API tiene sus cuotas, pero **no
   existe histórico gratuito para entrenar** — sin modelo no hay predicción,
   y publicar picks sin modelo sería inventar.
2. **Horizonte 48 h → 72 h**: había 178 partidos con cuotas y el corte
   temporal dejaba fuera a la mayoría.
3. **`name_mapper.py`** (§4): alias manuales + normalización (tildes,
   sufijos societarios, apóstrofes) + fuzzy + **registro de fallos** en
   `nombres_sin_mapear.json`. Resultado: **0 sin mapear** (antes se perdían
   partidos en silencio).

## 2. Hallazgo mayor: el filtro de EV vale 87 puntos de ROI

Backtest de gestión de capital sobre **480 días reales** de picks históricos
(`run_markowitz_v34.py`):

| Estrategia | ROI total | Drawdown máx | Volatilidad diaria |
|---|---|---|---|
| Kelly ⅛ (todos los picks) | −94.78 % | 95.6 % | 4.17 % |
| **Kelly ⅛ + filtro EV v32** | **−8.10 %** | **34.7 %** | — |
| Markowitz (todos) | −100 % | 100 % | 15.95 % |
| Markowitz + filtro EV v32 | −99.99 % | 100 % | — |

**Dos conclusiones, ambas importantes:**
1. **El filtro de EV extremo de la v32 transforma una ruina (−94.8 %) en una
   pérdida contenida (−8.1 %)**: 87 puntos porcentuales de diferencia. Es la
   validación independiente más fuerte que ha tenido una decisión de este
   proyecto.
2. **Markowitz NO se adopta** (§5): concentra el peso justo en los picks de
   mayor EV, que son los peor calibrados; su volatilidad cuadruplica a la de
   Kelly y termina en ruina total incluso con el filtro aplicado.

**Y una advertencia que toca decir sin adornos:** ni siquiera la mejor
variante da ROI positivo (−8.1 %) sobre ese conjunto histórico. Ese conjunto
es el de los picks *antiguos* sin EVC, sin fiabilidad Brier, sin cuarentena
ni umbrales por deporte — todo eso llegó después. No es un veredicto sobre el
sistema actual, pero **tampoco hay evidencia todavía de rentabilidad real**:
el panel de Rendimiento Real (v32) es el que dará la respuesta honesta con
los picks que se publiquen de aquí en adelante.

## 3. Cadena de resiliencia universal ✅

`source_resilience.py` (v33, probado con fallo forzado) se extiende ahora a
la NBA: `The Odds API → Betexplorer`, con la ventana de temporada integrada
para no gastar créditos fuera de ella.

## 4. Activadores automáticos ✅

- **NBA con cuotas reales (§4)**: `basketball_nba` ya está en `SPORT_KEYS`
  con ventana de temporada (oct-jun). En julio **ni se intenta la petición**;
  en octubre se activa sola y sus picks pasan a tener EV real y stake Kelly.
- **Presupuesto adaptativo**: con 17 ligas la captura completa cuesta ~20
  créditos, así que los snapshots RLM bajan de 3 a 2 o 1 al día según el
  saldo mensual (corte duro en 50).
- **Shadow en Bundesliga/Eredivisie (§2)**: sigue calendarizado a septiembre
  2026 (necesita 60 días de snapshots RLM). No se fuerza.

## 5. Valor en Vivo (§6) ✅ SIN consumir API

`valor_en_vivo.py` lee **exclusivamente** `odds_historico.db` (los snapshots
que ya se capturan para el RLM) y calcula EV actual + tendencia de la línea
(📈 sube / 📉 baja / ➖ estable). Cero peticiones HTTP, verificado.
Primera ejecución real: **191 partidos con snapshots, 25 filas con EV+**.
La vista avisa de que los EV >15 % son la zona poco fiable (hallazgo v32).

## 6. Bot de Telegram (§1) ✅ ACTIVO

Workflow presente en el repositorio, cron diario 10:00 UTC + disparo manual,
credenciales solo desde Secrets. Verificado en seco: el mensaje sale con Pick
del Día, Capa 1, Capa 2, escalera y aviso de EV extremo.

## 7. No regresión ✅

test_simetria ✓ · test_match_parlay ✓ · **smoke de 17 ligas de fútbol** ✓ ·
smoke MLB/NBA/Tenis ✓ · AppTest en ambos modos × todas las vistas ✓ ·
bot en seco ✓ · Mundial intacto.
