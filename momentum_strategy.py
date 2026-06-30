# momentum_strategy.py — Lógica de detección MOMENTUM / Fuerza relativa
#
# Filosofía Minervini/O'Neil: cazar LÍDERES (fuerza relativa alta, tendencia alcista).
# Dos formas de detección, ambas sin look-ahead:
#   - evaluate_breakout (PRIMARIA, producción): ruptura confirmada del máximo previo
#     que aguanta como soporte; stop bajo el nivel roto, riesgo ≤12%, fresca (r1m>0).
#   - evaluate_entry (SECUNDARIA / backtest): rebote en la MA50 en subida (pullback).
#
# generate_momentum_signals produce señales [symbol, date, sl] para portfolio_backtest.py
# y aplica liquidez point-in-time (mismo universo que producción).
#
# NOTA sobre el backtest (config market_filter_ma=200 + trailing ~0.32):
#   El momentum MECÁNICO no bate al SPY sobre universo real (CAGR ~+6/+11% vs +14.6%;
#   las cifras viejas de "~15%, bate al índice" eran sesgo de supervivencia de un
#   universo cherry-picked). Lo robusto: el filtro de mercado MA200 protege en bear
#   (2022: capital intacto vs SPY −20%) y la liquidez es imprescindible. Por eso el
#   uso real es un DETECTOR para revisión manual, no un robot. Ver README / memoria.

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
    # --- Filtro de liquidez (institucional) — ÚNICA fuente del umbral ---
    # Se aplica IGUAL en producción (screener, sobre la última barra) y en el backtest
    # (point-in-time en cada rebalanceo) para que ambos operen el MISMO universo.
    min_dollar_vol=20_000_000,  # dólar-volumen MEDIANO mínimo (≈ $20M/día)
    min_price=10.0,             # precio mínimo (fuera chicharros)
    liq_window=50,              # sesiones para la mediana del dólar-volumen
    # --- Detector de RUPTURA confirmada (lista PRIMARIA del screener) ---
    # Caza líderes que han SUPERADO su resistencia (máximo previo) y la mantienen como
    # soporte → ahí va el stop. Filosofía position trading: comprar fuerza confirmada,
    # no adivinar suelos. El máximo NO debe actuar de resistencia: debe haber quedado
    # ABAJO como soporte. Stop ≤ max_risk_pct (12%), lo que descarta las ya extendidas.
    breakout_rs_min=90,         # RS estricto (top ~10%) para la lista de rupturas
    prior_high_exclude=25,      # sesiones recientes excluidas del máximo 52s → "resistencia previa"
    breakout_hold_window=5,     # las últimas N sesiones deben aguantar sobre el nivel roto
    retest_margin=0.04,         # si el mínimo reciente volvió a ≤4% del nivel roto → "retest OK"
    breakout_min_r1m=0.0,       # FRESCURA: el último mes (21 sesiones) debe seguir subiendo
                                # (>0). Descarta rupturas viejas que ya hicieron techo y se
                                # giran, sin penalizar a las que corrigieron y rebotan.
    breakout_max_ext_ma50=0.12, # CAP DE EXTENSIÓN sobre la MA50: descarta rupturas compradas
                                # demasiado lejos de la MA50 (px > MA50·1.12). En líderes
                                # volátiles el soporte fiable es la MA50, NO el máximo roto: si
                                # el precio entra muy arriba, el stop al nivel roto cae DENTRO
                                # del hueco hasta la MA50 y el retroceso normal lo barre
                                # (SNEX/AMKR jun-2026, ambas a +17/+19% de la MA50; LLY +19%:
                                # con el stop en la MA50 el riesgo sería 16% > tope, no operable).
                                # BACKTEST (350 large/mid-cap, 2019-26, rupturas): sin cap
                                # CAGR 8.7%/Sharpe 0.55/PF 1.82; cap 0.12 → CAGR 12.9%/Sharpe
                                # 0.81/PF 2.64; pico en 0.15 (15.2%/0.90). Meseta estable
                                # 0.10-0.15; el usuario eligió 0.12 (más disciplina de stop).
                                # OJO: un solo periodo/universo → no clavar el valor exacto
                                # (sobreajuste). Ver memoria breakout_stop_vs_ma50.
    breakout_stop_atr=0.5,      # MARGEN del stop bajo el soporte real (mín. de testeo o
                                # nivel roto, el más bajo) − este·ATR. Margen para barridos.
                                # BACKTEST (cap 0.12, hold 1.0): nivel−0.5 (actual viejo)
                                # CAGR 14.0/Sharpe 0.85; híbrido min−0.5 → 14.6/0.88 (mejora
                                # limpia). 1.0 empeora (12.2), 1.5 sube a 16.6 pero el patrón
                                # no es monótono → ruido/sobreajuste, NO perseguirlo. Queda 0.5.
    breakout_stop_ref='hybrid', # 'hybrid' = stop bajo min(mínimo de testeo, nivel roto):
                                # si hubo barrido, va bajo el mínimo del barrido; si no,
                                # bajo el nivel roto. 'level' = solo el nivel roto (viejo).
    breakout_hold_atr=1.0,      # TOLERANCIA del "aguanta como soporte": en las últimas
                                # `breakout_hold_window` sesiones el mínimo no debe estar
                                # más de `breakout_hold_atr`·ATR bajo el nivel roto. Antes
                                # 0.5 → rechazaba el barrido/overshoot normal del retest.
                                # BACKTEST (cap 0.12 fijo): 0.5→CAGR 12.9/Sharpe 0.81/PF 2.64;
                                # 1.0→14.0/0.85/2.74 (ÓPTIMO); 1.5→12.3/0.73; 2.0→11.2/0.68.
                                # Relajar a 1.0 tolera el barrido sano y MEJORA; pasar de ahí
                                # admite rupturas que se giran y empeora. El cierre sigue
                                # exigiéndose sobre el nivel (px>prior_high). Los barridos más
                                # profundos (LLY ~1.4·ATR) son justo casos de la lista 'a
                                # vigilar', no entradas accionables. Ver breakout_stop_vs_ma50.
    # --- Lista 'A VIGILAR / EN TESTEO' (radar, NO accionable) ---
    # Líder que hizo nuevos máximos recientes y ha RETROCEDIDO desde ellos, pero sigue
    # sobre la MA50 (en subida) y aún no ha llegado a testearla. Es el paso PREVIO a la
    # entrada: se vigila si rebota (continuación) o cae al testeo de la MA50 (y entonces
    # aparece en la lista de pullback). No lleva stop/entrada accionables.
    watch_rs_min=90,            # mismo listón de líder que la ruptura (top ~10%)
    watch_high_window=25,       # ventana del "máximo reciente" desde el que retrocede
    watch_near_high=0.02,       # ese máximo reciente debe estar a ≤2% del máximo de 52s
    watch_pullback_min=0.03,    # ...y el precio ha retrocedido ≥3% desde ese máximo
    watch_ma50_buffer=0.0,      # ...pero sigue por encima de la MA50 (uptrend intacto)
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


def evaluate_breakout(c, h, l, i, rs_val, params=None):
    """
    Detector de RUPTURA CONFIRMADA (lista primaria). Caza líderes que han superado su
    resistencia (máximo previo de 52s) y la mantienen como SOPORTE, con stop natural
    justo bajo el nivel roto y riesgo ≤ max_risk_pct (12%). Acepta tanto las que ya
    han retesteado el nivel como las que solo lo han superado con claridad sin girarse.

    Sin look-ahead: solo usa datos hasta la barra i. Devuelve dict o None.
    """
    p = {**DEFAULTS, **(params or {})}
    if rs_val is None or rs_val < p['breakout_rs_min'] or i < 252:
        return None
    px = c[i]
    ma50 = c[i - 50:i].mean()
    ma200 = c[i - 200:i].mean()
    ma50_prev = c[i - 70:i - 20].mean()
    ma200_prev = c[i - 221:i - 21].mean() if i >= 221 else ma200
    # Tendencia de fondo (stage 2): líder en tendencia alcista sostenida
    if not (px > ma50 > ma200 and ma200 > ma200_prev and ma50 > ma50_prev):
        return None

    # Cap de extensión sobre la MA50: el soporte fiable de un líder volátil es la MA50,
    # no el máximo roto. Si el precio entra demasiado lejos de la MA50, el stop al nivel
    # roto cae dentro del hueco hasta ella y un retroceso normal lo barre (SNEX/AMKR
    # jun-2026: rompieron, el techo no aguantó, fueron a la MA50 y saltó el stop).
    max_ext = p.get('breakout_max_ext_ma50')
    if max_ext is not None and px > ma50 * (1 + max_ext):
        return None

    # Resistencia previa = máximo de 52s EXCLUYENDO las últimas sesiones (la ruptura).
    ex = p['prior_high_exclude']
    prior_high = h[i - 252:i - ex].max()
    if not (px > prior_high):          # tiene que haber roto el techo
        return None

    at = _atr(h, l, c, i, p['atr_period'])
    if not np.isfinite(at) or at <= 0:
        return None

    # El nivel roto debe AGUANTAR como soporte: en las últimas N sesiones el mínimo no
    # se ha metido más de `breakout_hold_atr`·ATR por debajo del techo roto. Tolera el
    # barrido/overshoot normal del retest (si luego cierra sobre el nivel, px>prior_high).
    hw = p['breakout_hold_window']
    recent_low = l[i - hw:i + 1].min()
    if recent_low < prior_high - p['breakout_hold_atr'] * at:
        return None

    # Stop natural: bajo el SOPORTE REAL = el más bajo entre el mínimo local de testeo
    # (donde entraron compradores en el barrido) y el nivel roto, menos un margen para
    # barridos. Si hubo retest, el stop va bajo el mínimo del barrido (no bajo la
    # resistencia, que se suele perforar un poco); si NO hubo retest, recent_low queda
    # sobre el nivel y el ancla robusta es el propio nivel roto. El gate de "hold" acota
    # recent_low a ≤1·ATR bajo el nivel, así que el stop nunca se dispara de ancho.
    # Riesgo ≤ 12% (max_risk_pct) descarta de paso las rupturas ya extendidas.
    stop_anchor = min(recent_low, prior_high) if p.get('breakout_stop_ref', 'hybrid') == 'hybrid' else prior_high
    sl = stop_anchor - p['breakout_stop_atr'] * at
    risk = (px - sl) / px
    if risk <= 0 or risk > p['max_risk_pct']:
        return None

    # Frescura: que el último mes siga subiendo (no una ruptura vieja ya girándose).
    r1m = (c[i] / c[i - 21] - 1) if i >= 21 and c[i - 21] > 0 else 0.0
    if r1m <= p['breakout_min_r1m']:
        return None

    hi52 = h[i - 252:i].max()
    retested = recent_low <= prior_high * (1 + p['retest_margin'])
    return dict(signal=True, entry=float(px), sl=round(float(sl), 4),
                risk_pct=round(float(risk) * 100, 2),
                breakout_level=round(float(prior_high), 2),
                pct_above_breakout=round((px / prior_high - 1) * 100, 1),
                ma50=round(float(ma50), 2), ma200=round(float(ma200), 2),
                hi52=round(float(hi52), 2),
                pct_from_high=round((px / hi52 - 1) * 100, 1),
                r1m=round(float(r1m) * 100, 1),
                retested=bool(retested))


def evaluate_watch(c, h, l, i, rs_val, params=None):
    """
    Lista 'A VIGILAR / EN TESTEO' (radar, NO accionable, sin stop/entrada). Detecta al
    líder que hizo NUEVOS MÁXIMOS recientes y ha RETROCEDIDO desde ellos, pero sigue por
    encima de la MA50 (en subida) y aún no ha llegado a testearla. Es el paso PREVIO a la
    entrada: se vigila si en las próximas sesiones REBOTA hacia arriba (continuación →
    posible ruptura) o cae al testeo de la MA50 (→ aparece en la lista de pullback).

    El hueco que ni la ruptura (px aún bajo el máximo) ni el pullback (aún no toca la
    MA50) capturan. Ej.: LLY sale los días 23-25/06/2026 (retrocedida ~4-7% del máximo de
    1183, aún sobre la MA50) y deja de salir el 26 (de nuevo en máximos → tarde/extendida).
    Sin look-ahead: solo usa datos hasta la barra i. Devuelve dict o None.
    """
    p = {**DEFAULTS, **(params or {})}
    if rs_val is None or rs_val < p['watch_rs_min'] or i < 252:
        return None
    px = c[i]
    ma50 = c[i - 50:i].mean()
    ma200 = c[i - 200:i].mean()
    ma50_prev = c[i - 70:i - 20].mean()
    ma200_prev = c[i - 221:i - 21].mean() if i >= 221 else ma200
    # Líder en tendencia alcista sostenida (mismo trend template que la ruptura)
    if not (px > ma50 > ma200 and ma200 > ma200_prev and ma50 > ma50_prev):
        return None

    hi52 = h[i - 252:i + 1].max()
    hi_recent = h[i - p['watch_high_window']:i + 1].max()
    # Acaba de hacer máximos: el máximo reciente está pegado al máximo de 52s.
    if hi_recent < hi52 * (1 - p['watch_near_high']):
        return None
    # Ha retrocedido desde ese máximo (≥ watch_pullback_min) PERO sigue sobre la MA50
    # (uptrend intacto, aún no ha llegado al testeo de la media → no es pullback todavía).
    pulled = px <= hi_recent * (1 - p['watch_pullback_min'])
    above_ma50 = px > ma50 * (1 + p['watch_ma50_buffer'])
    if not (pulled and above_ma50):
        return None

    at = _atr(h, l, c, i, p['atr_period'])
    return dict(signal=True, entry=float(px),
                recent_high=round(float(hi_recent), 2),
                pct_from_recent_high=round((px / hi_recent - 1) * 100, 1),
                ma50=round(float(ma50), 2), ma200=round(float(ma200), 2),
                hi52=round(float(hi52), 2),
                pct_from_high=round((px / hi52 - 1) * 100, 1),
                ext_ma50_pct=round((px / ma50 - 1) * 100, 1),
                atr=round(float(at), 2) if np.isfinite(at) else None)


def generate_momentum_signals(price_data, spy, step=5, params=None, evaluator=None, rs_floor=None):
    """
    Walk-forward sin look-ahead. En cada fecha:
      1) calcula el momentum 6m de todo el universo y lo convierte en percentil (RS),
      2) en los líderes (RS alto), exige trend template (px>MA50>MA200, MA200 y MA50
         subiendo, cerca de máximos) y un retroceso que tocó la MA50 y rebota,
      3) emite la señal con stop bajo el mínimo del retroceso − 0.5·ATR.
    Devuelve DataFrame [symbol, date, sl].

    `evaluator` permite backtestear OTRA forma de entrada con el MISMO universo/liquidez
    point-in-time: por defecto `evaluate_entry` (pullback a MA50); pásale `evaluate_breakout`
    para validar la lista PRIMARIA de rupturas. `rs_floor` (por defecto `rs_min`) es el
    corte de RS del bucle externo — para rupturas conviene `breakout_rs_min` (90).
    """
    p = {**DEFAULTS, **(params or {})}
    evaluator = evaluator or evaluate_entry
    rs_floor = p['rs_min'] if rs_floor is None else rs_floor
    cal = spy.index
    A = {}
    for s, d in price_data.items():
        A[s] = dict(idx={ts: i for i, ts in enumerate(d.index)},
                    h=d['High'].values.astype(float),
                    l=d['Low'].values.astype(float),
                    c=d['Close'].values.astype(float),
                    v=(d['Volume'].values.astype(float) if 'Volume' in d.columns else None))
    lw, mdv, mp = p['liq_window'], p['min_dollar_vol'], p['min_price']

    seen, rows = {}, []
    for ci in range(290, len(cal) - 2, step):
        T = cal[ci]
        # 1) momentum del universo LÍQUIDO (point-in-time) → ranking percentil.
        #    Mismo filtro que producción (dólar-volumen mediano + precio mínimo) pero
        #    evaluado en CADA fecha sin look-ahead, para que el RS se calcule entre
        #    nombres institucionales en ese momento, no contra microcaps que 'pop'ean.
        mom = {}
        for s, a in A.items():
            i = a['idx'].get(T)
            if i is None or i < 200:
                continue
            c = a['c']
            v = a['v']
            if v is not None and i >= lw:
                dollar = float(np.median(c[i - lw + 1:i + 1] * v[i - lw + 1:i + 1]))
                if c[i] < mp or dollar < mdv:
                    continue
            base = c[i - p['mom_lookback']]
            if base > 0:
                mom[s] = c[i] / base - 1
        if len(mom) < 50:
            continue
        rs = pd.Series(mom).rank(pct=True) * 100

        # 2) trigger en los líderes (lógica compartida con el screener de producción)
        for s, rs_val in rs.items():
            if rs_val < rs_floor:
                continue
            if s in seen and ci - seen[s] < p['cooldown']:
                continue
            a = A[s]
            i = a['idx'][T]
            sig = evaluator(a['c'], a['h'], a['l'], i, rs_val, p)
            if sig is None:
                continue
            seen[s] = ci
            rows.append(dict(symbol=s, date=str(T.date()), sl=sig['sl']))

    return pd.DataFrame(rows)
