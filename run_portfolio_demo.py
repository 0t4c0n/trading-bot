# run_portfolio_demo.py — Pipeline completo de backtest de cartera (reutilizable)
#
# Descarga datos → genera señales con la estrategia (walk-forward, sin look-ahead)
# → simula la cartera con portfolio_backtest.py → informe vs SPY.
#
# Para probar una NUEVA forma de inversión: reemplaza generate_momentum_signals()
# por tu propia lógica (debe devolver un DataFrame [symbol, date, sl]) y reutiliza el resto.
#
# Uso:
#   python run_portfolio_demo.py                 # universo AMPLIO (large/mid-cap por capitalización)
#   python run_portfolio_demo.py --demo          # universo demo (~60 líquidas hand-picked)
#   python run_portfolio_demo.py --quick         # pocas acciones, para validar el pipeline
#   python run_portfolio_demo.py --max 800 --min-cap 1e9   # ajustar tamaño/umbral del universo

import argparse
import time
import warnings

import pandas as pd
import requests
import yfinance as yf

from market_data import is_common_stock
from momentum_strategy import generate_momentum_signals
from portfolio_backtest import run_portfolio_backtest, print_report

warnings.filterwarnings('ignore')

# Universo demo: acciones líquidas y diversas hand-picked (solo para --demo / comparar)
DEMO_UNIVERSE = [
    'AAPL', 'MSFT', 'NVDA', 'AMD', 'GOOGL', 'META', 'AMZN', 'TSLA', 'AVGO', 'ORCL',
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'COF', 'AXP', 'SCHW',
    'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'UNH', 'ISRG', 'MDT', 'ABT', 'BSX',
    'WMT', 'COST', 'HD', 'NKE', 'SBUX', 'MCD', 'PG', 'KO', 'PEP', 'KHC',
    'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'CAT', 'DE', 'GE', 'HON', 'BA',
    'NEM', 'FCX', 'LIN', 'SHW', 'MLM', 'AMT', 'PLD', 'O', 'SPG', 'EQIX',
]


def get_broad_universe(min_market_cap=2e9, max_symbols=500):
    """Universo AMPLIO sin cherry-picking: acciones comunes de NYSE+NASDAQ con
    capitalización ≥ min_market_cap, ordenadas por capitalización y limitadas a
    max_symbols. NO elige nombres a mano — solo pone un suelo de tamaño y deja que
    el filtro de liquidez point-in-time de la estrategia haga el resto.

    CAVEAT: la API devuelve los listados ACTUALES → persiste sesgo de supervivencia
    (faltan las que cotizaban y luego quebraron/deslistaron). Eliminarlo del todo
    exige una base de constituyentes históricos; esto es lo mejor sin ella.
    """
    url = "https://api.nasdaq.com/api/screener/stocks"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    rows = []
    for exch in ('NYSE', 'NASDAQ'):
        try:
            r = requests.get(url, headers=headers,
                             params={'tableonly': 'true', 'limit': '25000', 'exchange': exch},
                             timeout=20)
            if r.status_code == 200:
                rows += r.json()['data']['table']['rows']
        except Exception as e:
            print(f"  ⚠️ Error universo {exch}: {e}")
    cand = []
    for row in rows:
        sym = row.get('symbol', '')
        if not sym or any(ch in sym for ch in '^./'):
            continue
        if not is_common_stock(row.get('name', '') or ''):
            continue
        try:
            mcap = float(str(row.get('marketCap', '0')).replace(',', '') or 0)
        except ValueError:
            mcap = 0.0
        if mcap >= min_market_cap:
            cand.append((sym, mcap))
    cand.sort(key=lambda x: -x[1])
    syms = [s for s, _ in cand[:max_symbols]]
    print(f"Universo amplio: {len(syms)} acciones (cap ≥ ${min_market_cap/1e9:.1f}B, top {max_symbols}).")
    return syms or list(DEMO_UNIVERSE)


def download(symbols, start='2019-09-01', end=None, batch_size=75):
    """Descarga OHLCV (con Open y Volume) + SPY por lotes con reintentos.
    Devuelve (dict[sym]->DataFrame, spy_df)."""
    end = end or pd.Timestamp.today().strftime('%Y-%m-%d')
    data = {}
    n_batches = (len(symbols) + batch_size - 1) // batch_size
    for b in range(n_batches):
        batch = symbols[b * batch_size:(b + 1) * batch_size]
        for attempt in range(3):
            try:
                raw = yf.download(batch, start=start, end=end, group_by='ticker',
                                  auto_adjust=True, progress=False, threads=True)
                for s in batch:
                    try:
                        d = raw[s][['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
                        if len(d) > 300:
                            data[s] = d
                    except Exception:
                        pass
                break
            except Exception:
                time.sleep(5 * (2 ** attempt))
        print(f"  lote {b + 1}/{n_batches} — acumuladas {len(data)} acciones", end='\r')
    print()
    spy = yf.download('^GSPC', start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(spy.columns, pd.MultiIndex):
        spy.columns = spy.columns.droplevel(-1)
    spy = spy[['Open', 'High', 'Low', 'Close']].dropna()
    return data, spy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', action='store_true', help='Universo demo hand-picked (~60)')
    ap.add_argument('--quick', action='store_true', help='Universo mínimo (validar pipeline)')
    ap.add_argument('--start', default='2019-09-01')
    ap.add_argument('--step', type=int, default=5, help='Frecuencia del walk-forward (sesiones)')
    ap.add_argument('--max', type=int, default=500, help='Máx. acciones en el universo amplio')
    ap.add_argument('--min-cap', type=float, default=2e9, help='Capitalización mínima (USD)')
    args = ap.parse_args()

    if args.quick:
        universe = DEMO_UNIVERSE[:12]
    elif args.demo:
        universe = DEMO_UNIVERSE
    else:
        universe = get_broad_universe(min_market_cap=args.min_cap, max_symbols=args.max)

    print(f"Descargando {len(universe)} acciones (desde {args.start})...")
    price_data, spy = download(universe, start=args.start)
    print(f"Con datos: {len(price_data)} | Generando señales momentum (walk-forward)...")

    signals = generate_momentum_signals(price_data, spy, step=args.step)
    # Config validada para momentum: salida de cartera (SPY<MA200→liquidez) + trailing ancho
    cfg = dict(market_filter_ma=200, trailing_pct=0.32)

    print(f"Señales: {len(signals)}\n")
    if signals.empty:
        print("Sin señales en este universo/periodo.")
        return
    results = run_portfolio_backtest(signals, price_data, spy, cfg)
    print_report(results)


if __name__ == "__main__":
    main()
