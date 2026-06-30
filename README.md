# 📈 Detector de Líderes — Ruptura Confirmada

Sistema automatizado que escanea diariamente NYSE + NASDAQ buscando **líderes de mercado** (las acciones más fuertes) que acaban de **romper su máximo previo y lo mantienen como soporte**. No es un robot de trading: es un **detector para revisión manual** — saca pocas candidatas de calidad para que tú mires el gráfico y decidas.

Pensado para **position trading**: detectar las pocas empresas excepcionales del año (las "futuras Micron/SanDisk"), entrar poco y **piramidar** si siguen subiendo.

## 📱 Dashboard

`https://0t4c0n.github.io/trading-bot/`

## 🎯 Filosofía

> Comprar **fuerza confirmada**, no adivinar suelos. Una ruptura que ha superado su resistencia y la testea como soporte da una entrada con **stop natural** bajo el soporte real (el mínimo del testeo, o el nivel roto si no hubo retest). Pocas candidatas, revisadas a mano, dejando correr a las ganadoras.

- **Temporalidad**: gráfico diario (1D)
- **Universo**: NYSE + NASDAQ, solo acciones **líquidas** (sin microcaps/chicharros)
- **Frecuencia**: ejecución automática diaria (solo en mercado alcista)
- **Salida del screener**: **top 6 rupturas** + **top 3 pullback** + **top 3 a vigilar**, ordenadas por un score de calidad

---

## 🧠 Metodología

### 1. Filtro de mercado (eliminatorio)
**Solo se busca si el S&P 500 está sobre su MA200.** En mercado bajista NO se generan candidatos. El momentum es beta pura: el backtest confirma que sin salir a liquidez en bear el drawdown se dispara.

### 2. Filtro de liquidez (calidad institucional)
Antes de nada, el universo se recorta a nombres líquidos: **dólar-volumen mediano ≥ $20M/día** y **precio ≥ $10**. Esto elimina microcaps y chicharros que, por su volatilidad, contaminaban el ranking de fuerza relativa.

### 3. Lista PRIMARIA — ruptura confirmada
Una acción entra si cumple **todo**:
- **RS top 10%** (percentil ≥90 del retorno a 6 meses sobre el universo líquido)
- **Tendencia alcista**: `precio > MA50 > MA200`, con ambas medias al alza
- **Ruptura de una BASE real** (no una tendencia continua): el precio ha **consolidado** en un rango tight (≤30% de amplitud) durante ~2 meses, cerca de sus máximos, y **acaba de superar el techo** de esa consolidación. Esto descarta las acciones que llevan meses subiendo sin parar (que trivialmente superan su máximo de hace semanas pero no rompen ninguna resistencia)
- **El nivel aguanta como soporte**: los mínimos recientes no han perdido el techo roto más de ~1×ATR (tolera el barrido/overshoot normal del retest; el cierre sigue exigiéndose sobre el nivel)
- **No extendida**: el precio está a **≤12% sobre la MA50**. En líderes volátiles el soporte fiable es la MA50, no el máximo roto; si el precio entra muy arriba, el stop al nivel roto queda dentro del hueco hasta la MA50 y un retroceso normal lo barre (casos SNEX/AMKR/LLY)
- **Fresca**: el último mes (r1m) sigue subiendo → descarta rupturas viejas ya girándose
- **Rentable**: se descartan empresas con margen neto ≤ 0
- **No cripto-directo**: fuera mineras de bitcoin, tesorerías cripto y exchanges (volátiles y con riesgo regulatorio); se mantienen las de tecnología blockchain

### 4. Stop y riesgo
- **Stop Loss** = soporte real − 0.5×ATR(14), donde el soporte real es **el más bajo entre el mínimo del testeo/barrido y el nivel roto**. Si hubo barrido, el stop va bajo el mínimo del barrido (no bajo la resistencia, que se suele perforar un poco); si no hubo retest, va bajo el nivel roto
- Se descartan entradas con **riesgo > 12%** (esto mismo elimina las rupturas ya extendidas)

### 5. Ranking — score de calidad 0-100
Las rupturas se ordenan por un score **transparente** (no predice ganadores; ordena calidad de setup para tu triaje):

| Componente | Peso |
|---|---|
| Fuerza relativa (RS) | 35 |
| Fundamental (rentable + crecimiento ventas/EPS) | 20 |
| Volumen en la ruptura (vol 10/50) | 15 |
| Momentum 6m | 10 |
| Retest confirmado | 10 |
| Frescura (r1m) | 10 |

> El score **no premia el SL pequeño**: el backtest mostró que premiar bajo riesgo es contraproducente (el tramo <4% de riesgo es el que peor rinde), y el cap de extensión ya acota la distancia al soporte. Esos puntos van a la RS, lo único que el backtest vio ordenar (débilmente) el retorno futuro.

Cada candidata se enriquece con datos de yfinance (sector, margen, crecimiento, recomendación de analistas, precio objetivo y **aviso de earnings ≤7 días**).

### 6. Lista SECUNDARIA — pullback a MA50
Como apoyo, los líderes (RS top 20%) en rebote sobre la MA50 en subida (entrada de bajo riesgo clásica).

### 7. Lista A VIGILAR — en testeo (radar, no accionable)
El hueco entre la ruptura y el pullback: un líder (RS top 10%) que **hizo máximos recientes y ha retrocedido** desde ellos, pero **sigue por encima de la MA50** y aún no la ha testeado, y **ya está cerca de la zona de testeo** (≤12% sobre la MA50, para que sea zona de decisión y no un cohete aún extendido). No lleva stop/entrada: es para **vigilar las próximas sesiones** y ver si rebota (→ posible ruptura, momento de entrar) o cae hasta la MA50 (→ aparece en la lista de pullback). Evita perseguir la acción el día que se dispara.

### 8. Salida — dejar correr (gestión manual)
La gestionas tú con un trailing stop ancho (~32% bajo el máximo). Empezar poco y piramidar si la acción sigue subiendo.

---

## 📊 ¿Bate al índice? — la verdad honesta

**No, el momentum mecánico no bate al SPY sobre el universo real.** Un backtest de cartera riguroso (universo amplio por capitalización, liquidez point-in-time, 2019-2025) da **CAGR ~+6% base / ~+11% afinado vs +14.6% del SPY**. Las cifras optimistas de versiones antiguas venían de un universo cherry-picked de supervivientes.

Lo único robusto del backtest: (1) el **filtro de liquidez** era imprescindible; (2) el **filtro de mercado (MA200)** protege de verdad en bear (2022 verificado: capital intacto vs SPY −20%).

**Por eso esto NO es un robot, es un detector.** El valor está en tu criterio sobre las pocas candidatas limpias que el filtro deja, no en operar una cesta mecánica. Se usa para el ~10% de la cartera; el resto, indexado.

> ⚠️ Persiste sesgo de supervivencia (listados actuales, sin delisted) → backtest aún optimista.

---

## ⚙️ Componentes

| Archivo | Función |
|---|---|
| `momentum_screener.py` | **Screener diario** (universo → liquidez → RS → rupturas + pullback → score → `docs/data.json`) |
| `momentum_strategy.py` | Lógica de detección: `evaluate_breakout` (ruptura), `evaluate_entry` (pullback), `evaluate_watch` (a vigilar), `DEFAULTS` |
| `market_data.py` | Datos: universo, descarga, salud de mercado, liquidez, enriquecimiento yfinance (cripto/fundamentales) |
| `portfolio_backtest.py` | Motor de backtest de cartera reutilizable (CAGR, drawdown, Sharpe, vs SPY) |
| `run_portfolio_demo.py` | Pipeline de backtest (universo amplio por capitalización → señales → cartera → informe) |
| `docs/index.html` | Dashboard web (responsive móvil) |
| `.github/workflows/daily-trading-analysis.yml` | Ejecución diaria automática |

---

## 🚀 Uso

```bash
pip install -r requirements.txt
python momentum_screener.py        # genera docs/data.json (top 6 rupturas + top 3 pullback + top 3 a vigilar)
open docs/index.html               # dashboard local

# Backtest (validación honesta sobre universo amplio)
python run_portfolio_demo.py            # universo amplio por capitalización
python run_portfolio_demo.py --demo     # universo demo (~60 nombres)
python run_portfolio_demo.py --quick    # validación rápida del pipeline
```

Probar otra estrategia: el motor de cartera está **desacoplado** — genera señales `[symbol, date, sl]` y pásalas a `run_portfolio_backtest()`.

---

## 📁 Estructura del JSON de salida

```json
{
  "strategy": "Detector de líderes — ruptura de máximos confirmada (position trading)",
  "market_context": { "healthy": true, "status_label": "ALCISTA ✅ — se busca" },
  "summary": { "total_analyzed": 1655, "leaders": 330, "picks": 6 },
  "breakouts": [
    {
      "rank": 1, "symbol": "XYZ", "score": 78.8, "price": 100.0,
      "rs_rating": 95, "mom6m": 120, "r1m": 8, "retested": true,
      "breakout_level": 94.0, "pct_above_breakout": 6.4, "pct_from_52w_high": -2,
      "sl": 92.0, "risk_pct": 8.0,
      "volume": { "ratio_10_50": 1.3, "label": "confirma ✅" }, "rsi": 62,
      "sector": "Technology",
      "fundamentals": {
        "profit_margin_pct": 18, "rev_growth_pct": 25, "eps_growth_pct": 40,
        "analyst_rating": "strong_buy", "target_upside_pct": 20
      },
      "earnings_flag": "⚠️ resultados en 3 días"
    }
  ],
  "pullbacks": [ { "rank": 1, "symbol": "ABC", "rs_rating": 92, "...": "..." } ],
  "watch": [ { "rank": 1, "symbol": "LLY", "rs_rating": 97, "recent_high": 1183, "pct_from_recent_high": -6.4, "ext_ma50_pct": 9, "ma50": 1010, "...": "..." } ]
}
```

---

## ⚠️ Disclaimer

Herramienta de análisis técnico **educativa**, no constituye recomendación de inversión. Las candidatas son puntos de partida para tu revisión manual, no compras automáticas. El trading implica riesgo de pérdida total. Verifica siempre los setups manualmente antes de operar.
