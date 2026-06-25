# portfolio_backtest.py — Motor de backtest de CARTERA reutilizable
#
# Separa la GENERACIÓN DE SEÑALES (la estrategia) de la SIMULACIÓN DE CAPITAL.
# Cualquier estrategia futura solo tiene que producir un DataFrame de señales con
# columnas: symbol, date (fecha de señal), sl (stop loss inicial). El motor:
#   - entra en la apertura del día siguiente a la señal,
#   - dimensiona la posición por riesgo (% de equity arriesgado hasta el SL),
#   - respeta un nº máximo de posiciones simultáneas y un tope por posición,
#   - gestiona la salida con trailing stop (configurable),
#   - calcula curva de equity, CAGR, max drawdown, Sharpe, exposición,
#   - y compara contra comprar-y-mantener SPY sobre el mismo capital y periodo.
#
# Para probar una NUEVA forma de inversión: genera tus señales (con la lógica que
# sea) en ese formato y llama a run_portfolio_backtest(). El motor no sabe ni le
# importa cómo se generaron.

import numpy as np
import pandas as pd


DEFAULT_CONFIG = dict(
    initial_capital=10_000.0,
    risk_per_trade_pct=0.01,   # % de equity arriesgado por trade (entrada → SL)
    max_positions=10,          # nº máximo de posiciones simultáneas
    max_position_pct=0.20,     # tope de capital en una sola posición
    trailing_pct=0.20,         # trailing stop: % bajo el máximo alcanzado
    commission_pct=0.001,      # comisión por lado (0.1%)
    max_hold_days=252,         # cierre forzoso tras N sesiones
    min_position_value=200.0,  # no abrir posiciones ridículas
    market_filter_ma=None,     # si se fija (p.ej. 200): cierra TODA la cartera y no entra
                               # mientras el SPY esté bajo su MA(N). Protege drawdown.
)


def _prepare_arrays(price_data, symbols):
    """Pre-indexa cada símbolo para acceso O(1) por fecha en el bucle diario."""
    arr = {}
    for s in symbols:
        d = price_data.get(s)
        if d is None or d.empty:
            continue
        arr[s] = dict(
            idx={ts: i for i, ts in enumerate(d.index)},
            o=d['Open'].values.astype(float),
            h=d['High'].values.astype(float),
            l=d['Low'].values.astype(float),
            c=d['Close'].values.astype(float),
            dates=d.index,
        )
    return arr


def run_portfolio_backtest(signals, price_data, spy, config=None):
    """
    signals:    DataFrame con columnas symbol, date, sl (stop inicial).
    price_data: dict[symbol] -> DataFrame con Open/High/Low/Close indexado por fecha.
    spy:        DataFrame del benchmark (Open/High/Low/Close) — define el calendario.
    Devuelve dict con equity_curve (Series), trades (DataFrame) y metrics (dict).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cal = spy.index
    cal_pos = {ts: i for i, ts in enumerate(cal)}

    sig = signals.copy()
    sig['date'] = pd.to_datetime(sig['date'])
    arr = _prepare_arrays(price_data, sig['symbol'].unique())

    # Mapear cada señal a su fecha de ENTRADA (apertura del día siguiente en el calendario)
    entries_by_day = {}
    for _, r in sig.iterrows():
        d = r['date']
        if d not in cal_pos:
            # alinear a la siguiente fecha del calendario
            future = cal[cal > d]
            if len(future) == 0:
                continue
            d = future[0]
        ci = cal_pos[d]
        if ci + 1 >= len(cal):
            continue
        entry_day = cal[ci + 1]
        entries_by_day.setdefault(entry_day, []).append(dict(symbol=r['symbol'], sl=float(r['sl'])))

    # Filtro de mercado opcional: SPY sobre/bajo su MA(N)
    market_ok_by_day = None
    if cfg.get('market_filter_ma'):
        spy_ma = spy['Close'].rolling(int(cfg['market_filter_ma'])).mean()
        market_ok_by_day = (spy['Close'] >= spy_ma)

    cash = cfg['initial_capital']
    positions = []   # dicts: symbol, shares, entry, stop, peak, entry_day
    trades = []
    equity_curve = []

    def price_at(sym, day, field):
        a = arr.get(sym)
        if a is None or day not in a['idx']:
            return None
        return a[field][a['idx'][day]]

    for day in cal:
        # ── 1. Gestionar posiciones abiertas (salidas + trailing) ──────────────
        still_open = []
        for p in positions:
            a = arr.get(p['symbol'])
            if a is None or day not in a['idx']:
                still_open.append(p)   # sin barra hoy: mantener
                continue
            i = a['idx'][day]
            lo, hi, op, cl = a['l'][i], a['h'][i], a['o'][i], a['c'][i]
            held = cal_pos[day] - cal_pos[p['entry_day']]

            exit_price = None
            if lo <= p['stop']:
                # gap a la baja: si abre bajo el stop, sale en la apertura
                exit_price = op if op <= p['stop'] else p['stop']
            elif held >= cfg['max_hold_days']:
                exit_price = cl

            if exit_price is not None:
                proceeds = p['shares'] * exit_price * (1 - cfg['commission_pct'])
                cash += proceeds
                pnl = proceeds - p['cost_basis']
                trades.append(dict(symbol=p['symbol'], entry_day=p['entry_day'], exit_day=day,
                                   entry=p['entry'], exit=exit_price, shares=p['shares'],
                                   pnl=pnl, ret_pct=(exit_price / p['entry'] - 1) * 100,
                                   bars=held))
            else:
                p['peak'] = max(p['peak'], hi)
                p['stop'] = max(p['stop'], p['peak'] * (1 - cfg['trailing_pct']))
                still_open.append(p)
        positions = still_open

        # ── 1b. Filtro de mercado: si el SPY está bajo su MA, liquidar TODO ─────
        market_ok = True
        if market_ok_by_day is not None:
            mo = market_ok_by_day.get(day)
            market_ok = bool(mo) if mo is not None and not pd.isna(mo) else True
        if not market_ok and positions:
            survivors = []
            for p in positions:
                px_c = price_at(p['symbol'], day, 'c')
                if px_c is None:
                    survivors.append(p)   # sin barra: no se puede liquidar hoy
                    continue
                proceeds = p['shares'] * px_c * (1 - cfg['commission_pct'])
                cash += proceeds
                trades.append(dict(symbol=p['symbol'], entry_day=p['entry_day'], exit_day=day,
                                   entry=p['entry'], exit=px_c, shares=p['shares'],
                                   pnl=proceeds - p['cost_basis'],
                                   ret_pct=(px_c / p['entry'] - 1) * 100,
                                   bars=cal_pos[day] - cal_pos[p['entry_day']]))
            positions = survivors

        # equity al inicio (para dimensionar) = cash + MTM
        def mtm():
            v = cash
            for p in positions:
                c = price_at(p['symbol'], day, 'c')
                v += p['shares'] * (c if c is not None else p['entry'])
            return v
        equity = mtm()

        # ── 2. Nuevas entradas (apertura de hoy) — solo si el mercado lo permite ─
        for s in (entries_by_day.get(day, []) if market_ok else []):
            if len(positions) >= cfg['max_positions']:
                break
            entry = price_at(s['symbol'], day, 'o')
            if entry is None or entry <= 0:
                continue
            risk_per_share = entry - s['sl']
            if risk_per_share <= 0:
                continue
            risk_cap = cfg['risk_per_trade_pct'] * equity
            pos_value = risk_cap / risk_per_share * entry
            pos_value = min(pos_value, cfg['max_position_pct'] * equity, cash)
            if pos_value < cfg['min_position_value']:
                continue
            shares = pos_value / entry
            cost = shares * entry * (1 + cfg['commission_pct'])
            if cost > cash:
                continue
            cash -= cost
            positions.append(dict(symbol=s['symbol'], shares=shares, entry=entry,
                                  stop=s['sl'], peak=entry, entry_day=day, cost_basis=cost))

        equity_curve.append((day, mtm()))

    # Liquidar lo que quede al final (al último cierre)
    last = cal[-1]
    for p in positions:
        c = price_at(p['symbol'], last, 'c') or p['entry']
        proceeds = p['shares'] * c * (1 - cfg['commission_pct'])
        cash += proceeds
        trades.append(dict(symbol=p['symbol'], entry_day=p['entry_day'], exit_day=last,
                           entry=p['entry'], exit=c, shares=p['shares'],
                           pnl=proceeds - p['cost_basis'], ret_pct=(c / p['entry'] - 1) * 100,
                           bars=cal_pos[last] - cal_pos[p['entry_day']]))

    eq = pd.Series(dict(equity_curve)).sort_index()
    trades_df = pd.DataFrame(trades)
    metrics = compute_metrics(eq, spy, trades_df, cfg)
    return dict(equity_curve=eq, trades=trades_df, metrics=metrics, config=cfg)


def compute_metrics(eq, spy, trades, cfg):
    """Métricas de la cartera + benchmark SPY (comprar y mantener)."""
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total_ret = eq.iloc[-1] / eq.iloc[0] - 1
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    daily = eq.pct_change().dropna()
    sharpe = (daily.mean() / daily.std() * np.sqrt(252)) if daily.std() > 0 else 0.0
    roll_max = eq.cummax()
    max_dd = ((eq - roll_max) / roll_max).min()

    # Benchmark SPY buy & hold sobre el mismo periodo y capital
    spy_c = spy['Close'].reindex(eq.index).ffill()
    spy_eq = cfg['initial_capital'] * spy_c / spy_c.iloc[0]
    spy_total = spy_eq.iloc[-1] / spy_eq.iloc[0] - 1
    spy_cagr = (spy_eq.iloc[-1] / spy_eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0.0
    spy_dd = ((spy_eq - spy_eq.cummax()) / spy_eq.cummax()).min()
    spy_daily = spy_eq.pct_change().dropna()
    spy_sharpe = (spy_daily.mean() / spy_daily.std() * np.sqrt(252)) if spy_daily.std() > 0 else 0.0

    m = dict(
        years=round(years, 2),
        final_equity=round(eq.iloc[-1], 0),
        total_return_pct=round(total_ret * 100, 1),
        cagr_pct=round(cagr * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 1),
        sharpe=round(sharpe, 2),
        n_trades=len(trades),
        spy_total_return_pct=round(spy_total * 100, 1),
        spy_cagr_pct=round(spy_cagr * 100, 2),
        spy_max_drawdown_pct=round(spy_dd * 100, 1),
        spy_sharpe=round(spy_sharpe, 2),
        alpha_cagr_pct=round((cagr - spy_cagr) * 100, 2),
    )
    if len(trades) > 0:
        r = trades['ret_pct']
        m.update(
            win_rate_pct=round((trades['pnl'] > 0).mean() * 100, 1),
            avg_win_pct=round(r[r > 0].mean(), 1) if (r > 0).any() else 0.0,
            avg_loss_pct=round(r[r < 0].mean(), 1) if (r < 0).any() else 0.0,
            profit_factor=round(trades.loc[trades['pnl'] > 0, 'pnl'].sum() /
                                abs(trades.loc[trades['pnl'] < 0, 'pnl'].sum()), 2)
                          if (trades['pnl'] < 0).any() else float('inf'),
            avg_hold_bars=round(trades['bars'].mean(), 0),
            best_trade_pct=round(r.max(), 1),
            worst_trade_pct=round(r.min(), 1),
        )
    return m


def print_report(results):
    m = results['metrics']
    print("=" * 64)
    print("BACKTEST DE CARTERA")
    print("=" * 64)
    print(f"  Periodo:            {m['years']} años   |   Trades: {m['n_trades']}")
    print(f"  Capital final:      ${m['final_equity']:,.0f}")
    print(f"  Retorno total:      {m['total_return_pct']:+.1f}%")
    print(f"  CAGR:               {m['cagr_pct']:+.2f}%   (SPY: {m['spy_cagr_pct']:+.2f}%)")
    print(f"  Max Drawdown:       {m['max_drawdown_pct']:.1f}%   (SPY: {m['spy_max_drawdown_pct']:.1f}%)")
    print(f"  Sharpe:             {m['sharpe']:.2f}   (SPY: {m['spy_sharpe']:.2f})")
    print(f"  ALPHA (CAGR):       {m['alpha_cagr_pct']:+.2f}%  {'✓ bate al SPY' if m['alpha_cagr_pct'] > 0 else '✗ no bate al SPY'}")
    if 'win_rate_pct' in m:
        print(f"  Win rate:           {m['win_rate_pct']:.1f}%   PF: {m['profit_factor']:.2f}")
        print(f"  Avg win / loss:     {m['avg_win_pct']:+.1f}% / {m['avg_loss_pct']:+.1f}%")
        print(f"  Hold medio:         {m['avg_hold_bars']:.0f} sesiones")
        print(f"  Mejor / peor:       {m['best_trade_pct']:+.1f}% / {m['worst_trade_pct']:+.1f}%")
    print("=" * 64)


if __name__ == "__main__":
    print("Motor de backtest de cartera. Importar run_portfolio_backtest() con:")
    print("  - signals: DataFrame [symbol, date, sl]")
    print("  - price_data: dict[symbol] -> DataFrame OHLC")
    print("  - spy: DataFrame OHLC del benchmark")
    print("Ver run_portfolio_demo.py para un ejemplo con datos reales.")
