# debug_stock.py
import yfinance as yf
import pandas as pd
import json
from pprint import pprint

# Importa la clase principal desde tu script original
from script_automated import MinerviniStockScreener, get_ticker_info_with_cache

# --- CONFIGURACIÓN ---
# ▼▼▼ ¡AQUÍ ES DONDE PONES LA ACCIÓN QUE QUIERES DEBUGEAR! ▼▼▼
TICKER_TO_DEBUG = "RSI"  # Cambia "NVDA" por el símbolo que quieras analizar
# Simula un RS Rating para el análisis. Minervini requiere >= 70.
# Puedes cambiar este valor para ver cómo afecta al resultado.
SIMULATED_RS_RATING = 85
# Elige si el debug debe usar el sistema de caché o llamar siempre a la API en vivo.
USE_CACHE_IN_DEBUG = False # Poner en True para probar la lógica de caché.
# --- FIN DE LA CONFIGURACIÓN ---

def debug_single_stock(symbol, rs_rating):
    """
    Ejecuta el análisis Minervini en modo DEBUG para una única acción.
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
    if USE_CACHE_IN_DEBUG:
        print(f"2. Obteniendo datos fundamentales para {symbol} (usando sistema de caché)...")
        ticker_info = get_ticker_info_with_cache(symbol)
        print("✓ Datos fundamentales obtenidos vía caché.")
    else:
        print(f"2. Descargando datos fundamentales (.info) para {symbol} (llamada en vivo)...")
        try:
            ticker_info = ticker_obj.info
            if not ticker_info or 'sector' not in ticker_info:
                print(f"❌ Error: .info devuelto vacío o incompleto para {symbol}.")
                ticker_info = {}
            print("✓ Datos fundamentales descargados.")
        except Exception as e:
            print(f"❌ Error al descargar .info: {e}")
            ticker_info = {}

    # 2.5. Verificar datos fundamentales clave
    print("2.5. Verificando disponibilidad de datos fundamentales clave...")
    required_keys = ['earningsQuarterlyGrowth', 'returnOnEquity', 'netIncomeToCommon']
    missing_keys = [key for key in required_keys if key not in ticker_info or ticker_info[key] is None]
    
    if missing_keys:
        print(f"   ⚠️  AVISO: Faltan datos fundamentales clave en la respuesta de la API:")
        for key in missing_keys:
            print(f"      - '{key}' no encontrado o es None.")
        print("   Esto causará que los filtros fundamentales fallen, lo cual es el comportamiento esperado.")
    else:
        print("✓ Todos los datos fundamentales clave están presentes.")

    # 3. Calcular Medias Móviles
    print("3. Calculando Medias Móviles (50, 150, 200)...")
    hist_with_ma = screener.calculate_moving_averages(hist_df)
    print("✓ Medias Móviles calculadas.")

    # 4. Ejecutar el análisis Minervini
    print("\n" + "="*15 + f" INICIANDO ANÁLISIS MINERVINI PARA {symbol} " + "="*15)
    analysis_result = screener.get_minervini_analysis(
        df=hist_with_ma, 
        rs_rating=rs_rating, 
        ticker_info=ticker_info, 
        symbol=symbol,
        debug_mode=True  # <-- ¡AQUÍ ESTÁ LA MAGIA!
    )
    print("="*17 + " ANÁLISIS MINERVINI COMPLETADO " + "="*17 + "\n")

    # 5. Mostrar los resultados de forma clara
    print(f"✅ RESUMEN FINAL PARA: {TICKER_TO_DEBUG} ✅")
    print("-" * 40)

    if analysis_result is None:
        print("‼️  ACCIÓN DESCARTADA POR COMPLETO.")
        print("   Razón principal: Beneficios negativos o nulos. El script está configurado para ignorar estas acciones.")
        return
    
    print(f"  - ¿Pasa TODOS los filtros?: {'SÍ' if analysis_result.get('passes_all_filters') else 'NO'}")
    print(f"  - Razón final del filtro: {analysis_result.get('filter_reasons', ['N/A'])[0]}")
    print(f"  - Stage Analysis: {analysis_result.get('stage_analysis', 'N/A')}")
    print(f"  - Minervini Score calculado: {analysis_result.get('minervini_score', 'N/A')}")
    print(f"  - Señal de Entrada: {analysis_result.get('entry_signal', 'N/A')}")

if __name__ == "__main__":
    if not TICKER_TO_DEBUG or TICKER_TO_DEBUG == "TICKER_AQUÍ":
        print("Por favor, edita este script y cambia la variable 'TICKER_TO_DEBUG' por la acción que quieres analizar.")
    else:
        debug_single_stock(TICKER_TO_DEBUG, SIMULATED_RS_RATING)