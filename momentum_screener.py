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
from momentum_strategy import evaluate_entry, evaluate_breakout, DEFAULTS

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
        # Fuerza bruta del momentum (retorno 6m) para el ranking — es lo único que
        # ordena (muy débilmente) mejor el retorno futuro. NO se usa el riesgo: el
        # backtest mostró que premiar bajo riesgo es contraproducente (el tramo <4%
        # de riesgo es el que peor rinde).
        mom6m = (c[i] / c[i - MOM_LOOKBACK] - 1) * 100 if c[i - MOM_LOOKBACK] > 0 else 0.0
        picks.append(dict(symbol=s, rs=float(rs_ratings.get(s, 0)), mom6m=round(mom6m, 1), **sig))
    # Ranking por fuerza de momentum. AVISO: ninguna feature predice fiablemente al
    # runner (correlaciones ≈0); el orden es casi cosmético. El edge está en operar
    # una CESTA diversificada de los top y dejar correr, no en clavar el #1.
    picks.sort(key=lambda p: -p['mom6m'])
    return picks


def find_breakouts(data, rs_ratings, market_healthy):
    """Lista PRIMARIA: líderes con RUPTURA confirmada de su resistencia (máximo previo),
    que la mantienen como soporte, con stop natural ≤12% bajo el nivel roto. Position
    trading: comprar fuerza confirmada para revisar a mano y, si sigue, piramidar."""
    out = []
    if not market_healthy:
        return out
    for s, df in data.items():
        try:
            c = df['Close'].values.astype(float)
            h = df['High'].values.astype(float)
            l = df['Low'].values.astype(float)
        except Exception:
            continue
        i = len(c) - 1
        sig = evaluate_breakout(c, h, l, i, float(rs_ratings.get(s, 0)), DEFAULTS)
        if sig is None:
            continue
        mom6m = (c[i] / c[i - MOM_LOOKBACK] - 1) * 100 if c[i - MOM_LOOKBACK] > 0 else 0.0
        out.append(dict(symbol=s, rs=float(rs_ratings.get(s, 0)), mom6m=round(mom6m, 1), **sig))
    # Ranking: primero las que ya retestearon (entrada de menor riesgo) y, dentro de
    # cada grupo, por fuerza relativa. Tú eliges a mano dentro de las que salgan.
    out.sort(key=lambda x: (not x['retested'], -x['rs']))
    return out


def build_dashboard(breakouts, pullbacks, market_healthy, market_score, n_universe, n_leaders):
    data = {
        "timestamp": datetime.now().isoformat(),
        "market_date": datetime.now().strftime("%Y-%m-%d"),
        "strategy": "Detector de líderes — ruptura de máximos confirmada (position trading)",
        "market_context": {
            "healthy": bool(market_healthy),
            "health_score": float(market_score),
            "status_label": "ALCISTA ✅ — se busca" if market_healthy else "BAJISTA ⚠️ — a liquidez",
            "description": "SPY sobre MA200: condiciones para cazar líderes con ruptura"
                           if market_healthy else
                           "SPY bajo MA200: NO se busca (riesgo de drawdown). A liquidez / indexado.",
        },
        "summary": {
            "total_analyzed": n_universe,
            "leaders": n_leaders,
            "picks": len(breakouts),
            "message": (f"{len(breakouts)} rupturas confirmadas + {len(pullbacks)} en pullback "
                        f"(de {n_leaders} líderes / {n_universe} líquidas) | "
                        f"Mercado {'alcista ✅' if market_healthy else 'bajista ⚠️ — a liquidez'}"),
        },
        "criteria": {
            "market_filter": "SOLO se busca si SPY > MA200 (en bear: 0 candidatos)",
            "liquidity": (f"Universo filtrado a nombres líquidos: dólar-volumen mediano "
                          f"≥ ${DEFAULTS['min_dollar_vol']/1e6:.0f}M/día y precio "
                          f"≥ ${DEFAULTS['min_price']:.0f} (fuera microcaps/chicharros)"),
            "selection": (f"PRIMARIO: RS top 10% (≥{DEFAULTS['breakout_rs_min']}) + px>MA50>MA200 "
                          f"(ambas subiendo) + RUPTURA del máximo previo (52s) que aguanta como soporte"),
            "exclusions": "Fuera cripto-directo (mineras / tesorerías bitcoin / exchanges) por volatilidad y riesgo regulatorio; se mantienen las de tecnología blockchain",
            "entry": "Comprar la fuerza confirmada; empezar poco y piramidar si sigue subiendo",
            "stop": f"Justo bajo el nivel roto (ahora soporte) − 0.5×ATR(14), riesgo ≤ {DEFAULTS['max_risk_pct']*100:.0f}%",
            "exit": "Dejar correr: trailing stop ~32% bajo el máximo alcanzado (gestión manual)",
            "secondary": "SECUNDARIO: líderes (RS top 20%) en rebote sobre la MA50 (entrada de bajo riesgo)",
        },
        "breakouts": [],
        "pullbacks": [],
    }
    for rank, p in enumerate(breakouts, 1):
        data["breakouts"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "price": round(p['entry'], 2),
            "rs_rating": round(p['rs'], 1),
            "mom6m": p['mom6m'],
            "retested": p['retested'],
            "breakout_level": p['breakout_level'],
            "pct_above_breakout": p['pct_above_breakout'],
            "pct_from_52w_high": p['pct_from_high'],
            "ma50": p['ma50'],
            "ma200": p['ma200'],
            "sl": p['sl'],
            "risk_pct": p['risk_pct'],
            "note": ("Retest del nivel roto OK — soporte confirmado (entrada de bajo riesgo)"
                     if p['retested'] else
                     "Ruptura clara, aún sin retest — entrar a medias o esperar retest"),
            "sl_explanation": "Stop justo bajo el máximo roto (ahora soporte) − 0.5×ATR",
        })
    for rank, p in enumerate(pullbacks[:5], 1):
        data["pullbacks"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "price": round(p['entry'], 2),
            "rs_rating": round(p['rs'], 1),
            "mom6m": p['mom6m'],
            "pct_from_52w_high": p['pct_from_high'],
            "ma50": p['ma50'],
            "ma200": p['ma200'],
            "sl": p['sl'],
            "risk_pct": p['risk_pct'],
            "note": "Rebote en la MA50 en subida (entrada de bajo riesgo)",
            "sl_explanation": "Mínimo del pullback − 0.5×ATR (rebote en MA50)",
        })
    return data


def run_momentum_screener():
    print("=== DETECTOR DE LÍDERES (ruptura confirmada + pullback MA50) ===")
    md = MarketData()
    symbols = md.get_universe()
    print(f"Universo: {len(symbols)} acciones. Descargando...")

    data = md.download_all_data(symbols)
    spy = data.pop('_MARKET_INDEX', None)
    print(f"Con datos: {len(data)} acciones")

    # Filtro de liquidez ANTES del RS: que el percentil de fuerza relativa se calcule
    # entre nombres institucionales, no contra microcaps que 'pop'ean una vez.
    liquid = set(md.liquid_symbols(data, min_dollar_vol=DEFAULTS['min_dollar_vol'],
                                   min_price=DEFAULTS['min_price'], window=DEFAULTS['liq_window']))
    n_universe_raw = len(data)
    data = {s: df for s, df in data.items() if s in liquid}
    print(f"Líquidas (≥${DEFAULTS['min_dollar_vol']/1e6:.0f}M/día mediana, "
          f">${DEFAULTS['min_price']:.0f}): {len(data)} (de {n_universe_raw})")

    market_healthy, market_score = md.check_market_health(spy)
    print(f"Mercado: {'ALCISTA ✅' if market_healthy else 'BAJISTA ⚠️ (a liquidez)'} (score {market_score})")

    rs = compute_rs_percentile(data)
    n_leaders = int((rs >= DEFAULTS['rs_min']).sum())
    breakouts = find_breakouts(data, rs, market_healthy)
    pullbacks = find_momentum_picks(data, rs, market_healthy)

    # Excluir cripto-DIRECTO (mineras / tesorerías bitcoin / exchanges): muy volátil y con
    # riesgo regulatorio. Se mantienen las de tecnología blockchain. Solo se consulta la
    # descripción de los candidatos finales (barato), no de todo el universo.
    cand = {p['symbol'] for p in breakouts} | {p['symbol'] for p in pullbacks}
    crypto = md.crypto_direct_symbols(cand) if cand else set()
    if crypto:
        breakouts = [p for p in breakouts if p['symbol'] not in crypto]
        pullbacks = [p for p in pullbacks if p['symbol'] not in crypto]
        print(f"Excluidas cripto-directo: {sorted(crypto)}")

    print(f"Líderes (RS≥{DEFAULTS['rs_min']}): {n_leaders} | "
          f"Rupturas confirmadas (RS≥{DEFAULTS['breakout_rs_min']}): {len(breakouts)} | "
          f"Pullback MA50: {len(pullbacks)}")

    # Guardar CSV de rupturas (lista primaria)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if breakouts:
        pd.DataFrame(breakouts).to_csv(f"momentum_breakouts_{ts}.csv", index=False)

    # Guardar dashboard
    dash = build_dashboard(breakouts, pullbacks, market_healthy, market_score, len(data), n_leaders)
    os.makedirs('docs', exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    with open('docs/last_update.txt', 'w') as f:
        f.write(datetime.now().isoformat())
    print(f"✅ Dashboard actualizado: docs/data.json ({len(breakouts)} rupturas)")
    for p in breakouts[:10]:
        tag = "retest✓" if p['retested'] else "sin retest"
        print(f"  {p['symbol']:<6} RS={p['rs']:.0f}  px={p['entry']:.2f}  "
              f"ruptura={p['breakout_level']:.2f} (+{p['pct_above_breakout']:.1f}%)  "
              f"SL={p['sl']:.2f}  riesgo={p['risk_pct']:.1f}%  {tag}")
    return breakouts


if __name__ == "__main__":
    run_momentum_screener()
