# create_dashboard_data.py
import pandas as pd
import json
import glob
import os
from datetime import datetime

def create_dashboard_data():
    """Convierte los resultados del script en datos JSON para el dashboard"""
    
    # Buscar el archivo de datos filtrados más reciente
    filtered_files = glob.glob("*_FILTERED_ONLY_*.csv")
    all_files = glob.glob("*_ALL_DATA_*.csv")
    
    if not filtered_files:
        print("No se encontraron archivos filtrados")
        return
    
    # Obtener el archivo más reciente
    latest_filtered = max(filtered_files, key=os.path.getctime)
    latest_all = max(all_files, key=os.path.getctime) if all_files else None
    
    print(f"Procesando: {latest_filtered}")
    
    # Leer datos
    filtered_df = pd.read_csv(latest_filtered)
    all_df = pd.read_csv(latest_all) if latest_all else pd.DataFrame()
    
    # Crear estructura para el dashboard
    dashboard_data = {
        "timestamp": datetime.now().isoformat(),
        "market_date": datetime.now().strftime("%Y-%m-%d"),
        "summary": {
            "total_analyzed": len(all_df) if not all_df.empty else 0,
            "passed_filters": len(filtered_df),
            "filter_rate": round((len(filtered_df) / len(all_df) * 100), 1) if not all_df.empty else 0
        },
        "top_picks": [],
        "market_trends": {},
        "filter_criteria": {
            "volume_50d_min": "300,000",
            "price_vs_ma50": "0% a +5%",
            "ma200_trend": "Positiva",
            "last_day": "Positivo",
            "earnings": "Positivos último trimestre",
            "volume_boost": "+25% vs promedio 50d"
        }
    }
    
    if not filtered_df.empty:
        # Calcular scores como en el script original
        trend_scores = {
            'Alcista fuerte': 100,
            'Alcista': 80,
            'Lateral/Mixta': 60,
            'Bajista': 20,
            'Bajista fuerte': 0
        }
        
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
                    "volume_50d_millions": round(row['Volume_50d_Avg'] / 1000000, 1) if pd.notna(row['Volume_50d_Avg']) else 0
                },
                "ma_levels": {
                    "ma_10": round(row['MA_10'], 2) if pd.notna(row['MA_10']) else 0,
                    "ma_21": round(row['MA_21'], 2) if pd.notna(row['MA_21']) else 0,
                    "ma_50": round(row['MA_50'], 2) if pd.notna(row['MA_50']) else 0,
                    "ma_200": round(row['MA_200'], 2) if pd.notna(row['MA_200']) else 0
                }
            }
            dashboard_data["top_picks"].append(pick)
        
        # Tendencias del mercado
        if 'MA_Trend' in filtered_df.columns:
            trend_counts = filtered_df['MA_Trend'].value_counts().to_dict()
            dashboard_data["market_trends"] = {
                trend: int(count) for trend, count in trend_counts.items()
            }
        
        # Estadísticas adicionales
        dashboard_data["statistics"] = {
            "avg_volume_50d_millions": round(filtered_df['Volume_50d_Avg'].mean() / 1000000, 1),
            "avg_volume_ratio": round(filtered_df['Volume_Ratio_vs_50d'].mean(), 2),
            "avg_price_vs_ma50": round(filtered_df['Price_vs_MA50_Pct'].mean(), 1),
            "avg_last_day_change": round(filtered_df['Last_Day_Change_Pct'].mean(), 1),
            "price_range_vs_ma50": {
                "min": round(filtered_df['Price_vs_MA50_Pct'].min(), 1),
                "max": round(filtered_df['Price_vs_MA50_Pct'].max(), 1)
            }
        }
    
    # Crear directorio docs si no existe
    os.makedirs('docs', exist_ok=True)
    
    # Guardar JSON
    with open('docs/data.json', 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Dashboard data creado: docs/data.json")
    print(f"✓ Top picks encontrados: {len(dashboard_data['top_picks'])}")
    
    # Crear archivo de última actualización
    with open('docs/last_update.txt', 'w') as f:
        f.write(datetime.now().isoformat())

if __name__ == "__main__":
    create_dashboard_data()