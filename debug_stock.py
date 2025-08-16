# debug_stock.py
import yfinance as yf
import pandas as pd
import json
from pprint import pprint
# Importa la clase principal desde tu script original
from script_automated import MinerviniStockScreener

# --- CONFIGURACIÓN ---
# ▼▼▼ ¡AQUÍ ES DONDE PONES LA ACCIÓN QUE QUIERES DEBUGEAR! ▼▼▼
TICKER_TO_DEBUG = "RSI"  # Cambia "NVDA" por el símbolo que quieras analizar
# --- FIN DE LA CONFIGURACIÓN ---

def calculate_real_rs_rating(stock_df, benchmark_df):
    """Calcula un RS Rating realista comparando el rendimiento del último año contra un benchmark (SPY)."""
    if len(stock_df) < 252 or len(benchmark_df) < 252:
        print("   ⚠️  Datos insuficientes para calcular RS Rating real. Usando 50 como valor por defecto.")
        return 50.0

    # Rendimiento del último año (252 días de trading)
    stock_perf = (stock_df['Close'].iloc[-1] / stock_df['Close'].iloc[-252]) - 1
    benchmark_perf = (benchmark_df['Close'].iloc[-1] / benchmark_df['Close'].iloc[-252]) - 1
    
    # Fórmula simple para un RS Rating proxy: 50 es igual al mercado.
    # Cada 1% de rendimiento superior al mercado suma 1 punto al RS.
    rs_rating = 50.0 + (stock_perf - benchmark_perf) * 100
    
    print(f"   - Rendimiento {TICKER_TO_DEBUG} (1A): {stock_perf:.2%}")
    print(f"   - Rendimiento SPY (1A): {benchmark_perf:.2%}")
    
    # Limitar el RS Rating a un rango realista (1-99)
    return max(1, min(99, rs_rating))

def debug_single_stock(symbol):
    """
    Ejecuta el análisis Minervini en modo DEBUG para una única acción.
    """
    print(f"🕵️  Iniciando debug para: {symbol}")
    print("-" * 40)

    screener = MinerviniStockScreener()
    
    # 1. Descargar datos históricos para la acción
    print(f"1. Descargando datos históricos ('2y') para {symbol} y benchmark (SPY)...")
    try:
        # Descargar ambos tickers a la vez es más eficiente
        data = yf.download([symbol, 'SPY'], period="2y", auto_adjust=True, progress=False)
        hist_df = data.loc[:, (slice(None), symbol)].droplevel(1, axis=1)
        spy_df = data.loc[:, (slice(None), 'SPY')].droplevel(1, axis=1)
        
        if hist_df.empty or len(hist_df) < 252 or spy_df.empty:
            print(f"❌ Error: No se pudieron descargar suficientes datos para {symbol}. Se necesitan al menos 252 días.")
            return
        print("✓ Datos históricos descargados.")
    except Exception as e:
        print(f"❌ Error al descargar datos históricos: {e}")
        return

    # 1.5. Calcular RS Rating real
    print("1.5. Calculando RS Rating real vs. SPY...")
    rs_rating = calculate_real_rs_rating(hist_df, spy_df)
    print(f"📊 RS Rating calculado para {symbol}: {rs_rating:.1f} (el filtro requiere >= 70)")

    # 2. Descargar información fundamental (.info) - Siempre en vivo para el debug
    print(f"2. Descargando datos fundamentales (.info) para {symbol} (llamada en vivo)...")
    try:
        # Usamos yf.Ticker para obtener el .info
        ticker_info = yf.Ticker(symbol).info
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
        debug_single_stock(TICKER_TO_DEBUG)