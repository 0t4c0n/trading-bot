# momentum_screener.py — Detector diario de líderes (producción)
#
# Flujo:
#   - SOLO busca en mercado alcista (SPY > MA200). En bear: 0 candidatos, a liquidez.
#   - Filtra el universo a nombres LÍQUIDOS (dólar-vol mediano ≥$20M, precio ≥$10).
#   - Calcula la fuerza relativa (RS) sobre ese universo líquido.
#   - Lista PRIMARIA (find_breakouts → evaluate_breakout): RS top 10% con RUPTURA
#     confirmada del máximo previo que aguanta como soporte; stop bajo el nivel roto,
#     riesgo ≤12%, fresca (r1m>0). Enriquece con yfinance (cripto/fundamentales/sector/
#     earnings), descarta cripto-directo y no rentables, y ORDENA por un score 0-100.
#   - Lista SECUNDARIA (find_momentum_picks → evaluate_entry): pullback a la MA50.
#   - Salida (gestión manual): dejar correr con trailing stop ~32% bajo el máximo.
#
# Genera docs/data.json con top MAX_BREAKOUTS rupturas + top MAX_PULLBACKS pullback.
# Es un DETECTOR para revisión manual (position trading), no un robot — ver README.

import json
import os
import time
from datetime import datetime

import numpy as np
import pandas as pd

from market_data import MarketData
from momentum_strategy import evaluate_entry, evaluate_breakout, evaluate_watch, DEFAULTS

MOM_LOOKBACK = DEFAULTS['mom_lookback']   # 126 sesiones (6 meses)
MAX_BREAKOUTS = 6   # tope de la lista primaria (rápido de revisar; el resto en el CSV)
MAX_PULLBACKS = 3   # tope de la lista secundaria
MAX_WATCH = 3       # tope de la lista 'a vigilar / en testeo' (mismo nº que pullback)


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


def find_watch(data, rs_ratings, market_healthy):
    """Lista 'A VIGILAR / EN TESTEO' (radar): líderes que hicieron máximos recientes y han
    RETROCEDIDO desde ellos pero siguen sobre la MA50 — el paso PREVIO a la entrada. No
    son accionables (sin stop): se vigila si rebotan (→ posible ruptura) o caen al testeo
    de la MA50 (→ pullback). Captura el hueco que ni ruptura ni pullback ven todavía."""
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
        sig = evaluate_watch(c, h, l, i, float(rs_ratings.get(s, 0)), DEFAULTS)
        if sig is None:
            continue
        mom6m = (c[i] / c[i - MOM_LOOKBACK] - 1) * 100 if c[i - MOM_LOOKBACK] > 0 else 0.0
        out.append(dict(symbol=s, rs=float(rs_ratings.get(s, 0)), mom6m=round(mom6m, 1), **sig))
    # Ranking por fuerza relativa (el candidato de vigilancia de mayor calidad primero).
    out.sort(key=lambda p: (-p['rs'], -p['mom6m']))
    return out


def _rsi(c, n=14):
    d = np.diff(c)
    up = np.clip(d, 0, None)
    dn = -np.clip(d, None, 0)
    ru = pd.Series(up).ewm(alpha=1 / n, adjust=False).mean().iloc[-1]
    rd = pd.Series(dn).ewm(alpha=1 / n, adjust=False).mean().iloc[-1]
    return 100.0 if rd == 0 else float(100 - 100 / (1 + ru / rd))


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
            v = df['Volume'].values.astype(float)
        except Exception:
            continue
        i = len(c) - 1
        sig = evaluate_breakout(c, h, l, i, float(rs_ratings.get(s, 0)), DEFAULTS)
        if sig is None:
            continue
        mom6m = (c[i] / c[i - MOM_LOOKBACK] - 1) * 100 if c[i - MOM_LOOKBACK] > 0 else 0.0
        # Volumen: media 10 sesiones / media 50 → >1 = la ruptura sube con interés.
        vol_ratio = (v[-10:].mean() / v[-50:].mean()) if len(v) >= 50 and v[-50:].mean() > 0 else 1.0
        out.append(dict(symbol=s, rs=float(rs_ratings.get(s, 0)), mom6m=round(mom6m, 1),
                        vol_ratio=round(float(vol_ratio), 2), rsi=round(_rsi(c), 0), **sig))
    return out   # el orden definitivo (por score) se asigna en run, con los fundamentales


def _clip01(x):
    return max(0.0, min(1.0, x))


def score_breakout(p):
    """Score 0-100 TRANSPARENTE para ordenar (no predice ganadores: ordena calidad de
    setup + convicción + fundamental para el triaje manual). Pesos: RS 35, fundamental
    20, volumen 15, momentum 10, retest 10, frescura r1m 10.

    NO premia el riesgo/SL pequeño: el backtest mostró que premiar bajo riesgo es
    contraproducente (el tramo <4% de riesgo es el que peor rinde) — igual que ya hace la
    lista de pullback. Además el cap de extensión sobre la MA50 ya acota la distancia al
    soporte de forma estructural, así que no hay que ordenarlo también aquí. Esos 10 pts
    fueron a RS (25→35), lo único que el backtest vio ordenar (débilmente) el retorno."""
    rs = _clip01((p['rs'] - 80) / 20)                       # RS 80→0, 100→1
    mom = _clip01(p['mom6m'] / 150)                          # momentum 6m, cap 150%
    vol = _clip01((p.get('vol_ratio', 1.0) - 0.8) / 0.6)    # vol10/50: 0.8→0, 1.4→1
    rete = 1.0 if p['retested'] else 0.0
    fresh = _clip01(p.get('r1m', 0) / 10)                    # r1m ≥10% → 1
    margin, revg, epsg = p.get('margin'), p.get('revg'), p.get('epsg')
    f_prof = 1.0 if (margin is not None and margin > 0) else (0.5 if margin is None else 0.0)
    f_rev = _clip01((revg or 0) / 0.30) if revg is not None else 0.5
    f_eps = _clip01((epsg or 0) / 0.50) if epsg is not None else 0.5
    fund = f_prof * 0.5 + f_rev * 0.25 + f_eps * 0.25
    return round(35 * rs + 10 * mom + 15 * vol + 10 * rete + 10 * fresh + 20 * fund, 1)


def build_dashboard(breakouts, pullbacks, watch, market_healthy, market_score, n_universe, n_leaders):
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
            "message": (f"Top {min(len(breakouts), MAX_BREAKOUTS)} rupturas (de {len(breakouts)}) + "
                        f"{min(len(pullbacks), MAX_PULLBACKS)} en pullback (de {len(pullbacks)}) + "
                        f"{min(len(watch), MAX_WATCH)} a vigilar (de {len(watch)}) | "
                        f"{n_leaders} líderes / {n_universe} líquidas | "
                        f"Mercado {'alcista ✅' if market_healthy else 'bajista ⚠️ — a liquidez'}"),
        },
        "criteria": {
            "market_filter": "SOLO se busca si SPY > MA200 (en bear: 0 candidatos)",
            "liquidity": (f"Universo filtrado a nombres líquidos: dólar-volumen mediano "
                          f"≥ ${DEFAULTS['min_dollar_vol']/1e6:.0f}M/día y precio "
                          f"≥ ${DEFAULTS['min_price']:.0f} (fuera microcaps/chicharros)"),
            "selection": (f"PRIMARIO: RS top 10% (≥{DEFAULTS['breakout_rs_min']}) + px>MA50>MA200 "
                          f"(ambas subiendo) + RUPTURA del máximo previo (52s) que aguanta como soporte, "
                          f"y NO extendida: precio ≤{DEFAULTS['breakout_max_ext_ma50']*100:.0f}% sobre la MA50 "
                          f"(en líderes volátiles el soporte real es la MA50, no el máximo roto)"),
            "exclusions": "Fuera cripto-directo (mineras / tesorerías bitcoin / exchanges) por volatilidad y riesgo regulatorio; se mantienen las de tecnología blockchain",
            "entry": "Comprar la fuerza confirmada; empezar poco y piramidar si sigue subiendo",
            "stop": f"Bajo el soporte real (mínimo del testeo/barrido o nivel roto, el más bajo) − 0.5×ATR(14), riesgo ≤ {DEFAULTS['max_risk_pct']*100:.0f}%",
            "exit": "Dejar correr: trailing stop ~32% bajo el máximo alcanzado (gestión manual)",
            "secondary": "SECUNDARIO: líderes (RS top 20%) en rebote sobre la MA50 (entrada de bajo riesgo)",
            "watch": ("A VIGILAR / EN TESTEO: líder (RS top 10%) que hizo máximos recientes y ha "
                      "retrocedido desde ellos pero sigue sobre la MA50. NO accionable (sin stop): "
                      "vigilar si rebota (→ posible ruptura) o cae a la MA50 (→ pullback)"),
        },
        "breakouts": [],
        "pullbacks": [],
        "watch": [],
    }
    for rank, p in enumerate(breakouts[:MAX_BREAKOUTS], 1):
        vr = p.get('vol_ratio', 1.0)
        vol_label = "confirma ✅" if vr >= 1.1 else ("flojo ⚠️" if vr < 0.9 else "neutro")
        ed = p.get('earnings_days')
        earnings_flag = (f"⚠️ resultados en {ed} días" if ed is not None and 0 <= ed <= 7 else None)
        tgt, px = p.get('target'), p['entry']
        data["breakouts"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "name": p.get('name') or p['symbol'],
            "score": p.get('score'),
            "price": round(px, 2),
            "rs_rating": round(p['rs'], 1),
            "mom6m": p['mom6m'],
            "r1m": p.get('r1m'),
            "retested": p['retested'],
            "breakout_level": p['breakout_level'],
            "pct_above_breakout": p['pct_above_breakout'],
            "pct_from_52w_high": p['pct_from_high'],
            "ma50": p['ma50'],
            "ma200": p['ma200'],
            "sl": p['sl'],
            "risk_pct": p['risk_pct'],
            "volume": {"ratio_10_50": vr, "label": vol_label},
            "rsi": p.get('rsi'),
            "sector": p.get('sector') or "—",
            "fundamentals": {
                "profit_margin_pct": round(p['margin'] * 100, 1) if p.get('margin') is not None else None,
                "rev_growth_pct": round(p['revg'] * 100, 0) if p.get('revg') is not None else None,
                "eps_growth_pct": round(p['epsg'] * 100, 0) if p.get('epsg') is not None else None,
                "analyst_rating": p.get('rating'),
                "target_upside_pct": round((tgt / px - 1) * 100, 0) if tgt else None,
            },
            "earnings_flag": earnings_flag,
            "note": ("Retest del nivel roto OK — soporte confirmado (entrada de bajo riesgo)"
                     if p['retested'] else
                     "Ruptura clara, aún sin retest — entrar a medias o esperar retest"),
            "sl_explanation": "Stop bajo el soporte real: el mínimo del testeo/barrido (o el nivel roto si no hubo retest), − 0.5×ATR",
        })
    for rank, p in enumerate(pullbacks[:MAX_PULLBACKS], 1):
        data["pullbacks"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "name": p.get('name') or p['symbol'],
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
    for rank, p in enumerate(watch[:MAX_WATCH], 1):
        data["watch"].append({
            "rank": rank,
            "symbol": p['symbol'],
            "name": p.get('name') or p['symbol'],
            "price": round(p['entry'], 2),
            "rs_rating": round(p['rs'], 1),
            "mom6m": p['mom6m'],
            "recent_high": p['recent_high'],
            "pct_from_recent_high": p['pct_from_recent_high'],
            "pct_from_52w_high": p['pct_from_high'],
            "ext_ma50_pct": p['ext_ma50_pct'],
            "ma50": p['ma50'],
            "ma200": p['ma200'],
            "sector": p.get('sector') or "—",
            "note": ("Retrocede desde máximos; aún sobre la MA50. Vigilar próximas sesiones: "
                     "si REBOTA → posible entrada de ruptura; si cae a la MA50 → pullback de bajo riesgo"),
            "watch_zone": ("Entrada ideal: rebote confirmado cerca de la zona de testeo o de la MA50 "
                           f"(${p['ma50']:.0f}); NO perseguir el día que se dispara"),
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
    watch = find_watch(data, rs, market_healthy)

    # Enriquecer SOLO los candidatos finales con yfinance (una llamada por símbolo):
    # cripto-directo, sector, margen, crecimiento, recomendación, objetivo y earnings.
    cand = sorted({p['symbol'] for p in breakouts} | {p['symbol'] for p in pullbacks}
                  | {p['symbol'] for p in watch[:MAX_WATCH]})
    if cand:
        time.sleep(15)   # dejar respirar a Yahoo tras la descarga masiva antes de pedir .info
    enrich = md.enrich_candidates(cand) if cand else {}

    def keep(p):
        e = enrich.get(p['symbol'], {})
        if e.get('is_crypto'):
            return False                         # fuera cripto-directo (mineras, etc.)
        m = e.get('margin')
        if m is not None and m <= 0:             # gate fundamental: fuera no rentables
            return False
        return True

    crypto = sorted(s for s, e in enrich.items() if e.get('is_crypto'))
    unprof = sorted(s for s, e in enrich.items()
                    if not e.get('is_crypto') and e.get('margin') is not None and e['margin'] <= 0)
    breakouts = [p for p in breakouts if keep(p)]
    pullbacks = [p for p in pullbacks if keep(p)]
    # El radar no repite un nombre que ya es accionable hoy (ruptura o pullback).
    actionable = {p['symbol'] for p in breakouts} | {p['symbol'] for p in pullbacks}
    watch = [p for p in watch if keep(p) and p['symbol'] not in actionable]
    if crypto:
        print(f"Excluidas cripto-directo: {crypto}")
    if unprof:
        print(f"Excluidas no rentables: {unprof}")

    # Adjuntar fundamentales + score y ORDENAR las rupturas por score (calidad de setup).
    for p in breakouts + pullbacks + watch:
        e = enrich.get(p['symbol'], {})
        p['name'] = e.get('name')
        p['sector'] = e.get('sector')
        p['margin'] = e.get('margin')
        p['revg'] = e.get('revg')
        p['epsg'] = e.get('epsg')
        p['rating'] = e.get('rating')
        p['target'] = e.get('target')
        p['earnings_days'] = e.get('earnings_days')
    for p in breakouts:
        p['score'] = score_breakout(p)
    breakouts.sort(key=lambda x: -x['score'])

    print(f"Líderes (RS≥{DEFAULTS['rs_min']}): {n_leaders} | "
          f"Rupturas confirmadas (RS≥{DEFAULTS['breakout_rs_min']}): {len(breakouts)} | "
          f"Pullback MA50: {len(pullbacks)} | A vigilar (testeo): {len(watch)}")

    # Guardar CSV de rupturas (lista primaria)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if breakouts:
        pd.DataFrame(breakouts).to_csv(f"momentum_breakouts_{ts}.csv", index=False)

    # Guardar dashboard
    dash = build_dashboard(breakouts, pullbacks, watch, market_healthy, market_score, len(data), n_leaders)
    os.makedirs('docs', exist_ok=True)
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    with open('docs/last_update.txt', 'w') as f:
        f.write(datetime.now().isoformat())
    print(f"✅ Dashboard actualizado: docs/data.json ({len(breakouts)} rupturas)")
    for p in breakouts[:12]:
        tag = "retest✓" if p['retested'] else "sin retest"
        print(f"  score={p['score']:5.1f}  {p['symbol']:<6} RS={p['rs']:.0f}  "
              f"mom6m={p['mom6m']:.0f}%  vol={p['vol_ratio']:.2f}  riesgo={p['risk_pct']:.1f}%  "
              f"r1m={p.get('r1m',0):.0f}%  {p.get('sector') or '—':<14} {tag}")
    return breakouts


if __name__ == "__main__":
    run_momentum_screener()
