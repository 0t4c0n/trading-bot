# 🌊 Wyckoff Spring Screener

Sistema automatizado de **Swing Trading Macro** basado en la **Fase C de Wyckoff** combinada con análisis de **Volume Profile (VPVR)**. Escanea diariamente todas las acciones del NYSE + NASDAQ buscando rebotes institucionales en soportes estructurales validados por liquidez.

## 📱 Dashboard

`https://[tu-usuario].github.io/[nombre-repo]/`

## 🎯 Filosofía de la estrategia

> Capturar giros mayores en soportes estructurales de medio/largo plazo, diseñados para mantener operaciones durante **semanas o meses**.

- **Temporalidad única**: gráfico diario (1D)
- **Universo**: NYSE + NASDAQ (~8000 acciones), **excluye penny stocks (<$5)**
- **Frecuencia**: ejecución automática diaria (5h tras cierre US)
- **Resultado**: top 10 setups operables con SL/TP/R:R precisos

---

## 🧠 Metodología (Fase C Wyckoff + VPVR)

### 1. Volume Profile Anual (VPVR)
Calcula el perfil de volumen de las últimas **252 sesiones** (1 año):
- **POC** (Point of Control): nivel de máximo volumen
- **HVN** (High Volume Nodes): zonas con volumen ≥1.5× la media

Estos son los precios donde el dinero institucional ha estado más activo → actúan como imán y soporte/resistencia.

### 2. Soporte Estructural S1
Mínimo más bajo en los **130 días previos a la ventana de búsqueda del Spring**. Es un soporte **establecido**, no el mínimo absoluto del rango (para que el Spring pueda perforarlo).

### 3. Filtro de Confluencia
S1 debe estar **dentro del 1.5%** de un HVN o POC. Score gradual:
- 0–0.5%: 30 pts (perfecta) · 0.5–1.0%: 22 pts (alta) · 1.0–1.5%: 14 pts (válida)

### 4. Spring (Fase C) — últimos 60 días
Vela que cumple **TODAS** las condiciones:
- `Low < S1` (perforación del soporte)
- `Close > S1` (recuperación)
- Cierre en el **tercio superior** del rango (≥67%)
- Volumen **>1.5× SMA(20)** (absorción institucional)

### 5. Validación post-Spring
- ❌ **Spring FALLIDO**: si tras el Spring algún Close < Spring Low → invalidado y excluido
- ⏱️ **Spring CADUCADO**: si pasan >30 días sin Test → señal estancada, excluido

### 6. Test (gatillo de entrada)
Retroceso a la zona de S1 (±0.5%) con:
- Volumen < SMA(20) (oferta agotada)
- Volumen decreciente respecto al día anterior

**Timing ideal**: 5–25 días tras el Spring (max 20 pts en score).

### 7. Filtro de Mercado
Si el **S&P 500 está por debajo de su MA200**, el mercado es bajista y los Springs tienen mucha menor probabilidad. El score de probabilidad cae a 0–4 pts (de 15 posibles), penalizando heavily esas señales.

---

## 📊 Sistema de Scoring Dual (0–100)

### Probabilidad (0–60 pts) — ¿es probable que el rebote ocurra?
| Factor | Pts | Detalle |
|---|---|---|
| Salud del mercado | 0–15 | SPY sobre MA200 + alineación MA50/MA200 |
| Timing del Test | 0–20 | 5–25 días = ideal (20 pts), demás escalado |
| OBV en la base | 0–15 | Pendiente positiva = acumulación silenciosa |
| Ranking industrial | 0–10 | Sector en top 25% = 10 pts, top 50% = 7 pts |

### Potencial (0–40 pts) — ¿cuánto puede subir?
| Factor | Pts | Detalle |
|---|---|---|
| Anchura de base (Wyckoff Cause) | 0–15 | Días en rango S1±20% (causa → efecto) |
| R:R hasta TP2 | 0–15 | R:R ≥4 = 15 pts, ≥3 = 10 pts |
| Profundidad del shake-out | 0–10 | Wick más profundo = más absorción |

**Total = Probabilidad + Potencial**

---

## 🛡️ Gestión de Riesgo

| | Fórmula | Notas |
|---|---|---|
| **Entrada** | S1 × 1.002 | Ligeramente por encima de S1 |
| **Stop Loss** | Spring Low − 0.5×ATR(14) | Margen anti-volatilidad |
| **TP1 (50%)** | Resistencia local 60d previos al Spring | Mover SL a breakeven |
| **TP2 (50%)** | Siguiente HVN superior o R:R 1:3.5 | Dejar correr |

El margen `0.5×ATR(14)` en el SL es **crítico**: añade un buffer proporcional a la volatilidad típica de cada acción, evitando que el ruido normal del mercado active el stop.

---

## ⚙️ Componentes

| Archivo | Función |
|---|---|
| `script_automated.py` | Screener principal (descarga, análisis Wyckoff, save CSV) |
| `create_dashboard_data.py` | Convierte CSV a JSON para el dashboard |
| `debug_stock.py` | Análisis detallado paso a paso de una acción |
| `docs/index.html` | Dashboard web (responsive móvil) |
| `docs/data.json` | Output JSON consumido por el dashboard |
| `.github/workflows/daily-trading-analysis.yml` | Ejecución diaria automática |

---

## 🚀 Uso

### Local
```bash
pip install -r requirements.txt
python script_automated.py        # genera CSVs
python create_dashboard_data.py   # genera docs/data.json
open docs/index.html              # abre dashboard local
```

### Debug de una acción
```bash
# Editar TICKER_TO_DEBUG en debug_stock.py
python debug_stock.py
```

Muestra paso a paso: estado mercado → VPVR → S1 → confluencia → Spring → Test → Riesgo → Score.

### CI/CD (GitHub Actions)
Se ejecuta automáticamente cada día laborable a las 01:00 UTC (5h tras cierre US), genera el análisis completo y despliega a GitHub Pages.

---

## 📁 Estructura del JSON de salida

```json
{
  "market_context": {
    "healthy": true,
    "status_label": "ALCISTA ✅",
    "health_score": 14.3
  },
  "summary": {
    "springs_detected": 12,    // operables (no fallidos ni caducos)
    "springs_failed": 8,        // invalidados
    "springs_stale": 5,         // sin Test >30 días
    "tests_active": 3           // en zona de entrada AHORA
  },
  "top_picks": [
    {
      "rank": 1,
      "symbol": "XYZ",
      "wyckoff_score": 85.5,
      "probability_score": 52.0,
      "potential_score": 33.5,
      "entry_status": { "status": "Test Activo - ENTRADA", "icon": "🎯" },
      "spring": { "date": "2026-05-15", "low": 12.45, "vol_ratio": 2.8 },
      "risk_management": {
        "entry_price": 12.97,
        "sl": 11.83,
        "tp1": 15.40,
        "tp2": 17.82,
        "rr_tp2": 4.2,
        "current_to_sl_pct": 8.5
      }
    }
  ]
}
```

---

## ⚠️ Disclaimer

Herramienta de análisis técnico **educativa**, no constituye recomendación de inversión. El trading implica riesgo de pérdida total. Verifica siempre los setups manualmente antes de operar.
