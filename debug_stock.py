# debug_stock.py
import yfinance as yf
import pandas as pd
import json
from pprint import pprint

# Importa la clase principal desde tu script original
from script_automated import MinerviniStockScreener

# --- CONFIGURACIÓN ---
# ▼▼▼ ¡AQUÍ ES DONDE PONES LA ACCIÓN QUE QUIERES DEBUGEAR! ▼▼▼
TICKER_TO_DEBUG = "ISSC"  # Cambia "NVDA" por el símbolo que quieras analizar
# Simula un RS Rating para el análisis. Minervini requiere >= 70.
# Puedes cambiar este valor para ver cómo afecta al resultado.
SIMULATED_RS_RATING = 85 
# --- FIN DE LA CONFIGURACIÓN ---

def debug_single_stock(symbol, rs_rating):
    """
    Ejecuta el análisis Minervini completo para una única acción y muestra los resultados detallados.
    """
    print(f"🕵️  Iniciando debug para: {symbol}")
    print(f"📊  Simulando un RS Rating de: {rs_rating} (el filtro requiere >= 70)")
    print("-" * 40)

    screener = MinerviniStockScreener()
    
    # 1. Descargar datos históricos para la acción
    print(f"1. Descargando datos históricos ('2y') para {symbol}...")
    try:
        # Usamos yf.Ticker para obtener los datos de una sola acción
        ticker_obj = yf.Ticker(symbol)
        hist_df = ticker_obj.history(period="2y", auto_adjust=True)
        
        if hist_df.empty or len(hist_df) < 252:
            print(f"❌ Error: No se pudieron descargar suficientes datos para {symbol}. Se necesitan al menos 252 días.")
            return
        print("✓ Datos históricos descargados.")
    except Exception as e:
        print(f"❌ Error al descargar datos históricos: {e}")
        return

    # 2. Descargar información fundamental (.info)
    print(f"2. Descargando datos fundamentales (.info) para {symbol}...")
    try:
        ticker_info = ticker_obj.info
        if not ticker_info or 'sector' not in ticker_info:
             print(f"❌ Error: .info devuelto vacío o incompleto para {symbol}.")
             # Aún así intentamos continuar, puede que algunos filtros fallen pero otros funcionen
             ticker_info = {}
        print("✓ Datos fundamentales descargados.")
    except Exception as e:
        print(f"❌ Error al descargar .info: {e}")
        # Continuamos sin datos fundamentales para ver los filtros técnicos
        ticker_info = {}

    # 3. Calcular Medias Móviles
    print("3. Calculando Medias Móviles (50, 150, 200)...")
    hist_with_ma = screener.calculate_moving_averages(hist_df)
    print("✓ Medias Móviles calculadas.")

    # 4. Ejecutar el análisis Minervini
    print("4. Ejecutando el análisis completo de 11 filtros Minervini...")
    analysis_result = screener.get_minervini_analysis(
        df=hist_with_ma, 
        rs_rating=rs_rating, 
        ticker_info=ticker_info, 
        symbol=symbol
    )
    print("✓ Análisis completado.")
    print("-" * 40)

    # 5. Mostrar los resultados de forma clara
    print(f"✅ RESULTADOS DETALLADOS PARA: {TICKER_TO_DEBUG} ✅")
    print("-" * 40)

    if analysis_result is None:
        print("‼️  ACCIÓN DESCARTADA POR COMPLETO.")
        print("   Razón principal: Beneficios negativos o nulos. El script está configurado para ignorar estas acciones.")
        return

    # Usamos pprint para una visualización más limpia del diccionario
    pprint(analysis_result)

    # Imprimir un resumen más legible
    print("\n" + "-"*40)
    print("🔍 RESUMEN DEL ANÁLISIS:")
    print(f"  - ¿Pasa TODOS los filtros?: {'SÍ' if analysis_result.get('passes_all_filters') else 'NO'}")
    print(f"  - Razón final del filtro: {analysis_result.get('filter_reasons', ['N/A'])[0]}")
    print(f"  - Stage Analysis: {analysis_result.get('stage_analysis', 'N/A')}")
    print(f"  - Minervini Score calculado: {analysis_result.get('minervini_score', 'N/A')}")
    print("-" * 40)
    print("\n💡 Para entender el resultado, revisa el diccionario de arriba.")
    print("   - 'passes_all_filters': te dice si pasó todo.")
    print("   - 'filter_reasons': te da el motivo exacto por el que fue aceptada o rechazada.")
    print("   - Compara los valores de 'ma_50', 'ma_150', 'current_price', etc., con los criterios del README.")


if __name__ == "__main__":
    if not TICKER_TO_DEBUG or TICKER_TO_DEBUG == "TICKER_AQUÍ":
        print("Por favor, edita este script y cambia la variable 'TICKER_TO_DEBUG' por la acción que quieres analizar.")
    else:
        debug_single_stock(TICKER_TO_DEBUG, SIMULATED_RS_RATING)