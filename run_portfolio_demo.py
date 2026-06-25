# run_portfolio_demo.py — Pipeline completo de backtest de cartera (reutilizable)
#
# Descarga datos → genera señales con la estrategia (walk-forward, sin look-ahead)
# → simula la cartera con portfolio_backtest.py → informe vs SPY.
#
# Para probar una NUEVA forma de inversión: reemplaza generate_signals() por tu
# propia lógica (debe devolver un DataFrame [symbol, date, sl]) y reutiliza el resto.
#
# Uso:
#   python run_portfolio_demo.py                 # universo demo (~150 líquidas)
#   python run_portfolio_demo.py --sp500         # S&P 500 (necesita docs/sp500.csv o descarga)
#   python run_portfolio_demo.py --quick         # pocas acciones, para validar el pipeline

import sys
import argparse
import contextlib
import io
import warnings

import numpy as np
import pandas as pd
import yfinance as yf

from script_automated import WyckoffSpringScreener
from portfolio_backtest import run_portfolio_backtest, print_report

warnings.filterwarnings('ignore')

# Universo demo: acciones líquidas y diversas (sustituible)
DEMO_UNIVERSE = [
    'AAPL', 'MSFT', 'NVDA', 'AMD', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AVGO', 'ORCL',
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'COF', 'AXP', 'SCHW',
    'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'UNH', 'ISRG', 'MDT', 'ABT', 'BSX',
    'WMT', 'COST', 'HD', 'NKE', 'SBUX', 'MCD', 'PG', 'KO', 'PEP', 'KHC',
    'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'CAT', 'DE', 'GE', 'HON', 'BA',
    'NEM', 'FCX', 'LIN', 'SHW', 'MLM', 'AMT', 'PLD', 'O', 'SPG', 'EQIX',
]


def download(symbols, start='2019-09-01', end=None):
    """Descarga OHLCV + SPY. Devuelve (dict[sym]->DataFrame, spy_df)."""
    end = end or pd.Timestamp.today().strftime('%Y-%m-%d')
    raw = yf.download(symbols + ['^GSPC'], start=start, end=end, group_by='ticker',
                      auto_adjust=True, progress=False, threads=True)
    data = {}
    for s in symbols:
        try:
            d = raw[s][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            if len(d) > 300:
                data[s] = d
        except Exception:
            pass
    spy = raw['^GSPC'][['Open', 'High', 'Low', 'Close']].dropna()
    return data, spy


def generate_signals(price_data, spy, step=5, warmup=290, fwd_buffer=2):
    """
    Walk-forward: en cada fecha corre la estrategia con datos hasta esa fecha
    (sin look-ahead) y recoge las señales operables. Dedup por (symbol, spring_date).
    Devuelve DataFrame [symbol, date, sl, depth, score] listo para el motor de cartera.
    """
    sc = WyckoffSpringScreener()
    for s in price_data:
        sc.symbol_industries[s] = {'name': s + ' Common Stock', 'industry': 'Unknown', 'sector': 'Unknown'}

    cal = spy.index
    seen, rows = set(), []
    idxs = range(warmup, len(cal) - fwd_buffer, step)
    for ci in idxs:
        T = cal[ci]
        sliced = {s: d[d.index <= T] for s, d in price_data.items()}
        sliced = {s: d for s, d in sliced.items() if len(d) >= 260}
        if len(sliced) < 5:
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            rs = sc.calculate_rs_ratings_from_scores(sc.calculate_all_rs_scores(sliced))
        mh, ms = sc.check_market_health(spy[spy.index <= T])
        for s, d in sliced.items():
            try:
                an = sc.analyze_wyckoff_stock(s, d, float(rs.get(s, 0)),
                                              market_healthy=mh, market_health_score=ms,
                                              industry_rank=50.0)
            except Exception:
                continue
            if not an.get('is_actionable'):
                continue
            sp = an.get('spring_info') or {}
            key = (s, str(sp.get('date', '')))
            if key in seen:
                continue
            seen.add(key)
            rp = an.get('risk_params') or {}
            if not rp.get('sl'):
                continue
            rows.append(dict(symbol=s, date=str(T.date()), sl=rp['sl'],
                             depth=sp.get('spring_depth_pct'), score=an.get('wyckoff_score')))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='Universo mínimo (validar pipeline)')
    ap.add_argument('--start', default='2019-09-01')
    ap.add_argument('--step', type=int, default=5, help='Frecuencia del walk-forward (sesiones)')
    args = ap.parse_args()

    universe = DEMO_UNIVERSE[:12] if args.quick else DEMO_UNIVERSE
    print(f"Descargando {len(universe)} acciones...")
    price_data, spy = download(universe, start=args.start)
    print(f"Con datos: {len(price_data)} | Generando señales (walk-forward)...")
    signals = generate_signals(price_data, spy, step=args.step)
    print(f"Señales: {len(signals)}\n")
    if signals.empty:
        print("Sin señales en este universo/periodo.")
        return
    results = run_portfolio_backtest(signals, price_data, spy)
    print_report(results)


if __name__ == "__main__":
    main()
