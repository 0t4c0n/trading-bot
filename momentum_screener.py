# momentum_screener.py — Screener diario de MOMENTUM (producción)
#
# Estrategia (validada por backtest, ver memoria/commits):
#   - SOLO opera en mercado alcista (SPY > MA200). En bear: 0 picks, a liquidez.
#   - Selección: LÍDERES por fuerza relativa (RS top 20%) en tendencia alcista
#     (px > MA50 > MA200, ambas subiendo) y cerca de máximos de 52 semanas.
#   - Entrada de BAJO RIESGO: rebote en la MA50 en subida (stop bajo el mínimo
#     del retroceso − 0.5·ATR). El mejor punto de entrada según el estudio.
#   - Salida (gestión manual): dejar correr con trailing stop ~32% bajo el máximo.
#
# Usa la MISMA lógica de entrada que el backtest (momentum_strategy.evaluate_entry)
# para que producción y backtest operen idénticamente. Reutiliza la infraestructura
# de datos del screener anterior (universo, descarga, salud de mercado).

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from market_data import MarketData
from momentum_strategy import evaluate_entry, DEFAULTS

MOM_LOOKBACK = DEFAULTS['mom_lookback']   # 126 sesiones (6 meses)


def compute_rs_percentile(data, lookback=MOM_LOOKBACK):
    """Fuerza relativa = percentil del retorno a 6 meses sobre el universo."""
    rets = {}
    for s, df in data.items():
        c = df['Close']
        if len(c) > lookback and float(c.iloc[-1 - lookback]) > 0:
            rets[s] = float(c.iloc[-1]) / float(c.iloc[-1 - lookback]) - 1
    if not rets:
        return pd.Series(dtype=float)
    return (pd.Series(rets).rank(pct=True) * 100).round(1)


def find_momentum_picks(data, rs_ratings, market_healthy):
    """Evalúa la entrada de momentum en la última barra de cada acción."""
    picks = []
    if not market_healthy:
        return picks   # mercado bajista → no se opera
    for s, df in data.items():
        try:
            c = df['Close'].values.astype(float)
            h = df['High'].values.astype(float)
            l = df['Low'].values.astype(float)
        except Exception:
            continue
        i = len(c) - 1
        sig = evaluate_entry(c, h, l, i, float(rs_ratings.get(s, 0)), DEFAULTS)
        if sig is None:
            continue
        picks.append(dict(symbol=s, rs=float(rs_ratings.get(s, 0)), **sig))
    # Ranking: líderes más fuertes primero; a igualdad, menor riesgo
    picks.sort(key=lambda p: (-p['rs'], p['risk_pct']))
    return picks


def build_dashboard(picks, market_healthy, market_score, n_universe, n_leaders):
    data = {
        "timestamp": datetime.now().isoformat(),
        "market_date": datetime.now().strftime("%Y-%m-%d"),
        "strategy": "Momentum / Fuerza Relativa (líderes + pullback MA50)",
        "market_context": {
            "healthy": bool(market_healthy),
            "health_score": float(market_score),
            "status_label": "ALCISTA ✅ — se opera" if market_healthy else "BAJISTA ⚠️ — a liquidez",
            "description": "SPY sobre MA200: condiciones para comprar líderes en pullback"
                           if market_healthy else
                           "SPY bajo MA200: NO se opera momentum (riesgo de drawdown). A liquidez.",
        },
        "summary": {
            "total_analyzed": n_universe,
            "leaders": n_leaders,
            "picks": len(picks),
            "message": (f"{len(picks)} líderes en pullback operables hoy "
                        f"(de {n_leaders} líderes / {n_universe} acciones) | "
                        f"Mercado {'alcista ✅' if market_healthy else 'bajista ⚠️ — a liquidez'}"),
        },
        "criteria": {
            "market_filter": "SOLO opera si SPY > MA200 (en bear: 0 picks)",
            "selection": "RS top 20% (retorno 6m) + px>MA50>MA200 (ambas subiendo) + dentro del 25% del máximo 52s",
            "entry": "Rebote en MA50 en subida (retroceso que toca la MA50 y rebota)",
            "stop": "Mínimo del retroceso − 0.5×ATR(14), riesgo ≤ 12%",
            "exit": "Dejar correr: trailing stop ~32% bajo el máximo alcanzado (gestión manual)",
        },
        "top_picks": [],
    }
    for rank, p in enumerate(picks[:20], 1):
        entry = p['entry']
        data["top_picks"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "price": round(entry, 2),
            "relative_strength": {"rs_rating": round(p['rs'], 1),
                                  "label": "Líder fuerte" if p['rs'] >= 90 else "Líder"},
            "trend": {"ma50": p['ma50'], "ma200": p['ma200'],
                      "pct_from_52w_high": p['pct_from_high']},
            "risk_management": {
                "entry_price": round(entry, 2),
                "sl": p['sl'],
                "risk_pct": p['risk_pct'],
                "sl_explanation": "Mínimo del pullback − 0.5×ATR (rebote en MA50)",
                "trailing_stop_pct": p['trailing_stop_pct'],
                "exit_strategy": f"Dejar correr: trailing stop {p['trailing_stop_pct']:.0f}% "
                                 f"bajo el máximo (objetivo: cabalgar al líder)",
            },
        })
    return data


def run_momentum_screener():
    print("=== SCREENER MOMENTUM (líderes + pullback MA50) ===")
    md = MarketData()
    symbols = md.get_universe()
    print(f"Universo: {len(symbols)} acciones. Descargando...")

    data = md.download_all_data(symbols)
    spy = data.pop('_MARKET_INDEX', None)
    print(f"Con datos: {len(data)} acciones")

    market_healthy, market_score = md.check_market_health(spy)
    print(f"Mercado: {'ALCISTA ✅' if market_healthy else 'BAJISTA ⚠️ (a liquidez)'} (score {market_score})")

    rs = compute_rs_percentile(data)
    n_leaders = int((rs >= DEFAULTS['rs_min']).sum())
    picks = find_momentum_picks(data, rs, market_healthy)
    print(f"Líderes (RS≥{DEFAULTS['rs_min']}): {n_leaders} | Picks operables hoy: {len(picks)}")

    # Guardar CSV de picks
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if picks:
        pd.DataFrame(picks).to_csv(f"momentum_picks_{ts}.csv", index=False)

    # Guardar dashboard
    dash = build_dashboard(picks, market_healthy, market_score, len(data), n_leaders)
    os.makedirs('docs', exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    with open('docs/last_update.txt', 'w') as f:
        f.write(datetime.now().isoformat())
    print(f"✅ Dashboard actualizado: docs/data.json ({len(picks)} picks)")
    for p in picks[:10]:
        print(f"  {p['symbol']:<6} RS={p['rs']:.0f}  entry={p['entry']:.2f}  "
              f"SL={p['sl']:.2f}  riesgo={p['risk_pct']:.1f}%  ({p['pct_from_high']:.0f}% del máx)")
    return picks


if __name__ == "__main__":
    run_momentum_screener()
