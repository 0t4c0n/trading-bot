# create_dashboard_data.py - VERSIÓN CON ANÁLISIS DE ELIMINACIÓN
import pandas as pd
import json
import glob
import os
from datetime import datetime

def get_growth_type(row):
    """Determina qué tipo de crecimiento cumple la acción"""
    revenue_growth = row.get('Revenue_Growth_Positive', False)
    earnings_growth = row.get('Earnings_Growth_Positive', False)
    
    if revenue_growth and earnings_growth:
        return "Ingresos + Beneficios"
    elif revenue_growth:
        return "Ingresos"
    elif earnings_growth:
        return "Beneficios"
    else:
        return "N/A"

def create_dashboard_data():
    """Convierte los resultados del script en datos JSON para el dashboard"""
    
    print("=== CREATE DASHBOARD DATA - CON ANÁLISIS DE ELIMINACIÓN ===")
    
    try:
        # Buscar el archivo de datos filtrados más reciente
        filtered_files = glob.glob("*_FILTERED_ONLY_*.csv")
        all_files = glob.glob("*_ALL_DATA_*.csv")
        
        print(f"Archivos FILTERED encontrados: {filtered_files}")
        print(f"Archivos ALL_DATA encontrados: {all_files}")
        
        if not all_files:
            print("❌ No se encontraron archivos ALL_DATA")
            print("💡 Ejecuta primero: python script_automated.py")
            return False
        
        # Obtener el archivo más reciente
        latest_all = max(all_files, key=os.path.getctime)
        latest_filtered = max(filtered_files, key=os.path.getctime) if filtered_files else None
        
        print(f"Procesando archivo ALL_DATA: {latest_all}")
        print(f"Procesando archivo FILTERED: {latest_filtered if latest_filtered else 'Ninguno'}")
        
        # Leer datos
        try:
            all_df = pd.read_csv(latest_all)
            print(f"✓ ALL_DATA leído: {len(all_df)} filas")
        except Exception as e:
            print(f"❌ Error leyendo ALL_DATA: {e}")
            return False
            
        try:
            filtered_df = pd.read_csv(latest_filtered) if latest_filtered else pd.DataFrame()
            print(f"✓ FILTERED leído: {len(filtered_df)} filas")
        except Exception as e:
            print(f"⚠️ Error leyendo FILTERED (usando DataFrame vacío): {e}")
            filtered_df = pd.DataFrame()
        
        # Crear estructura para el dashboard
        dashboard_data = {
            "timestamp": datetime.now().isoformat(),
            "market_date": datetime.now().strftime("%Y-%m-%d"),
            "summary": {
                "total_analyzed": len(all_df) if not all_df.empty else 0,
                "passed_filters": len(filtered_df),
                "filter_rate": round((len(filtered_df) / len(all_df) * 100), 1) if not all_df.empty and len(filtered_df) > 0 else 0,
                "message": "Oportunidades encontradas" if len(filtered_df) > 0 else "Sin oportunidades hoy"
            },
            "top_picks": [],
            "market_trends": {},
            "filter_criteria": {
                "volume_50d_min": "300,000",
                "price_vs_ma50": "0% a +5%",
                "ma200_trend": "Positiva",
                "last_day": "Positivo",
                "earnings": "Positivos último trimestre",
                "volume_boost": "+25% vs promedio 50d",
                "growth_flexible": "🚀 Ingresos >+15% O Beneficios >+25%",
                "relative_strength": "💪 Outperform SPY +3% (20d)"
            }
        }
        
        print(f"Dashboard data estructura creada")
        print(f"Summary: {dashboard_data['summary']}")
        
        if not filtered_df.empty:
            print("Procesando acciones filtradas...")
            # Calcular scores como en el script original
            trend_scores = {
                'Alcista fuerte': 100,
                'Alcista': 80,
                'Lateral/Mixta': 60,
                'Bajista': 20,
                'Bajista fuerte': 0
            }
            
            try:
                filtered_df['Trend_Score'] = filtered_df['MA_Trend'].map(trend_scores).fillna(50)
                
                # Normalizar scores
                if filtered_df['Volume_Ratio_vs_50d'].max() > 0:
                    filtered_df['Volume_Score'] = (filtered_df['Volume_Ratio_vs_50d'] / filtered_df['Volume_Ratio_vs_50d'].max() * 50).fillna(0)
                else:
                    filtered_df['Volume_Score'] = 0
                    
                if filtered_df['Last_Day_Change_Pct'].max() > 0:
                    filtered_df['Day_Change_Score'] = (filtered_df['Last_Day_Change_Pct'] / filtered_df['Last_Day_Change_Pct'].max() * 30).fillna(0)
                else:
                    filtered_df['Day_Change_Score'] = 0
                    
                filtered_df['MA50_Score'] = filtered_df['Price_vs_MA50_Pct'].apply(
                    lambda x: 20 - abs(x - 2.5) * 4 if pd.notna(x) else 0
                )
                
                filtered_df['Total_Score'] = (
                    filtered_df['Trend_Score'] + 
                    filtered_df['Volume_Score'] + 
                    filtered_df['Day_Change_Score'] + 
                    filtered_df['MA50_Score']
                )
                
                # Ordenar por score
                filtered_sorted = filtered_df.sort_values('Total_Score', ascending=False)
                
                # Top 10 para el dashboard
                for i, (_, row) in enumerate(filtered_sorted.head(10).iterrows()):
                    vol_ratio_pct = ((row['Volume_Ratio_vs_50d'] - 1) * 100) if pd.notna(row['Volume_Ratio_vs_50d']) else 0
                    
                    pick = {
                        "rank": i + 1,
                        "symbol": row['Symbol'],
                        "company": row['Company_Name'][:30] if pd.notna(row['Company_Name']) else 'N/A',
                        "sector": row['Sector'] if pd.notna(row['Sector']) else 'N/A',
                        "price": round(row['Current_Price'], 2) if pd.notna(row['Current_Price']) else 0,
                        "score": round(row['Total_Score'], 1),
                        "metrics": {
                            "ma50_distance": round(row['Price_vs_MA50_Pct'], 1) if pd.notna(row['Price_vs_MA50_Pct']) else 0,
                            "last_day_change": round(row['Last_Day_Change_Pct'], 1) if pd.notna(row['Last_Day_Change_Pct']) else 0,
                            "volume_boost": round(vol_ratio_pct, 0),
                            "trend": row['MA_Trend'] if pd.notna(row['MA_Trend']) else 'N/A',
                            "volume_50d_millions": round(row['Volume_50d_Avg'] / 1000000, 1) if pd.notna(row['Volume_50d_Avg']) else 0,
                            "relative_strength": round(row['Relative_Strength_Value'], 1) if pd.notna(row['Relative_Strength_Value']) else 0,
                            "growth_type": get_growth_type(row)
                        },
                        "ma_levels": {
                            "ma_10": round(row['MA_10'], 2) if pd.notna(row['MA_10']) else 0,
                            "ma_21": round(row['MA_21'], 2) if pd.notna(row['MA_21']) else 0,
                            "ma_50": round(row['MA_50'], 2) if pd.notna(row['MA_50']) else 0,
                            "ma_200": round(row['MA_200'], 2) if pd.notna(row['MA_200']) else 0
                        }
                    }
                    dashboard_data["top_picks"].append(pick)
                
                print(f"✓ {len(dashboard_data['top_picks'])} acciones añadidas a top_picks")
                
                # Tendencias del mercado
                if 'MA_Trend' in filtered_df.columns:
                    trend_counts = filtered_df['MA_Trend'].value_counts().to_dict()
                    dashboard_data["market_trends"] = {
                        trend: int(count) for trend, count in trend_counts.items()
                    }
                    print(f"✓ Tendencias del mercado calculadas: {dashboard_data['market_trends']}")
                
            except Exception as e:
                print(f"⚠️ Error procesando acciones filtradas: {e}")
                print("Continuando con dashboard básico...")
        
        # AÑADIR ANÁLISIS DE RAZONES DE ELIMINACIÓN
        dashboard_data["elimination_analysis"] = {
            "total_eliminated": len(all_df) - len(filtered_df),
            "elimination_rate": round(((len(all_df) - len(filtered_df)) / len(all_df) * 100), 1) if len(all_df) > 0 else 0,
            "top_reasons": {}
        }
        
        if len(all_df) > len(filtered_df):  # Si hay acciones eliminadas
            filter_reasons_count = {}
            total_stocks = len(all_df)
            
            for _, row in all_df.iterrows():
                if not row['Passes_Filters']:
                    reasons = str(row['Filter_Reasons']).split(';')
                    for reason in reasons:
                        reason = reason.strip()
                        if reason and reason != "✅ PASA TODOS LOS FILTROS" and reason != "nan":
                            filter_reasons_count[reason] = filter_reasons_count.get(reason, 0) + 1
            
            # Top 10 razones para el dashboard
            for reason, count in sorted(filter_reasons_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                percentage = round((count / total_stocks) * 100, 1)
                dashboard_data["elimination_analysis"]["top_reasons"][reason] = {
                    "count": count,
                    "percentage": percentage
                }
            
            print(f"✓ Análisis de eliminación: {len(filter_reasons_count)} razones diferentes")
        
        # Estadísticas adicionales
        if filtered_df.empty:
            dashboard_data["statistics"] = {
                "message": "Sin acciones que pasen todos los filtros",
                "total_analyzed": len(all_df) if not all_df.empty else 0,
                "suggestions": [
                    "Los 8 filtros son muy selectivos para garantizar calidad",
                    "Incluye Relative Strength vs SPY para outperformance",
                    "Crecimiento flexible: Ingresos >15% O Beneficios >25%",
                    "Mercados volátiles pueden tener días sin oportunidades claras",
                    "Revisa el análisis mañana para nuevas oportunidades",
                    "Los filtros priorizan empresas con momentum superior al mercado"
                ]
            }
            print("✓ Estadísticas para dashboard sin resultados")
        else:
            try:
                dashboard_data["statistics"] = {
                    "avg_volume_50d_millions": round(filtered_df['Volume_50d_Avg'].mean() / 1000000, 1),
                    "avg_volume_ratio": round(filtered_df['Volume_Ratio_vs_50d'].mean(), 2),
                    "avg_price_vs_ma50": round(filtered_df['Price_vs_MA50_Pct'].mean(), 1),
                    "avg_last_day_change": round(filtered_df['Last_Day_Change_Pct'].mean(), 1),
                    "avg_relative_strength": round(filtered_df['Relative_Strength_Value'].mean(), 1) if 'Relative_Strength_Value' in filtered_df.columns else 0,
                    "price_range_vs_ma50": {
                        "min": round(filtered_df['Price_vs_MA50_Pct'].min(), 1),
                        "max": round(filtered_df['Price_vs_MA50_Pct'].max(), 1)
                    }
                }
                print("✓ Estadísticas completas calculadas")
            except Exception as e:
                print(f"⚠️ Error calculando estadísticas: {e}")
        
        # Crear directorio docs si no existe
        print("Creando directorio docs...")
        os.makedirs('docs', exist_ok=True)
        print("✓ Directorio docs creado/verificado")
        
        # Guardar JSON
        json_path = 'docs/data.json'
        print(f"Guardando JSON en: {json_path}")
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Dashboard data creado: {json_path}")
            
            # Verificar que se creó
            if os.path.exists(json_path):
                size = os.path.getsize(json_path)
                print(f"✅ Archivo verificado - Tamaño: {size} bytes")
                
                # Mostrar resumen del contenido
                print(f"📊 Resumen del dashboard:")
                print(f"   - Total analizadas: {dashboard_data['summary']['total_analyzed']}")
                print(f"   - Acciones filtradas: {dashboard_data['summary']['passed_filters']}")
                print(f"   - Top picks: {len(dashboard_data['top_picks'])}")
                print(f"   - Acciones eliminadas: {dashboard_data['elimination_analysis']['total_eliminated']}")
                print(f"   - Razones de eliminación: {len(dashboard_data['elimination_analysis']['top_reasons'])}")
                
            else:
                print("❌ El archivo no se pudo verificar")
                return False
                
        except Exception as e:
            print(f"❌ Error guardando JSON: {e}")
            return False
        
        # Crear archivo de última actualización
        try:
            with open('docs/last_update.txt', 'w') as f:
                f.write(datetime.now().isoformat())
            print("✓ Archivo last_update.txt creado")
        except Exception as e:
            print(f"⚠️ Error creando last_update.txt: {e}")
        
        print(f"🎉 Dashboard completamente generado con análisis de eliminación!")
        return True
        
    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_dashboard_data()
    if success:
        print("\n✅ SUCCESS: Dashboard creado correctamente")
        print("📱 Abre docs/index.html en tu navegador")
    else:
        print("\n❌ FAILED: Revisar errores arriba")