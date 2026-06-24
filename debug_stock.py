# debug_stock.py - Wyckoff Spring Debug Tool (con scoring dual Probabilidad + Potencial)
import yfinance as yf
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from script_automated import WyckoffSpringScreener

# ▼▼▼ ELIGE LA ACCIÓN A ANALIZAR ▼▼▼
TICKER_TO_DEBUG = "INTC"
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲


def debug_wyckoff_stock(symbol):
    print(f"=== WYCKOFF SPRING DEBUG: {symbol} ===\n")
    screener = WyckoffSpringScreener()

    # 1. Descargar datos
    print(f"Descargando datos (2 años) para {symbol} y ^GSPC...")
    try:
        data = yf.download([symbol, '^GSPC'], period='2y', auto_adjust=True, progress=False)
        hist_df = data.xs(symbol,   level=1, axis=1).dropna()
        spy_df  = data.xs('^GSPC',  level=1, axis=1).dropna()
        if hist_df.empty or len(hist_df) < screener.MIN_DATA_POINTS:
            print(f"❌ Datos insuficientes ({len(hist_df)} velas, mínimo {screener.MIN_DATA_POINTS})")
            return
        print(f"✓ {len(hist_df)} velas ({hist_df.index[0].date()} → {hist_df.index[-1].date()})\n")
    except Exception as e:
        print(f"❌ Error descargando datos: {e}")
        return

    current_price = float(hist_df['Close'].iloc[-1])

    # 2. Estado del mercado
    print("--- ESTADO DEL MERCADO ---")
    market_healthy, market_health_score = screener.check_market_health(spy_df)
    status = "ALCISTA ✅" if market_healthy else "BAJISTA ⚠️"
    print(f"  S&P 500: {status} | Score: {market_health_score}/15")
    if not market_healthy:
        print(f"  ⚠️  Mercado bajista — Springs menos fiables. Considerar esperar.")

    # 3. RS Rating estimado
    print(f"\n--- RS RATING ---")
    rs_rating = 50.0
    try:
        if len(hist_df) >= 252 and len(spy_df) >= 252:
            def _rs(df):
                c = df['Close']
                p3   = ((c.iloc[-1]/c.iloc[-63])-1)*100
                p_q2 = ((c.iloc[-63]/c.iloc[-126])-1)*100
                p_q3 = ((c.iloc[-126]/c.iloc[-189])-1)*100
                p_q4 = ((c.iloc[-189]/c.iloc[-252])-1)*100
                return 0.4*p3 + 0.2*p_q2 + 0.2*p_q3 + 0.2*p_q4
            rs_rating = max(1.0, min(99.0, 50.0 + (_rs(hist_df) - _rs(spy_df))))
            print(f"  RS Rating estimado: {rs_rating:.1f}/100")
    except Exception:
        print(f"  RS Rating: {rs_rating:.1f} (fallback)")

    # 4. Volume Profile
    print(f"\n--- VOLUME PROFILE ({screener.VOL_LOOKBACK} días) ---")
    poc, hvn_list = screener.calculate_volume_profile(hist_df)
    print(f"  Precio actual: ${current_price:.2f}")
    print(f"  POC:           ${poc:.2f}" if poc else "  POC:           N/A")
    print(f"  HVNs:          {len(hvn_list)}")
    if hvn_list:
        nearest = sorted(hvn_list, key=lambda h: abs(h - current_price))[:4]
        print(f"  4 HVN más cercanos: {[round(h,2) for h in nearest]}")

    # 5. Soporte estructural
    print(f"\n--- SOPORTE ESTRUCTURAL S1 ({screener.SUPPORT_LOOKBACK} días) ---")
    s1 = screener.find_structural_support(hist_df)
    print(f"  S1: ${s1:.2f}  (precio {((current_price-s1)/s1*100):+.1f}% sobre S1)")

    # 6. Confluencia
    print(f"\n--- CONFLUENCIA S1 ↔ Volume Profile ---")
    conf_valid, conf_score, nearest_level = screener.check_s1_confluence(s1, poc, hvn_list)
    if conf_valid:
        dist = abs(s1 - nearest_level) / nearest_level * 100
        tipo = "POC" if nearest_level == poc else "HVN"
        print(f"  ✅ VÁLIDA | Score: {conf_score}/30 | {tipo}: ${nearest_level:.2f} ({dist:.2f}% de distancia)")
    else:
        if poc:
            dist_poc = abs(s1 - poc) / poc * 100
            print(f"  ❌ Sin confluencia | POC a {dist_poc:.2f}% de S1 (límite: 1%)")
        if hvn_list:
            nhvn = min(hvn_list, key=lambda h: abs(h - s1))
            print(f"  ❌ HVN más cercano a S1: ${nhvn:.2f} ({abs(s1-nhvn)/nhvn*100:.2f}%)")
        print("  ⛔ Sin confluencia → Spring no aplica según metodología")

    # 7. Spring
    print(f"\n--- SPRING WYCKOFF (Fase C) ---")
    spring_info = screener.detect_spring(hist_df, s1) if conf_valid else None
    if spring_info:
        print(f"  ✅ SPRING DETECTADO")
        print(f"     Fecha:     {spring_info['date']}")
        print(f"     Low:       ${spring_info['low']:.2f}  (S1=${s1:.2f}, -"
              f"{spring_info['spring_depth_pct']:.3f}%)")
        print(f"     Close:     ${spring_info['close']:.2f}")
        print(f"     Cierre:    {spring_info['close_position']*100:.1f}% del rango (≥67% req.)")
        print(f"     Volumen:   {spring_info['vol_ratio']}× SMA(20) (≥{screener.FILTER_VOLUMEN}× req.)")
    elif conf_valid:
        print(f"  ❌ Sin Spring en últimos {screener.SUPPORT_LOOKBACK} días")
        print(f"     Cond.: Low<${s1:.2f} AND Close>${s1:.2f} AND cierre≥67% AND vol≥{screener.FILTER_VOLUMEN}×SMA20")

    # 8. Calidad de la base (solo si hay Spring)
    if spring_info:
        spring_idx = spring_info['index']
        print(f"\n--- CALIDAD DE LA BASE ---")
        obv = screener.calculate_obv_trend_in_base(hist_df, spring_idx)
        base_w = screener.calculate_base_width(hist_df, spring_idx, s1)
        print(f"  OBV trend en base: {obv:.4f}  "
              f"({'✅ Acumulación (compra neta)' if obv > 0 else '❌ Distribución (venta neta)'})")
        print(f"  Anchura de base:   {base_w} días en rango S1±20%  "
              f"({'✅ Causa sólida' if base_w >= 50 else '⚠️ Base estrecha' if base_w >= 20 else '❌ Base muy corta'})")

    # 9. Test / Gatillo de entrada
    print(f"\n--- TEST / GATILLO DE ENTRADA ---")
    if spring_info:
        test_info = screener.detect_test_signal(hist_df, spring_info['index'], s1)
        timing_score = screener.score_test_timing(
            spring_info['index'],
            test_info['index'] if test_info else None
        )
        if test_info:
            days = test_info['index'] - spring_info['index']
            tag = "🎯 ACTIVO — SEÑAL DE ENTRADA" if test_info.get('is_current') else "✅ Completado"
            print(f"  {tag}")
            print(f"  Fecha:     {test_info['date']}  ({days} días tras Spring)")
            print(f"  Close:     ${test_info['close']:.2f}")
            print(f"  Volumen:   {test_info['vol_ratio']}× SMA(20)  (debe ser <1.0)")
            print(f"  Timing:    {timing_score}/20 pts  "
                  f"({'ideal (5-25d)' if 5<=days<=25 else 'ligeramente tarde' if days<=40 else 'tarde'})")
        else:
            print(f"  ⚡ Spring OK — esperando retroceso a S1 (±0.5%) con volumen bajo")
            print(f"  Timing score si llega hoy: {timing_score}/20 pts")
    else:
        print("  — (requiere Spring previo)")

    # 10. Gestión de riesgo
    print(f"\n--- GESTIÓN DE RIESGO ---")
    if spring_info:
        rp = screener.calculate_risk_params(spring_info, hist_df, s1, hvn_list)
        if rp:
            print(f"  Entrada estimada: ${rp['entry_price']:.2f}  (S1 × 1.002)")
            print(f"  Stop Loss:        ${rp['sl']:.4f}  ({rp['risk_pct']:.2f}% de riesgo) ← Spring Low − 0.5×ATR14")
            print(f"  TP1 (50%):        ${rp['tp1']:.2f}  → R:R 1:{rp['rr_tp1']:.2f}  ← resistencia local 60d")
            print(f"  TP2 (50%):        ${rp['tp2']:.2f}  → R:R 1:{rp['rr_tp2']:.2f}  ← HVN superior / R:R 3.5")
            print(f"  ATR(14):          {rp['atr']:.4f}")
    else:
        print("  — (requiere Spring detectado)")

    # 11. Scoring final dual
    print(f"\n--- WYCKOFF SCORE DUAL ---")
    analysis = screener.analyze_wyckoff_stock(
        symbol, hist_df, rs_rating,
        market_healthy=market_healthy,
        market_health_score=market_health_score,
        industry_rank=50.0
    )
    prob  = analysis['probability_score']
    pot   = analysis['potential_score']
    total = analysis['wyckoff_score']
    print(f"  Probabilidad:  {prob:.1f}/60  (mercado + test timing + OBV + sector)")
    print(f"  Potencial:     {pot:.1f}/40   (base width + R:R + shake-out depth)")
    print(f"  TOTAL:         {total:.1f}/100")
    print(f"  Estado:        {analysis['entry_status']}")

    print(f"\n{'='*55}")
    print(f"  {symbol} | ${current_price:.2f} | RS:{rs_rating:.0f} | "
          f"Score:{total:.1f}/100 | {analysis['entry_status']}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    debug_wyckoff_stock(TICKER_TO_DEBUG)
