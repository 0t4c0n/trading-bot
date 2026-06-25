# run_portfolio_demo.py — Pipeline completo de backtest de cartera (reutilizable)
#
# Descarga datos → genera señales con la estrategia (walk-forward, sin look-ahead)
# → simula la cartera con portfolio_backtest.py → informe vs SPY.
#
# Para probar una NUEVA forma de inversión: reemplaza generate_momentum_signals()
# por tu propia lógica (debe devolver un DataFrame [symbol, date, sl]) y reutiliza el resto.
#
# Uso:
#   python run_portfolio_demo.py                 # universo demo (~60 líquidas)
#   python run_portfolio_demo.py --quick         # pocas acciones, para validar el pipeline

import argparse
import warnings

import pandas as pd
import yfinance as yf

from momentum_strategy import generate_momentum_signals
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='Universo mínimo (validar pipeline)')
    ap.add_argument('--start', default='2019-09-01')
    ap.add_argument('--step', type=int, default=5, help='Frecuencia del walk-forward (sesiones)')
    args = ap.parse_args()

    universe = DEMO_UNIVERSE[:12] if args.quick else DEMO_UNIVERSE
    print(f"Descargando {len(universe)} acciones...")
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
