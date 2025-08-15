# create_dashboard_data.py - VERSIÓN MINERVINI SEPA CON SCORING
import pandas as pd
import numpy as np
import json
import glob
import os
from datetime import datetime

def get_stage_icon(stage):
    """Devuelve icono según Stage Analysis"""
    if "Stage 2" in stage:
        return "🚀"
    elif "Stage 1" in stage or "Stage 3" in stage:
        return "⏳"
    elif "Stage 4" in stage:
        return "📉"
    else:
        return "❓"

def get_rs_strength_label(rs_rating):
    """Devuelve etiqueta de fortaleza relativa"""
    if rs_rating >= 90:
        return "💪 Exceptional"
    elif rs_rating >= 80:
        return "🔥 Strong"
    elif rs_rating >= 70:
        return "✅ Good"
    elif rs_rating >= 50:
        return "⚠️ Average"
    else:
        return "❌ Weak"

def create_minervini_dashboard_data():
    """Convierte los resultados Minervini en datos JSON para dashboard"""
    
    print("=== CREATE MINERVINI DASHBOARD DATA ===")
    
    try:
        # Buscar archivos Minervini
        stage2_files = glob.glob("*_STAGE2_ONLY_*.csv")
        all_files = glob.glob("*_ALL_DATA_*.csv")
        
        print(f"Archivos STAGE2 encontrados: {stage2_files}")
        print(f"Archivos ALL_DATA encontrados: {all_files}")
        
        if not all_files:
            print("❌ No se encontraron archivos ALL_DATA")
            print("💡 Ejecuta primero: python script_automated.py")
            return False
        
        # Obtener archivos más recientes
        latest_all = max(all_files, key=os.path.getctime)
        latest_stage2 = max(stage2_files, key=os.path.getctime) if stage2_files else None
        
        print(f"Procesando archivo ALL_DATA: {latest_all}")
        print(f"Procesando archivo STAGE2: {latest_stage2 if latest_stage2 else 'Ninguno'}")
        
        # Leer datos
        try:
            all_df = pd.read_csv(latest_all)
            print(f"✓ ALL_DATA leído: {len(all_df)} filas")
        except Exception as e:
            print(f"❌ Error leyendo ALL_DATA: {e}")
            return False
            
        try:
            stage2_df = pd.read_csv(latest_stage2) if latest_stage2 else pd.DataFrame()
            print(f"✓ STAGE2 leído: {len(stage2_df)} filas")
        except Exception as e:
            print(f"⚠️ Error leyendo STAGE2 (usando DataFrame vacío): {e}")
            stage2_df = pd.DataFrame()
        
        # Crear estructura del dashboard Minervini
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "market_date": datetime.now().strftime("%Y-%m-%d"),
            "summary": {
                "total_analyzed": len(all_df) if not all_df.empty else 0,
                "stage2_stocks": len(stage2_df),
                "success_rate": round((len(stage2_df) / len(all_df) * 100), 1) if not all_df.empty and len(stage2_df) > 0 else 0,
                "avg_minervini_score": round(all_df['Minervini_Score'].mean(), 1) if not all_df.empty and 'Minervini_Score' in all_df.columns else 0,
                "message": "Stage 2 stocks encontrados" if len(stage2_df) > 0 else "Sin Stage 2 stocks hoy"
            },
            "top_picks": [],
            "market_analysis": {},
            "minervini_criteria": {
                "technical_filters": [
                    "Price > MA150 y MA200",
                    "MA150 > MA200", 
                    "MA200 trending up ≥1 mes",
                    "Price > MA50 > MA150 > MA200",
                    "Price ≥30% above 52w low",
                    "Price within 25% of 52w high",
                    "RS Rating ≥70",
                    "VCP/Institutional accumulation"
                ],
                "fundamental_filters": [
                    "Strong Earnings ≥25% YoY",
                    "Revenue ≥20% + ROE ≥17%",
                    "Institutional Evidence (5/8 criterios híbridos)"
                ],
                "scoring_system": {
                    "stage_analysis": "0-40 pts (Stage 2 = 40)",
                    "rs_rating": "0-30 pts (RS 90+ = 27+)",
                    "position_52w": "0-20 pts (cerca high + lejos low)",
                    "patterns": "0-10 pts (VCP + accumulation)"
                }
            }
        }
        
        print(f"Dashboard Minervini estructura creada")
        print(f"Summary: {dashboard_data['summary']}")
        
        # Procesar datos para el ranking
        if not all_df.empty and 'Minervini_Score' in all_df.columns:
            print("Procesando ranking por Minervini Score...")
            
            # Ordenar por Minervini Score descendente
            all_sorted = all_df.sort_values('Minervini_Score', ascending=False)
            
            # Top 15 para dashboard (mostraremos top 10, pero calculamos más por si hay empates)
            top_stocks = all_sorted.head(15)
            
            for i, (_, row) in enumerate(top_stocks.head(10).iterrows()):
                stage = row.get('Stage_Analysis', 'Unknown')
                rs_rating = row.get('RS_Rating', 0)
                score = row.get('Minervini_Score', 0)
                
                # Calcular métricas adicionales
                dist_high = row.get('Distance_To_52w_High', 0)
                dist_low = row.get('Distance_From_52w_Low', 0)
                
                # Usar .get con valores por defecto para limpiar el código y evitar errores
                pick = {
                    "rank": i + 1,
                    "symbol": str(row['Symbol']),
                    "company": str(row.get('Company_Name', 'N/A')[:30]),
                    "sector": str(row.get('Sector', 'N/A')),
                    "price": float(row.get('Current_Price', 0.0)),
                    "minervini_score": float(row.get('Minervini_Score', 0.0)),
                    "stage_analysis": {
                        "stage": str(stage),
                        "icon": get_stage_icon(stage),
                        "passes_all_filters": bool(row.get('Passes_All_Filters', False))
                    },
                    "relative_strength": {
                        "rs_rating": float(row.get('RS_Rating', 0.0)),
                        "strength_label": get_rs_strength_label(float(row.get('RS_Rating', 0.0)))
                    },
                    "position_52w": {
                        "distance_to_high": float(row.get('Distance_To_52w_High', 0.0)),
                        "distance_from_low": float(row.get('Distance_From_52w_Low', 0.0)),
                        "high_52w": float(row.get('High_52w', 0.0)),
                        "low_52w": float(row.get('Low_52w', 0.0))
                    },
                    "technical_indicators": {
                        "vcp_detected": bool(row.get('VCP_Detected', False)),
                        "institutional_accumulation": bool(row.get('Institutional_Accumulation', False)),
                        "institutional_evidence": bool(row.get('Institutional_Evidence', False)),
                        "institutional_score": int(row.get('Institutional_Score', 0)),
                        "volume_50d_millions": round(row.get('Volume_50d_Avg', 0) / 1_000_000, 1)
                    },
                    "fundamental_metrics": {
                        "earnings_acceleration": bool(row.get('Earnings_Acceleration', False)),
                        "roe_strong": bool(row.get('ROE_Strong', False)),
                        "passes_technical": bool(row.get('Passes_Technical', False)),
                        "passes_fundamental": bool(row.get('Passes_Fundamental', False))
                    },
                    "entry_point": {
                        "signal": str(row.get('Entry_Signal', 'N/A')),
                        "is_extended": bool(row.get('Is_Extended', False))
                    },
                    "ma_levels": {
                        "ma_50": float(row['MA_50']) if pd.notna(row.get('MA_50')) else 0.0,
                        "ma_150": float(row['MA_150']) if pd.notna(row.get('MA_150')) else 0.0,
                        "ma_200": float(row['MA_200']) if pd.notna(row.get('MA_200')) else 0.0
                    }
                }
                dashboard_data["top_picks"].append(pick)
            
            print(f"✓ {len(dashboard_data['top_picks'])} acciones añadidas a top_picks")
        
        # Análisis del mercado por Stage
        if not all_df.empty and 'Stage_Analysis' in all_df.columns:
            stage_distribution = all_df['Stage_Analysis'].value_counts().to_dict()
            
            # Calcular scores promedio por stage
            stage_avg_scores = {}
            for stage in stage_distribution.keys():
                stage_stocks = all_df[all_df['Stage_Analysis'] == stage]
                if not stage_stocks.empty and 'Minervini_Score' in stage_stocks.columns:
                    stage_avg_scores[stage] = round(stage_stocks['Minervini_Score'].mean(), 1)
                else:
                    stage_avg_scores[stage] = 0
            
            # NUEVO: Calcular indicadores de amplitud de mercado
            pct_above_ma200 = 0
            if 'Current_Price' in all_df.columns and 'MA_200' in all_df.columns:
                valid_ma_stocks = all_df.dropna(subset=['Current_Price', 'MA_200'])
                if not valid_ma_stocks.empty:
                    above_ma200 = (valid_ma_stocks['Current_Price'] > valid_ma_stocks['MA_200']).sum()
                    pct_above_ma200 = round((above_ma200 / len(valid_ma_stocks)) * 100, 1)

            pct_rs_strong = 0
            if 'RS_Rating' in all_df.columns:
                valid_rs_stocks = all_df.dropna(subset=['RS_Rating'])
                if not valid_rs_stocks.empty:
                    strong_rs = (valid_rs_stocks['RS_Rating'] >= 70).sum()
                    pct_rs_strong = round((strong_rs / len(valid_rs_stocks)) * 100, 1)

            # NUEVO: Calcular % de acciones en Stage 2
            total_stocks_for_stage_pct = len(all_df.dropna(subset=['Stage_Analysis']))
            total_stage2 = stage_distribution.get("Stage 2 (Uptrend)", 0) + stage_distribution.get("Stage 2 (Developing)", 0)
            pct_in_stage2 = round((total_stage2 / total_stocks_for_stage_pct) * 100, 1) if total_stocks_for_stage_pct > 0 else 0

            dashboard_data["market_analysis"] = {
                "stage_distribution": stage_distribution,
                "stage_avg_scores": stage_avg_scores,
                "total_stage2": total_stage2,
                "market_health": "Strong" if len(stage2_df) > 0 else "Weak",
                # Datos de amplitud
                "pct_above_ma200": pct_above_ma200,
                "pct_rs_strong": pct_rs_strong,
                "pct_in_stage2": pct_in_stage2
            }
            
            print(f"✓ Análisis de mercado por stages calculado")
            print(f"✓ Indicadores de amplitud: >MA200: {pct_above_ma200}%, RS>70: {pct_rs_strong}%")
        
        # Análisis de eliminación Minervini
        dashboard_data["elimination_analysis"] = {
            "total_eliminated": len(all_df) - len(stage2_df),
            "elimination_rate": round(((len(all_df) - len(stage2_df)) / len(all_df) * 100), 1) if len(all_df) > 0 else 0,
            "top_reasons": {}
        }
        
        if len(all_df) > len(stage2_df):
            filter_reasons_count = {}
            total_stocks = len(all_df)
            
            for _, row in all_df.iterrows():
                if not row.get('Passes_All_Filters', False):
                    reasons = str(row.get('Filter_Reasons', '')).split(';')
                    for reason in reasons:
                        reason = reason.strip()
                        if reason and reason != "✅ PASA TODOS LOS FILTROS MINERVINI" and reason != "nan":
                            filter_reasons_count[reason] = filter_reasons_count.get(reason, 0) + 1
            
            # Top 10 razones para el dashboard
            for reason, count in sorted(filter_reasons_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                percentage = round((count / total_stocks) * 100, 1)
                dashboard_data["elimination_analysis"]["top_reasons"][reason] = {
                    "count": count,
                    "percentage": percentage
                }
            
            print(f"✓ Análisis de eliminación Minervini: {len(filter_reasons_count)} razones diferentes")
        
        # Estadísticas Minervini específicas
        if not all_df.empty:
            # Estadísticas de RS Rating
            rs_stats = {}
            if 'RS_Rating' in all_df.columns:
                rs_data = all_df['RS_Rating'].dropna()
                if not rs_data.empty:
                    rs_stats = {
                        "avg_rs_rating": round(rs_data.mean(), 1),
                        "rs_above_70": len(rs_data[rs_data >= 70]),
                        "rs_above_80": len(rs_data[rs_data >= 80]),
                        "rs_above_90": len(rs_data[rs_data >= 90])
                    }
            
            # Estadísticas de posición 52w
            position_stats = {}
            if 'Distance_To_52w_High' in all_df.columns:
                high_data = all_df['Distance_To_52w_High'].dropna()
                low_data = all_df['Distance_From_52w_Low'].dropna()
                if not high_data.empty and not low_data.empty:
                    position_stats = {
                        "avg_distance_to_high": round(high_data.mean(), 1),
                        "avg_distance_from_low": round(low_data.mean(), 1),
                        "near_highs_25pct": len(high_data[high_data <= 25]),
                        "above_low_30pct": len(low_data[low_data >= 30])
                    }
            
            dashboard_data["minervini_statistics"] = {
                "rs_rating_stats": rs_stats,
                "position_52w_stats": position_stats,
                "pattern_detection": {
                    "vcp_detected": all_df['VCP_Detected'].sum() if 'VCP_Detected' in all_df.columns else 0,
                    "institutional_accumulation": all_df['Institutional_Accumulation'].sum() if 'Institutional_Accumulation' in all_df.columns else 0,
                    "institutional_evidence": all_df['Institutional_Evidence'].sum() if 'Institutional_Evidence' in all_df.columns else 0,
                    "avg_institutional_score": round(all_df['Institutional_Score'].mean(), 1) if 'Institutional_Score' in all_df.columns else 0
                },
                "score_distribution": {
                    "score_80_plus": len(all_df[all_df['Minervini_Score'] >= 80]) if 'Minervini_Score' in all_df.columns else 0,
                    "score_60_79": len(all_df[(all_df['Minervini_Score'] >= 60) & (all_df['Minervini_Score'] < 80)]) if 'Minervini_Score' in all_df.columns else 0,
                    "score_40_59": len(all_df[(all_df['Minervini_Score'] >= 40) & (all_df['Minervini_Score'] < 60)]) if 'Minervini_Score' in all_df.columns else 0,
                    "score_below_40": len(all_df[all_df['Minervini_Score'] < 40]) if 'Minervini_Score' in all_df.columns else 0
                }
            }
            
            print("✓ Estadísticas Minervini específicas calculadas")
        
        # Crear directorio docs
        print("Creando directorio docs...")
        os.makedirs('docs', exist_ok=True)
        print("✓ Directorio docs creado/verificado")
        
        # Guardar JSON con conversión de tipos numpy
        json_path = 'docs/data.json'
        print(f"Guardando JSON Minervini en: {json_path}")
        
        def convert_numpy_types(obj):
            """Convierte tipos numpy/pandas a tipos JSON serializables"""
            import numpy as np
            if isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            else:
                return obj
        
        try:
            # Convertir todos los tipos numpy antes de serializar
            dashboard_data_clean = convert_numpy_types(dashboard_data)
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data_clean, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Dashboard Minervini creado: {json_path}")
            
            # Verificar archivo
            if os.path.exists(json_path):
                size = os.path.getsize(json_path)
                print(f"✅ Archivo verificado - Tamaño: {size} bytes")
                
                # Mostrar resumen del contenido Minervini
                print(f"📊 Resumen del dashboard Minervini:")
                print(f"   - Total analizadas: {dashboard_data['summary']['total_analyzed']}")
                print(f"   - Stage 2 stocks: {dashboard_data['summary']['stage2_stocks']}")
                print(f"   - Tasa de éxito: {dashboard_data['summary']['success_rate']}%")
                print(f"   - Score promedio: {dashboard_data['summary']['avg_minervini_score']}")
                print(f"   - Top picks: {len(dashboard_data['top_picks'])}")
                print(f"   - Eliminadas: {dashboard_data['elimination_analysis']['total_eliminated']}")
                print(f"   - Razones eliminación: {len(dashboard_data['elimination_analysis']['top_reasons'])}")
                
                # Mostrar distribución por stages
                if dashboard_data.get('market_analysis', {}).get('stage_distribution'):
                    print(f"   - Distribución por Stage:")
                    for stage, count in dashboard_data['market_analysis']['stage_distribution'].items():
                        print(f"     * {stage}: {count}")
                
            else:
                print("❌ El archivo no se pudo verificar")
                return False
                
        except Exception as e:
            print(f"❌ Error guardando JSON Minervini: {e}")
            return False
        
        # Crear archivo de última actualización
        try:
            with open('docs/last_update.txt', 'w') as f:
                f.write(datetime.now().isoformat())
            print("✓ Archivo last_update.txt creado")
        except Exception as e:
            print(f"⚠️ Error creando last_update.txt: {e}")
        
        print(f"🎉 Dashboard Minervini SEPA completamente generado!")
        return True
        
    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_minervini_dashboard_data()
    if success:
        print("\n✅ SUCCESS: Dashboard Minervini creado correctamente")
        print("📱 Abre docs/index.html en tu navegador")
        print("🎯 Sistema basado en metodología SEPA de Mark Minervini")
    else:
        print("\n❌ FAILED: Revisar errores arriba")