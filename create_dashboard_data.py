# create_dashboard_data.py - Wyckoff Spring Strategy Dashboard
import pandas as pd
import numpy as np
import json
import glob
import os
from datetime import datetime


def get_entry_status_icon(status):
    if 'Test Activo' in str(status):
        return "🎯"
    elif 'Test Completado' in str(status):
        return "✅"
    elif 'Spring Detectado' in str(status):
        return "⚡"
    else:
        return "⏳"


def get_rs_strength_label(rs_rating):
    rs = float(rs_rating) if rs_rating and str(rs_rating) != 'nan' else 0
    if rs >= 90:   return "Excepcional"
    elif rs >= 80: return "Fuerte"
    elif rs >= 70: return "Bueno"
    elif rs >= 50: return "Medio"
    else:          return "Débil"


def safe_float(val, default=0.0):
    try:
        f = float(val)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def safe_bool(val):
    if isinstance(val, bool):   return val
    if isinstance(val, (int, float)): return bool(val)
    if isinstance(val, str):    return val.strip().lower() in ('true', '1', 'yes')
    return False


def convert_numpy_types(obj):
    if isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float) and not np.isfinite(obj):
        return None
    try:
        if pd.isna(obj):
            return None
    except (TypeError, ValueError):
        pass
    return obj


def create_wyckoff_dashboard_data():
    """Convierte los resultados Wyckoff en datos JSON para el dashboard."""

    print("=== CREATE WYCKOFF DASHBOARD DATA ===")

    try:
        springs_files = glob.glob("wyckoff_spring_analysis_SPRINGS_*.csv")
        all_files     = glob.glob("wyckoff_spring_analysis_ALL_DATA_*.csv")

        print(f"Archivos SPRINGS encontrados: {springs_files}")
        print(f"Archivos ALL_DATA encontrados: {all_files}")

        if not all_files:
            print("❌ No se encontraron archivos ALL_DATA")
            print("💡 Ejecuta primero: python script_automated.py")
            return False

        latest_all     = max(all_files,     key=os.path.getctime)
        latest_springs = max(springs_files, key=os.path.getctime) if springs_files else None

        print(f"Procesando ALL_DATA: {latest_all}")
        print(f"Procesando SPRINGS:  {latest_springs or 'Ninguno'}")

        try:
            all_df = pd.read_csv(latest_all)
            print(f"✓ ALL_DATA leído: {len(all_df)} filas")
        except Exception as e:
            print(f"❌ Error leyendo ALL_DATA: {e}")
            return False

        try:
            springs_df = pd.read_csv(latest_springs) if latest_springs else pd.DataFrame()
            print(f"✓ SPRINGS leído: {len(springs_df)} filas")
        except Exception as e:
            print(f"⚠️ Error leyendo SPRINGS (DataFrame vacío): {e}")
            springs_df = pd.DataFrame()

        # ── Estado del mercado ──────────────────────────────────────────────
        market_healthy = False
        market_health_score = 0.0
        if 'Market_Healthy' in all_df.columns and not all_df.empty:
            market_healthy      = bool(all_df['Market_Healthy'].iloc[0])
            market_health_score = safe_float(all_df['Market_Health_Score'].iloc[0])

        # ── Métricas de resumen ─────────────────────────────────────────────
        spring_count      = len(springs_df)
        test_active_count = 0
        if not springs_df.empty and 'Entry_Status' in springs_df.columns:
            test_active_count = int(
                springs_df['Entry_Status'].str.contains('Test Activo', na=False).sum()
            )

        # Estadísticas de invalidación (sobre el universo completo)
        total_springs_raw = int(all_df['Spring_Detected'].sum()) \
                            if 'Spring_Detected' in all_df.columns else 0
        failed_count = int(all_df['Spring_Failed'].sum()) \
                       if 'Spring_Failed' in all_df.columns else 0
        stale_count  = int(all_df['Spring_Stale'].sum()) \
                       if 'Spring_Stale' in all_df.columns else 0

        avg_prob = round(springs_df['Probability_Score'].mean(), 1) \
                   if not springs_df.empty and 'Probability_Score' in springs_df.columns else 0
        avg_pot  = round(springs_df['Potential_Score'].mean(), 1) \
                   if not springs_df.empty and 'Potential_Score' in springs_df.columns else 0

        dashboard_data = {
            "timestamp":   datetime.now().isoformat(),
            "market_date": datetime.now().strftime("%Y-%m-%d"),
            "strategy":    "Wyckoff Spring + Volume Profile",

            # Estado del mercado (visible en portada del dashboard)
            "market_context": {
                "healthy":      market_healthy,
                "health_score": market_health_score,
                "status_label": "ALCISTA ✅" if market_healthy else "BAJISTA ⚠️",
                "description":  "S&P 500 sobre MA200 — condiciones favorables para Springs"
                                if market_healthy
                                else "S&P 500 bajo MA200 — Springs con menor probabilidad de éxito"
            },

            "summary": {
                "total_analyzed":     len(all_df),
                "springs_detected":   spring_count,        # solo operables (activos)
                "springs_raw_total":  total_springs_raw,   # incluye fallidos/caducos
                "springs_failed":     failed_count,        # invalidados (Close bajo Spring Low)
                "springs_stale":      stale_count,         # >30 días sin Test
                "tests_active":       test_active_count,
                "detection_rate":     round(spring_count / len(all_df) * 100, 2) if len(all_df) > 0 else 0,
                "avg_prob_score":     avg_prob,
                "avg_pot_score":      avg_pot,
                "message": f"{spring_count} Springs ACTIVOS | {test_active_count} en zona de entrada "
                           f"| {failed_count} fallidos, {stale_count} caducos | "
                           f"Mercado {'alcista ✅' if market_healthy else 'bajista ⚠️'}"
            },

            "top_picks": [],
            "market_analysis": {},

            "wyckoff_criteria": {
                "volume_profile":      f"VPVR {252} días (1 año) → POC + HVN",
                "structural_support":  "Mínimo estructural S1 de 130 días (~6 meses) "
                                       "ESTABLECIDO antes de la ventana de búsqueda del Spring (60 días)",
                "confluence_filter":   "S1 dentro del 1% de un HVN o del POC (score gradual)",
                "spring_window":       "Búsqueda del Spring limitada a los últimos 60 días (frescura)",
                "spring_conditions": [
                    "Low < S1 (perfora soporte)",
                    "Close > S1 (cierra encima)",
                    "Cierre en tercio superior ≥67% de la vela",
                    "Volumen > SMA(20) × 1.5"
                ],
                "test_conditions": [
                    "Retroceso a S1 (±0.5%)",
                    "Volumen < SMA(20)",
                    "Volumen decreciente respecto al día anterior",
                    "Timing ideal: 5-25 días tras el Spring"
                ],
                "scoring": {
                    "probability_0_60": {
                        "market_health":  "0-15 pts (SPY sobre/bajo MA200)",
                        "test_timing":    "0-20 pts (5-25 días = ideal)",
                        "obv_base":       "0-15 pts (OBV alcista = acumulación)",
                        "sector_rank":    "0-10 pts (sector top 50% del universo)"
                    },
                    "potential_0_40": {
                        "base_width":    "0-15 pts (Wyckoff Cause: días en rango)",
                        "rr_ratio_tp2":  "0-15 pts (R:R ≥ 4 = máximo)",
                        "spring_depth":  "0-10 pts (shake-out más profundo = más absorción)"
                    }
                },
                "risk_management": {
                    "stop_loss": "Mínimo Spring − 0.5 × ATR(14)",
                    "tp1":       "Resistencia local 60 días previos al Spring (50% posición)",
                    "tp2":       "Siguiente HVN superior o R:R mínimo 1:3.5 (50% restante)",
                    "breakeven": "SL → entrada al activarse TP1"
                }
            }
        }

        # ── Top Picks ────────────────────────────────────────────────────────
        source_df = springs_df if not springs_df.empty else all_df
        if not source_df.empty and 'Wyckoff_Score' in source_df.columns:
            source_df = source_df.copy()
            if 'Entry_Status' in source_df.columns:
                source_df['_priority'] = source_df['Entry_Status'].apply(
                    lambda x: 0 if 'Test Activo'     in str(x) else
                              1 if 'Test Completado' in str(x) else 2
                )
                top_stocks = source_df.sort_values(
                    ['_priority', 'Wyckoff_Score'], ascending=[True, False]
                ).head(10)
            else:
                top_stocks = source_df.nlargest(10, 'Wyckoff_Score')

            for i, (_, row) in enumerate(top_stocks.iterrows()):
                entry_status = str(row.get('Entry_Status', 'Sin Señal'))
                rs    = safe_float(row.get('RS_Rating', 0))
                score = safe_float(row.get('Wyckoff_Score', 0))
                prob  = safe_float(row.get('Probability_Score', 0))
                pot   = safe_float(row.get('Potential_Score', 0))
                price = safe_float(row.get('Current_Price', 0))

                pick = {
                    "rank":    i + 1,
                    "symbol":  str(row['Symbol']),
                    "company": str(row.get('Company_Name', 'N/A'))[:30],
                    "sector":  str(row.get('Sector', 'N/A')),
                    "industry":str(row.get('Industry', 'N/A')),
                    "price":   price,

                    # Scores
                    "wyckoff_score":     score,
                    "probability_score": prob,
                    "potential_score":   pot,

                    # Estado de entrada
                    "entry_status": {
                        "status": entry_status,
                        "icon":   get_entry_status_icon(entry_status)
                    },

                    # Contexto de mercado y sector
                    "market_context": {
                        "market_healthy":      safe_bool(row.get('Market_Healthy', True)),
                        "market_health_score": safe_float(row.get('Market_Health_Score', 0)),
                        "industry_rank":       safe_float(row.get('Industry_Rank', 50)),
                    },

                    # RS
                    "relative_strength": {
                        "rs_rating": rs,
                        "label":     get_rs_strength_label(rs)
                    },

                    # Niveles Wyckoff
                    "wyckoff_levels": {
                        "s1_level":           safe_float(row.get('S1_Level')),
                        "poc_level":          safe_float(row.get('POC_Level')),
                        "hvn_count":          int(safe_float(row.get('HVN_Count', 0))),
                        "confluence_valid":   safe_bool(row.get('Confluence_Valid', False)),
                        "confluence_score":   safe_float(row.get('Confluence_Score', 0)),
                        "nearest_confluence": safe_float(row.get('Nearest_Confluence', 0)),
                    },

                    # Spring (incluye estado de validación)
                    "spring": {
                        "detected":        safe_bool(row.get('Spring_Detected', False)),
                        "date":            str(row.get('Spring_Date', '')),
                        "low":             safe_float(row.get('Spring_Low', 0)),
                        "volume_ratio":    safe_float(row.get('Spring_Volume_Ratio', 0)),
                        "close_position":  safe_float(row.get('Spring_Close_Position', 0)),
                        "depth_pct":       safe_float(row.get('Spring_Depth_Pct', 0)),
                        "failed":          safe_bool(row.get('Spring_Failed', False)),
                        "fail_date":       str(row.get('Spring_Fail_Date', '')),
                        "stale":           safe_bool(row.get('Spring_Stale', False)),
                        "is_actionable":   safe_bool(row.get('Is_Actionable', False)),
                    },

                    # Calidad de la base
                    "base_quality": {
                        "obv_trend":       safe_float(row.get('OBV_Trend_Base', 0)),
                        "base_width_days": int(safe_float(row.get('Base_Width_Days', 0))),
                        "obv_positive":    safe_float(row.get('OBV_Trend_Base', 0)) > 0,
                    },

                    # Test — timing_days es None si no hay Test (evita "0d" engañoso)
                    "test": {
                        "detected":      safe_bool(row.get('Test_Detected', False)),
                        "date":          str(row.get('Test_Date', '')),
                        "volume_ratio":  safe_float(row.get('Test_Volume_Ratio', 0)),
                        "timing_days":   int(safe_float(row.get('Test_Timing_Days', 0)))
                                         if safe_bool(row.get('Test_Detected', False)) else None,
                        "timing_score":  safe_float(row.get('Test_Timing_Score', 0)),
                    },

                    # Gestión de riesgo (SL incluye margen de 0.5×ATR anti-volatilidad)
                    "risk_management": {
                        "entry_price":   safe_float(row.get('Entry_Price', 0)),
                        "sl":            safe_float(row.get('SL', 0)),
                        "sl_explanation":"Spring Low − 0.5×ATR(14) (margen anti-volatilidad)",
                        "tp1":           safe_float(row.get('TP1', 0)),
                        "tp2":           safe_float(row.get('TP2', 0)),
                        "risk_pct":      safe_float(row.get('Risk_Pct', 0)),
                        "rr_tp1":        safe_float(row.get('RR_TP1', 0)),
                        "rr_tp2":        safe_float(row.get('RR_TP2', 0)),
                        "atr":           safe_float(row.get('ATR', 0)),
                        # Distancia precio_actual → SL (cuánto riesgo si se entra al precio actual)
                        "current_to_sl_pct": round(
                            (price - safe_float(row.get('SL', 0))) / price * 100, 2
                        ) if price > 0 and safe_float(row.get('SL', 0)) > 0 else 0,
                    }
                }
                dashboard_data["top_picks"].append(pick)

            print(f"✓ {len(dashboard_data['top_picks'])} picks añadidos al dashboard")

        # ── Análisis de mercado ───────────────────────────────────────────────
        if not springs_df.empty:
            entry_dist = {}
            if 'Entry_Status' in springs_df.columns:
                entry_dist = springs_df['Entry_Status'].value_counts().to_dict()

            sector_springs = {}
            if 'Sector' in springs_df.columns:
                sector_springs = springs_df['Sector'].value_counts().head(5).to_dict()

            score_dist = {}
            if 'Wyckoff_Score' in springs_df.columns:
                score_dist = {
                    "score_80_plus": int((springs_df['Wyckoff_Score'] >= 80).sum()),
                    "score_60_79":   int(((springs_df['Wyckoff_Score'] >= 60) & (springs_df['Wyckoff_Score'] < 80)).sum()),
                    "score_40_59":   int(((springs_df['Wyckoff_Score'] >= 40) & (springs_df['Wyckoff_Score'] < 60)).sum()),
                    "score_below_40":int((springs_df['Wyckoff_Score'] < 40).sum()),
                }

            obv_positive = 0
            base_wide    = 0
            if 'OBV_Trend_Base' in springs_df.columns:
                obv_positive = int((springs_df['OBV_Trend_Base'] > 0).sum())
            if 'Base_Width_Days' in springs_df.columns:
                base_wide = int((springs_df['Base_Width_Days'] >= 50).sum())

            confluence_rate = 0.0
            if 'Confluence_Valid' in all_df.columns and len(all_df) > 0:
                confluence_rate = round(all_df['Confluence_Valid'].sum() / len(all_df) * 100, 1)

            dashboard_data["market_analysis"] = {
                "entry_distribution":    entry_dist,
                "sector_springs":        sector_springs,
                "score_distribution":    score_dist,
                "avg_prob_score":        avg_prob,
                "avg_pot_score":         avg_pot,
                "obv_positive_count":    obv_positive,
                "base_wide_count":       base_wide,
                "confluence_rate_pct":   confluence_rate,
                "rs_above_70_universe":  int((all_df['RS_Rating'] >= 70).sum())
                                         if 'RS_Rating' in all_df.columns else 0,
            }
            print("✓ Análisis de mercado calculado")

        # ── Guardar JSON ─────────────────────────────────────────────────────
        os.makedirs('docs', exist_ok=True)
        json_path = 'docs/data.json'

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(convert_numpy_types(dashboard_data), f, indent=2, ensure_ascii=False)

        size = os.path.getsize(json_path)
        print(f"✅ Dashboard creado: {json_path} ({size} bytes)")
        print(f"📊 Resumen: {spring_count} springs | {test_active_count} entradas activas | "
              f"Mercado {'alcista ✅' if market_healthy else 'bajista ⚠️'}")

        with open('docs/last_update.txt', 'w') as f:
            f.write(datetime.now().isoformat())
        print("✓ last_update.txt actualizado")

        return True

    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_wyckoff_dashboard_data()
    if success:
        print("\n✅ SUCCESS: Dashboard Wyckoff Spring creado")
        print("📱 Abre docs/index.html en tu navegador")
    else:
        print("\n❌ FAILED: Revisar errores arriba")
