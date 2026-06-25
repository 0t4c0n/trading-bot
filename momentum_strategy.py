# momentum_strategy.py — Generador de señales MOMENTUM / Fuerza relativa
#
# Filosofía Minervini/O'Neil: comprar LÍDERES (fuerza relativa alta, tendencia
# alcista, cerca de máximos) en un punto de ENTRADA de BAJO RIESGO — el retroceso
# a la MA50 en subida, donde el stop queda cerca. La salida (dejar correr con
# trailing) la gestiona el motor de cartera.
#
# Produce señales [symbol, date, sl] compatibles con portfolio_backtest.py.
#
# CONFIG RECOMENDADA en el motor de cartera (validada en backtest 2020-2025):
#   market_filter_ma=200   -> IMPRESCINDIBLE: el momentum es beta pura; sin salir
#                             a liquidez cuando el SPY pierde su MA200, el drawdown
#                             se dispara a -40%. Con ella baja a ~-18%.
#   trailing_pct=0.30-0.35 -> los líderes necesitan stops ANCHOS para no ser
#                             sacudidos; con trailing ajustado el sistema se hunde.
# Con esa config: CAGR ~15% vs SPY 14.6%, MaxDD ~-17% vs -34%, Sharpe ~0.9 vs 0.78.
# (Caveat: sesgo de supervivencia → optimista; validar out-of-sample.)

import contextlib
import io

import numpy as np
import pandas as pd


DEFAULTS = dict(
    rs_min=80,                # percentil mínimo de fuerza relativa (top 20%)
    mom_lookback=126,         # ventana de momentum (6 meses) para el ranking
    near_high_max_below=0.25, # descartar si está >25% bajo su máximo de 52s
    pullback_touch=0.05,      # el mínimo reciente tocó la MA50 (±) en este margen
    pullback_floor=0.07,      # ...pero sin perforarla más de un 7%
    not_extended=0.12,        # no entrar si el precio está >12% sobre la MA50
    swing_window=8,           # ventana del mínimo reciente (pullback / stop)
    atr_period=14,
    max_risk_pct=0.12,        # descartar entradas con stop a >12%
    cooldown=15,              # no re-señalar el mismo símbolo en N sesiones
    min_history=260,
)


def _atr(h, l, c, i, n=14):
    if i < n:
        return np.nan
    tr = np.maximum(h[i - n + 1:i + 1] - l[i - n + 1:i + 1], 0.0)
    return float(tr.mean())


def generate_momentum_signals(price_data, spy, step=5, params=None):
    """
    Walk-forward sin look-ahead. En cada fecha:
      1) calcula el momentum 6m de todo el universo y lo convierte en percentil (RS),
      2) en los líderes (RS alto), exige trend template (px>MA50>MA200, MA200 y MA50
         subiendo, cerca de máximos) y un retroceso que tocó la MA50 y rebota,
      3) emite la señal con stop bajo el mínimo del retroceso − 0.5·ATR.
    Devuelve DataFrame [symbol, date, sl].
    """
    p = {**DEFAULTS, **(params or {})}
    cal = spy.index
    A = {}
    for s, d in price_data.items():
        A[s] = dict(idx={ts: i for i, ts in enumerate(d.index)},
                    h=d['High'].values.astype(float),
                    l=d['Low'].values.astype(float),
                    c=d['Close'].values.astype(float))

    seen, rows = {}, []
    for ci in range(290, len(cal) - 2, step):
        T = cal[ci]
        # 1) momentum de todo el universo → ranking percentil
        mom = {}
        for s, a in A.items():
            i = a['idx'].get(T)
            if i is None or i < 200:
                continue
            c = a['c']
            base = c[i - p['mom_lookback']]
            if base > 0:
                mom[s] = c[i] / base - 1
        if len(mom) < 50:
            continue
        rs = pd.Series(mom).rank(pct=True) * 100

        # 2) trigger en los líderes
        for s, rs_val in rs.items():
            if rs_val < p['rs_min']:
                continue
            a = A[s]
            i = a['idx'][T]
            c, h, l = a['c'], a['h'], a['l']
            px = c[i]
            ma50 = c[i - 50:i].mean()
            ma200 = c[i - 200:i].mean()
            ma50_prev = c[i - 70:i - 20].mean()
            ma200_prev = c[i - 221:i - 21].mean() if i >= 221 else ma200
            hi52 = h[i - 252:i].max() if i >= 252 else h[:i].max()

            # trend template
            if not (px > ma50 > ma200 and ma200 > ma200_prev and ma50 > ma50_prev):
                continue
            if px > hi52 or px < hi52 * (1 - p['near_high_max_below']):
                continue
            # pullback a la MA50 + rebote
            low8 = l[i - p['swing_window']:i].min()
            touched = ma50 * (1 - p['pullback_floor']) <= low8 <= ma50 * (1 + p['pullback_touch'])
            bounce = px > ma50 and c[i] > c[i - 1] and px <= ma50 * (1 + p['not_extended'])
            if not (touched and bounce):
                continue
            if s in seen and ci - seen[s] < p['cooldown']:
                continue

            at = _atr(h, l, c, i, p['atr_period'])
            if not np.isfinite(at) or at <= 0:
                continue
            sl = low8 - 0.5 * at
            risk = (px - sl) / px
            if risk <= 0 or risk > p['max_risk_pct']:
                continue
            seen[s] = ci
            rows.append(dict(symbol=s, date=str(T.date()), sl=round(sl, 4)))

    return pd.DataFrame(rows)
