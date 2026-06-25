# 📈 Momentum Screener

Sistema automatizado de **momentum / fuerza relativa** al estilo Minervini/O'Neil. Escanea diariamente el NYSE + NASDAQ buscando **líderes de mercado** (las acciones más fuertes) en un **punto de entrada de bajo riesgo**: el rebote en la media de 50 sesiones dentro de una tendencia alcista.

El objetivo es **batir al índice** cabalgando a los grandes ganadores, controlando el riesgo con una entrada precisa y un filtro de mercado estricto.

## 📱 Dashboard

`https://0t4c0n.github.io/trading-bot/`

## 🎯 Filosofía de la estrategia

> Comprar **líderes fuertes** en el retroceso a una media móvil en subida, y **dejar correr** a los ganadores con un trailing stop. Pocas operaciones, pero las ganadoras corren mucho.

- **Temporalidad**: gráfico diario (1D)
- **Universo**: NYSE + NASDAQ (solo acciones comunes/ADRs; sin bonos, preferentes, CEF ni SPACs)
- **Frecuencia**: ejecución automática diaria
- **Resultado**: lista de líderes en pullback operables hoy, con entrada, stop y guía de salida

---

## 🧠 Metodología

### 1. Filtro de mercado (eliminatorio)
**Solo se opera si el S&P 500 está sobre su MA200.** En mercado bajista NO se generan picks (a liquidez). El momentum es beta pura: operar en bear dispara el drawdown. El backtest lo confirma — con este filtro el drawdown baja de ~−40% a ~−18%.

### 2. Selección — líderes por fuerza relativa
Una acción es candidata si:
- **RS top 20%**: su retorno a 6 meses está en el percentil ≥80 del universo
- **Tendencia alcista**: `precio > MA50 > MA200`, con MA50 y MA200 al alza
- **Cerca de máximos**: dentro del 25% de su máximo de 52 semanas

### 3. Entrada — rebote en MA50 (bajo riesgo)
El mejor punto de entrada según el estudio (CAGR 13.8%, Sharpe 0.86 vs MA20/MA10/ruptura):
- El precio **retrocede y toca la MA50** en subida (mínimo reciente cerca de la MA50)
- **Rebota**: cierra de nuevo sobre la MA50 y gira al alza

Entrar en el pullback deja el **stop cerca**, así que el riesgo por operación es pequeño aunque la acción sea fuerte.

### 4. Stop y riesgo
- **Stop Loss** = mínimo del retroceso − 0.5×ATR(14)
- Se descartan entradas con **riesgo > 12%**

### 5. Salida — dejar correr (gestión manual)
La salida la gestionas tú con un **trailing stop ~32% bajo el máximo alcanzado**. El backtest mostró que vender en un objetivo fijo capa los runners; dejar correr multiplica ×2.7 la rentabilidad agregada y captura los grandes movimientos.

---

## 📊 Resultados del backtest (cartera, 2020–2025)

Universo ~2.500 acciones, simulación de cartera realista (tamaño por riesgo, salida de mercado, trailing 32%):

| | Estrategia | SPY (comprar y mantener) |
|---|---|---|
| **CAGR** | ~15% | 14.6% |
| **Max Drawdown** | **~−17%** | −34% |
| **Sharpe** | **~0.9** | 0.78 |

**Bate al índice en bruto y en riesgo-ajustado, con la mitad de drawdown.**

> ⚠️ **Caveat honesto**: el backtest tiene sesgo de supervivencia (universo actual, sin acciones quebradas) → resultados optimistas. Es un solo periodo. Antes de operar con dinero real conviene validación out-of-sample.

---

## ⚙️ Componentes

| Archivo | Función |
|---|---|
| `momentum_screener.py` | **Screener diario de producción** (universo → RS → filtro mercado → picks → `docs/data.json`) |
| `momentum_strategy.py` | Lógica de selección + entrada (compartida entre backtest y producción) |
| `market_data.py` | Infraestructura de datos (universo, descarga, salud de mercado) |
| `portfolio_backtest.py` | Motor de backtest de cartera reutilizable (CAGR, drawdown, Sharpe, vs SPY) |
| `run_portfolio_demo.py` | Pipeline completo de backtest (descarga → señales → cartera → informe) |
| `docs/index.html` | Dashboard web (responsive móvil) |
| `.github/workflows/daily-trading-analysis.yml` | Ejecución diaria automática |

---

## 🚀 Uso

### Screener diario (producción)
```bash
pip install -r requirements.txt
python momentum_screener.py        # genera docs/data.json con los picks de hoy
open docs/index.html               # abre el dashboard local
```

### Backtest de cartera
```bash
python run_portfolio_demo.py          # backtest sobre universo demo
python run_portfolio_demo.py --quick  # validación rápida del pipeline
```

### Probar una nueva estrategia
El motor de cartera está **desacoplado**: genera tus señales en formato
`[symbol, date, sl]` y pásalas a `run_portfolio_backtest()` (ver `portfolio_backtest.py`).

### CI/CD (GitHub Actions)
Se ejecuta automáticamente cada día laborable, genera los picks y despliega a GitHub Pages.

---

## 📁 Estructura del JSON de salida

```json
{
  "strategy": "Momentum / Fuerza Relativa (líderes + pullback MA50)",
  "market_context": {
    "healthy": true,
    "status_label": "ALCISTA ✅ — se opera"
  },
  "summary": {
    "total_analyzed": 4200,
    "leaders": 508,
    "picks": 12
  },
  "top_picks": [
    {
      "rank": 1,
      "symbol": "XYZ",
      "price": 131.60,
      "relative_strength": { "rs_rating": 93, "label": "Líder" },
      "trend": { "ma50": 120.28, "ma200": 98.40, "pct_from_52w_high": -12 },
      "risk_management": {
        "entry_price": 131.60,
        "sl": 117.88,
        "risk_pct": 10.4,
        "trailing_stop_pct": 32,
        "exit_strategy": "Dejar correr: trailing stop 32% bajo el máximo"
      }
    }
  ]
}
```

---

## ⚠️ Disclaimer

Herramienta de análisis técnico **educativa**, no constituye recomendación de inversión. El trading implica riesgo de pérdida total. Verifica siempre los setups manualmente antes de operar.
