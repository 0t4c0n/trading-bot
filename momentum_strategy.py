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
    not_extended=0.05,        # CLAVE: el precio actual debe estar a ≤5% sobre la MA50 para
                              # que sea un rebote REAL (no un pico extendido). Validación
                              # visual + backtest: bajar de 12% a 5% mejora CAGR 6.6→12.8 y
                              # Sharpe 0.47→0.80, y elimina las entradas extendidas que fallan.
    swing_window=8,           # ventana del mínimo reciente (pullback / stop)
    atr_period=14,
    max_risk_pct=0.12,        # descartar entradas con stop a >12%
    cooldown=15,              # no re-señalar el mismo símbolo en N sesiones
    min_history=260,
    trailing_stop_pct=32.0,   # salida recomendada (gestión manual): trailing % bajo el pico
)


def _atr(h, l, c, i, n=14):
    if i < n:
        return np.nan
    tr = np.maximum(h[i - n + 1:i + 1] - l[i - n + 1:i + 1], 0.0)
    return float(tr.mean())


def evaluate_entry(c, h, l, i, rs_val, params=None):
    """
    Evalúa la entrada de momentum en la barra i (sin look-ahead: solo usa datos
    hasta i incluido). Compartida por el backtest y el screener de producción para
    garantizar que ambos operan IDÉNTICAMENTE.

    Devuelve dict(signal=True, sl, entry, risk_pct, ma50, hi52, ...) o None.
    """
    p = {**DEFAULTS, **(params or {})}
    if rs_val is None or rs_val < p['rs_min'] or i < 252:
        return None
    px = c[i]
    ma50 = c[i - 50:i].mean()
    ma200 = c[i - 200:i].mean()
    ma50_prev = c[i - 70:i - 20].mean()
    ma200_prev = c[i - 221:i - 21].mean() if i >= 221 else ma200
    hi52 = h[i - 252:i].max()

    # Trend template: líder en tendencia alcista
    if not (px > ma50 > ma200 and ma200 > ma200_prev and ma50 > ma50_prev):
        return None
    if px > hi52 or px < hi52 * (1 - p['near_high_max_below']):
        return None

    # Entrada de bajo riesgo: retroceso que TOCA la MA50 en subida y rebota
    low_sw = l[i - p['swing_window']:i].min()
    touched = ma50 * (1 - p['pullback_floor']) <= low_sw <= ma50 * (1 + p['pullback_touch'])
    bounce = px > ma50 and c[i] > c[i - 1] and px <= ma50 * (1 + p['not_extended'])
    if not (touched and bounce):
        return None

    at = _atr(h, l, c, i, p['atr_period'])
    if not np.isfinite(at) or at <= 0:
        return None
    sl = low_sw - 0.5 * at
    risk = (px - sl) / px
    if risk <= 0 or risk > p['max_risk_pct']:
        return None

    return dict(signal=True, entry=float(px), sl=round(float(sl), 4),
                risk_pct=round(float(risk) * 100, 2), ma50=round(float(ma50), 2),
                ma200=round(float(ma200), 2), hi52=round(float(hi52), 2),
                pct_from_high=round((px / hi52 - 1) * 100, 1),
                trailing_stop_pct=round(p.get('trailing_stop_pct', 32.0), 1))


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

        # 2) trigger en los líderes (lógica compartida con el screener de producción)
        for s, rs_val in rs.items():
            if rs_val < p['rs_min']:
                continue
            if s in seen and ci - seen[s] < p['cooldown']:
                continue
            a = A[s]
            i = a['idx'][T]
            sig = evaluate_entry(a['c'], a['h'], a['l'], i, rs_val, p)
            if sig is None:
                continue
            seen[s] = ci
            rows.append(dict(symbol=s, date=str(T.date()), sl=sig['sl']))

    return pd.DataFrame(rows)
