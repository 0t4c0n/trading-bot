# script_automated.py - Versión automatizada para GitHub Actions
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import json
import os
import sys
from io import StringIO

class USStockMovingAveragesExtractor:
    def __init__(self):
        self.stock_symbols = []
        
    def get_nyse_nasdaq_symbols(self):
        """Obtiene símbolos de NYSE y NASDAQ combinados"""
        all_symbols = []
        
        try:
            print("Obteniendo símbolos del NYSE...")
            nyse_symbols = self.get_exchange_symbols('NYSE')
            print(f"✓ NYSE: {len(nyse_symbols)} símbolos obtenidos")
            
            print("Obteniendo símbolos del NASDAQ...")
            nasdaq_symbols = self.get_exchange_symbols('NASDAQ')
            print(f"✓ NASDAQ: {len(nasdaq_symbols)} símbolos obtenidos")
            
            # Combinar y eliminar duplicados
            all_symbols = list(set(nyse_symbols + nasdaq_symbols))
            print(f"✓ Total combinado (sin duplicados): {len(all_symbols)} símbolos")
            
            return all_symbols
            
        except Exception as e:
            print(f"Error obteniendo símbolos: {e}")
            # Lista de respaldo con principales de ambos exchanges
            backup_symbols = self.get_backup_symbols()
            print(f"Usando lista de respaldo: {len(backup_symbols)} símbolos")
            return backup_symbols
    
    def get_exchange_symbols(self, exchange):
        """Obtiene símbolos de un exchange específico (NYSE o NASDAQ)"""
        try:
            # Método 1: Usando NASDAQ API
            url = "https://api.nasdaq.com/api/screener/stocks"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            params = {
                'tableonly': 'true',
                'limit': '25000',
                'exchange': exchange
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'table' in data['data']:
                    symbols = [row['symbol'] for row in data['data']['table']['rows']]
                    return symbols
            
            return []
            
        except Exception as e:
            print(f"Error obteniendo símbolos de {exchange}: {e}")
            return []
    
    def get_backup_symbols(self):
        """Lista de respaldo con principales acciones de NYSE y NASDAQ"""
        # Principales NYSE
        nyse_major = [
            # Financieros
            'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'AXP', 'USB', 'PNC', 'TFC',
            'COF', 'SCHW', 'BLK', 'SPGI', 'ICE', 'CME', 'MCO', 'AON', 'MMC',
            
            # Industriales
            'CAT', 'BA', 'GE', 'HON', 'LMT', 'RTX', 'MMM', 'UPS', 'DE', 'EMR',
            'ITW', 'ETN', 'PH', 'ROK', 'DOV', 'XYL', 'IEX', 'FTV', 'AME',
            
            # Consumo
            'WMT', 'HD', 'PG', 'KO', 'PEP', 'COST', 'TGT', 'LOW', 'NKE', 'SBUX',
            'MCD', 'DIS', 'CL', 'KMB', 'CHD', 'SJM', 'GIS', 'K', 'CPB',
            
            # Salud
            'JNJ', 'PFE', 'ABT', 'MRK', 'LLY', 'BMY', 'AMGN', 'GILD', 'MDT',
            'DHR', 'TMO', 'A', 'SYK', 'BSX', 'EW', 'HOLX', 'ZBH', 'BAX', 'BDX',
            
            # Energía
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PXD', 'KMI', 'OKE', 'WMB', 'EPD',
            'ET', 'MPLX', 'PSX', 'VLO', 'MPC', 'HES', 'DVN', 'FANG', 'APA',
            
            # Telecomunicaciones
            'T', 'VZ', 'CMCSA', 'CHTR', 'TMUS', 'S'
        ]
        
        # Principales NASDAQ
        nasdaq_major = [
            # Tecnología
            'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 'META', 'NFLX',
            'NVDA', 'ADBE', 'PYPL', 'INTC', 'CSCO', 'AVGO', 'TXN', 'QCOM',
            'INTU', 'ISRG', 'FISV', 'ADP', 'BIIB', 'ILMN', 'MRNA', 'ZM', 'DOCU',
            'SNOW', 'PLTR', 'RBLX', 'U', 'TWLO', 'OKTA', 'DDOG', 'CRWD',
            
            # Biotecnología
            'GILD', 'REGN', 'VRTX', 'BMRN', 'ALXN', 'CELG', 'BIIB', 'AMGN',
            
            # Consumo/Retail
            'BKNG', 'EBAY', 'SBUX', 'ROST', 'ULTA', 'LULU', 'NTES', 'JD',
            'BABA', 'PDD', 'MELI', 'SE', 'SHOP', 'SQ', 'ROKU', 'SPOT',
            
            # Semiconductores
            'NVDA', 'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'ADI', 'KLAC', 'LRCX',
            'AMAT', 'MU', 'MRVL', 'SWKS', 'MCHP', 'XLNX', 'NXPI', 'TSM',
            
            # Servicios
            'NFLX', 'ROKU', 'SPOT', 'UBER', 'LYFT', 'DASH', 'ABNB', 'ZOOM',
            'TDOC', 'PTON', 'PINS', 'SNAP', 'TWTR', 'FB', 'WORK'
        ]
        
        # Combinar y eliminar duplicados
        all_backup = list(set(nyse_major + nasdaq_major))
        return all_backup
    
    def calculate_moving_averages(self, df):
        """Calcula las medias móviles de 10, 21, 50 y 200 días"""
        try:
            # Calcular medias móviles usando el precio de cierre
            df['MA_10'] = df['Close'].rolling(window=10).mean()
            df['MA_21'] = df['Close'].rolling(window=21).mean() 
            df['MA_50'] = df['Close'].rolling(window=50).mean()
            df['MA_200'] = df['Close'].rolling(window=200).mean()
            
            return df
        except Exception as e:
            print(f"Error calculando medias móviles: {e}")
            return df
    
    def get_current_ma_status(self, df, ticker_info=None):
        """Obtiene el estado actual de las medias móviles y métricas de filtrado"""
        try:
            if df.empty or len(df) < 200:
                return {
                    'current_price': None,
                    'ma_10': None,
                    'ma_21': None,
                    'ma_50': None,
                    'ma_200': None,
                    'above_ma_10': None,
                    'above_ma_21': None,
                    'above_ma_50': None,
                    'above_ma_200': None,
                    'ma_trend': 'Insuficientes datos',
                    'volume_50d_avg': None,
                    'last_day_volume': None,
                    'volume_ratio_vs_50d': None,
                    'volume_above_25pct': None,
                    'price_vs_ma50_pct': None,
                    'ma200_trend_positive': None,
                    'last_day_positive': None,
                    'quarterly_earnings_positive': None,
                    'passes_filters': False,
                    'filter_reasons': ['Datos insuficientes']
                }
            
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) >= 2 else None
            current_price = latest['Close']
            
            # Determinar tendencia basada en orden de MAs
            ma_10 = latest['MA_10']
            ma_21 = latest['MA_21'] 
            ma_50 = latest['MA_50']
            ma_200 = latest['MA_200']
            
            # FILTROS ESPECÍFICOS
            # 1. Volumen promedio últimos 50 días (MODIFICADO)
            volume_50d_avg = df['Volume'].tail(50).mean() if len(df) >= 50 else None
            
            # 6. NUEVO: Volumen último día vs promedio 50 días
            last_day_volume = latest['Volume']
            volume_ratio_vs_50d = None
            volume_above_25pct = None
            if volume_50d_avg and volume_50d_avg > 0:
                volume_ratio_vs_50d = (last_day_volume / volume_50d_avg)
                volume_above_25pct = volume_ratio_vs_50d >= 1.25  # 25% superior
            
            # 2. Porcentaje respecto a MA50 (MODIFICADO: 0% a 5%)
            price_vs_ma50_pct = None
            if pd.notna(ma_50) and ma_50 > 0:
                price_vs_ma50_pct = ((current_price - ma_50) / ma_50) * 100
            
            # 3. Tendencia de MA200 (comparar últimos 10 días con 10 días anteriores)
            ma200_trend_positive = None
            if len(df) >= 220 and pd.notna(df['MA_200'].iloc[-1]) and pd.notna(df['MA_200'].iloc[-11]):
                ma200_recent = df['MA_200'].tail(10).mean()
                ma200_previous = df['MA_200'].iloc[-20:-10].mean()
                ma200_trend_positive = ma200_recent > ma200_previous
            
            # 4. NUEVO: Último día positivo
            last_day_positive = None
            if previous is not None:
                last_day_change_pct = ((current_price - previous['Close']) / previous['Close']) * 100
                last_day_positive = last_day_change_pct > 0
            
            # 5. NUEVO: Beneficios último trimestre
            quarterly_earnings_positive = None
            if ticker_info:
                try:
                    # Intentar obtener datos financieros
                    quarterly_earnings = ticker_info.get('quarterlyEarningsGrowthYOY')
                    if quarterly_earnings is not None:
                        quarterly_earnings_positive = quarterly_earnings > 0
                    else:
                        # Alternativa: usar earnings trimestrales más recientes
                        net_income = ticker_info.get('netIncomeToCommon')
                        if net_income is not None:
                            quarterly_earnings_positive = net_income > 0
                        else:
                            quarterly_earnings_positive = None
                except:
                    quarterly_earnings_positive = None
            
            # Análisis de tendencia general
            if pd.notna(ma_10) and pd.notna(ma_21) and pd.notna(ma_50) and pd.notna(ma_200):
                if ma_10 > ma_21 > ma_50 > ma_200:
                    trend = "Alcista fuerte"
                elif ma_10 > ma_21 > ma_50:
                    trend = "Alcista"
                elif ma_10 < ma_21 < ma_50 < ma_200:
                    trend = "Bajista fuerte" 
                elif ma_10 < ma_21 < ma_50:
                    trend = "Bajista"
                else:
                    trend = "Lateral/Mixta"
            else:
                trend = "Datos insuficientes"
            
            # APLICAR FILTROS (CORREGIDOS)
            passes_filters = True
            filter_reasons = []
            
            # Filtro 1: Volumen promedio mínimo 300,000 (basado en 50 días)
            if volume_50d_avg == None:
                passes_filters = False
                filter_reasons.append("Sin datos vol 50d")
            elif volume_50d_avg < 300000:
                passes_filters = False
                filter_reasons.append(f"Vol 50d bajo: {int(volume_50d_avg)}")
            
            # Filtro 2: Entre 0% y 5% por encima de MA50
            if price_vs_ma50_pct == None:
                passes_filters = False
                filter_reasons.append("Sin datos MA50")
            elif price_vs_ma50_pct < 0:
                passes_filters = False
                filter_reasons.append(f"Debajo MA50: {price_vs_ma50_pct:.1f}%")
            elif price_vs_ma50_pct > 5:
                passes_filters = False
                filter_reasons.append(f"Muy arriba MA50: +{price_vs_ma50_pct:.1f}%")
            
            # Filtro 3: Tendencia MA200 debe ser positiva
            if ma200_trend_positive == None:
                passes_filters = False
                filter_reasons.append("Sin datos MA200 trend")
            elif ma200_trend_positive == False:
                passes_filters = False
                filter_reasons.append("MA200 tendencia negativa")
            
            # Filtro 4: Último día debe ser positivo
            if last_day_positive == None:
                passes_filters = False
                filter_reasons.append("Sin datos último día")
            elif last_day_positive == False:
                passes_filters = False
                filter_reasons.append("Último día negativo")
            
            # Filtro 5: Beneficios último trimestre positivos (CORREGIDO)
            if quarterly_earnings_positive == None:
                passes_filters = False
                filter_reasons.append("Sin datos earnings")
            elif quarterly_earnings_positive == False:
                passes_filters = False
                filter_reasons.append("Beneficios Q negativos")
            
            # Filtro 6: Volumen último día debe ser 25% superior al promedio 50d
            if volume_above_25pct == None:
                passes_filters = False
                filter_reasons.append("Sin datos vol ratio")
            elif volume_above_25pct == False:
                passes_filters = False
                vol_pct = ((volume_ratio_vs_50d - 1) * 100) if volume_ratio_vs_50d else 0
                filter_reasons.append(f"Vol insuficiente: {vol_pct:+.0f}% vs 50d")
            
            # Solo si pasa TODOS los filtros
            if passes_filters:
                filter_reasons = ["✅ PASA TODOS LOS FILTROS"]
            
            return {
                'current_price': round(current_price, 2),
                'ma_10': round(ma_10, 2) if pd.notna(ma_10) else None,
                'ma_21': round(ma_21, 2) if pd.notna(ma_21) else None,
                'ma_50': round(ma_50, 2) if pd.notna(ma_50) else None,
                'ma_200': round(ma_200, 2) if pd.notna(ma_200) else None,
                'above_ma_10': current_price > ma_10 if pd.notna(ma_10) else None,
                'above_ma_21': current_price > ma_21 if pd.notna(ma_21) else None,
                'above_ma_50': current_price > ma_50 if pd.notna(ma_50) else None,
                'above_ma_200': current_price > ma_200 if pd.notna(ma_200) else None,
                'ma_trend': trend,
                'volume_50d_avg': int(volume_50d_avg) if volume_50d_avg else None,
                'last_day_volume': int(last_day_volume) if last_day_volume else None,
                'volume_ratio_vs_50d': round(volume_ratio_vs_50d, 2) if volume_ratio_vs_50d else None,
                'volume_above_25pct': volume_above_25pct,
                'price_vs_ma50_pct': round(price_vs_ma50_pct, 2) if price_vs_ma50_pct else None,
                'ma200_trend_positive': ma200_trend_positive,
                'last_day_positive': last_day_positive,
                'last_day_change_pct': round(last_day_change_pct, 2) if 'last_day_change_pct' in locals() else None,
                'quarterly_earnings_positive': quarterly_earnings_positive,
                'passes_filters': passes_filters,
                'filter_reasons': filter_reasons
            }
            
        except Exception as e:
            print(f"Error analizando estado de MAs: {e}")
            return {'ma_trend': 'Error en cálculo', 'passes_filters': False, 'filter_reasons': ['Error de cálculo']}
    
    def get_stock_data_with_ma(self, symbols, period="1y"):
        """Obtiene datos y calcula medias móviles"""
        stock_data = {}
        failed_symbols = []
        
        print(f"Descargando datos para {len(symbols)} acciones...")
        
        for i, symbol in enumerate(symbols):
            try:
                # Descargar datos históricos
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if not hist.empty and len(hist) >= 10:
                    # Calcular medias móviles
                    hist_with_ma = self.calculate_moving_averages(hist)
                    
                    # Obtener info básica del ticker para earnings
                    try:
                        ticker_info = ticker.info
                        company_info = {
                            'name': ticker_info.get('longName', 'N/A'),
                            'sector': ticker_info.get('sector', 'N/A'),
                            'industry': ticker_info.get('industry', 'N/A'),
                            'market_cap': ticker_info.get('marketCap', 'N/A')
                        }
                    except:
                        ticker_info = {}
                        company_info = {'name': 'N/A', 'sector': 'N/A', 'industry': 'N/A', 'market_cap': 'N/A'}
                    
                    # Obtener estado actual de las MAs
                    ma_status = self.get_current_ma_status(hist_with_ma, ticker_info)
                    
                    stock_data[symbol] = {
                        'data': hist_with_ma,
                        'ma_status': ma_status,
                        'info': company_info
                    }
                    
                    filter_status = "✅ PASA" if ma_status['passes_filters'] else "❌ FILTRADO"
                    print(f"{filter_status} {symbol} - ${ma_status.get('current_price', 0):.2f} - {i+1}/{len(symbols)}")
                else:
                    failed_symbols.append(symbol)
                    print(f"✗ {symbol} - Datos insuficientes")
                
                # Pausa para evitar rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                failed_symbols.append(symbol)
                print(f"✗ {symbol} - Error: {e}")
                
        return stock_data, failed_symbols
    
    def save_ma_data(self, stock_data, filename_prefix="us_stocks_filtered_moving_averages"):
        """Guarda los datos con medias móviles y aplicación de filtros"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Crear resumen con medias móviles y filtros
        all_data = []
        filtered_data = []
        
        for symbol, data in stock_data.items():
            hist_df = data['data']
            ma_status = data['ma_status']
            info = data['info']
            
            if not hist_df.empty:
                row_data = {
                    'Symbol': symbol,
                    'Company_Name': info.get('name', 'N/A'),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Current_Price': ma_status.get('current_price'),
                    'MA_10': ma_status.get('ma_10'),
                    'MA_21': ma_status.get('ma_21'),
                    'MA_50': ma_status.get('ma_50'),
                    'MA_200': ma_status.get('ma_200'),
                    'Volume_50d_Avg': ma_status.get('volume_50d_avg'),
                    'Last_Day_Volume': ma_status.get('last_day_volume'),
                    'Volume_Ratio_vs_50d': ma_status.get('volume_ratio_vs_50d'),
                    'Volume_Above_25pct': ma_status.get('volume_above_25pct'),
                    'Price_vs_MA50_Pct': ma_status.get('price_vs_ma50_pct'),
                    'MA200_Trend_Positive': ma_status.get('ma200_trend_positive'),
                    'Last_Day_Change_Pct': ma_status.get('last_day_change_pct'),
                    'Last_Day_Positive': ma_status.get('last_day_positive'),
                    'Quarterly_Earnings_Positive': ma_status.get('quarterly_earnings_positive'),
                    'Above_MA_10': ma_status.get('above_ma_10'),
                    'Above_MA_21': ma_status.get('above_ma_21'),
                    'Above_MA_50': ma_status.get('above_ma_50'),
                    'Above_MA_200': ma_status.get('above_ma_200'),
                    'MA_Trend': ma_status.get('ma_trend'),
                    'Passes_Filters': ma_status.get('passes_filters'),
                    'Filter_Reasons': "; ".join(ma_status.get('filter_reasons', [])),
                    'Data_Points': len(hist_df),
                    'Start_Date': hist_df.index.min().strftime('%Y-%m-%d'),
                    'End_Date': hist_df.index.max().strftime('%Y-%m-%d')
                }
                
                all_data.append(row_data)
                
                # Solo añadir a datos filtrados si pasa todos los filtros
                if ma_status.get('passes_filters', False):
                    filtered_data.append(row_data)
        
        # Guardar TODOS los datos
        all_df = pd.DataFrame(all_data)
        all_filename = f"{filename_prefix}_ALL_DATA_{timestamp}.csv"
        all_df.to_csv(all_filename, index=False)
        print(f"✓ Todos los datos guardados: {all_filename}")
        
        # Guardar SOLO datos que pasan filtros
        if filtered_data:
            filtered_df = pd.DataFrame(filtered_data)
            filtered_filename = f"{filename_prefix}_FILTERED_ONLY_{timestamp}.csv"
            filtered_df.to_csv(filtered_filename, index=False)
            print(f"✓ Datos filtrados guardados: {filtered_filename}")
            print(f"📊 Acciones que PASAN filtros: {len(filtered_df)}/{len(all_df)}")
        else:
            print("❌ Ninguna acción pasó todos los filtros")
            filtered_df = pd.DataFrame()
        
        return all_df, filtered_df

def main():
    """Función principal para GitHub Actions - ANÁLISIS COMPLETO"""
    print("=== TRADING BOT AUTOMATIZADO - ANÁLISIS COMPLETO ===")
    
    # Crear instancia del extractor
    extractor = USStockMovingAveragesExtractor()
    
    # Para automatización completa, usar TODAS las acciones disponibles
    print("1. Obteniendo TODOS los símbolos NYSE + NASDAQ...")
    all_symbols = extractor.get_nyse_nasdaq_symbols()
    
    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        sys.exit(1)
    
    # CAMBIO PRINCIPAL: Procesar TODAS las acciones, no solo una muestra
    symbols_to_process = all_symbols  # SIN LÍMITE - ANÁLISIS COMPLETO
    print(f"🚀 Procesando {len(symbols_to_process)} acciones COMPLETAS (NYSE + NASDAQ)...")
    print("⚠️  Esto tomará entre 45-90 minutos para completar")
    
    # Dividir en lotes para mejor manejo de memoria y progreso
    batch_size = 100
    total_batches = (len(symbols_to_process) + batch_size - 1) // batch_size
    
    all_stock_data = {}
    all_failed = []
    
    print(f"📦 Procesando en {total_batches} lotes de {batch_size} acciones...")
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(symbols_to_process))
        batch_symbols = symbols_to_process[start_idx:end_idx]
        
        print(f"\n=== LOTE {batch_num + 1}/{total_batches} ===")
        print(f"Procesando acciones {start_idx + 1}-{end_idx} de {len(symbols_to_process)}")
        
        # Procesar lote
        batch_data, batch_failed = extractor.get_stock_data_with_ma(batch_symbols)
        
        # Agregar a resultados totales
        all_stock_data.update(batch_data)
        all_failed.extend(batch_failed)
        
        # Estadísticas del lote
        batch_passed = sum(1 for data in batch_data.values() if data['ma_status']['passes_filters'])
        print(f"✅ Lote completado: {len(batch_data)} procesadas, {batch_passed} pasan filtros, {len(batch_failed)} fallidas")
        
        # Pausa entre lotes para evitar rate limiting
        if batch_num < total_batches - 1:  # No pausar después del último lote
            print("⏳ Pausa de 30 segundos entre lotes...")
            time.sleep(30)
    
    print(f"\n=== PROCESAMIENTO COMPLETO FINALIZADO ===")
    print(f"📊 Total acciones procesadas exitosamente: {len(all_stock_data)}")
    print(f"❌ Total acciones con errores: {len(all_failed)}")
    
    if all_stock_data:
        print(f"\n3. Guardando resultados completos...")
        all_summary, filtered_summary = extractor.save_ma_data(all_stock_data)
        
        print(f"\n=== RESUMEN FINAL COMPLETO ===")
        print(f"🌐 Mercados analizados: NYSE + NASDAQ COMPLETOS")
        print(f"✓ Acciones procesadas exitosamente: {len(all_stock_data):,}")
        print(f"✗ Acciones con errores: {len(all_failed):,}")
        print(f"🔍 Acciones que PASAN todos los filtros: {len(filtered_summary) if not filtered_summary.empty else 0}")
        
        if not filtered_summary.empty:
            filter_rate = (len(filtered_summary) / len(all_stock_data)) * 100
            print(f"📈 Tasa de filtrado exitoso: {filter_rate:.2f}%")
        
        # Mostrar top 10 para verificación
        if not filtered_summary.empty:
            print(f"\n🔝 TOP 10 ACCIONES FILTRADAS (de análisis completo):")
            # Calcular scores como en el análisis original
            trend_scores = {
                'Alcista fuerte': 100,
                'Alcista': 80,
                'Lateral/Mixta': 60,
                'Bajista': 20,
                'Bajista fuerte': 0
            }
            
            filtered_summary['Trend_Score'] = filtered_summary['MA_Trend'].map(trend_scores).fillna(50)
            
            if filtered_summary['Volume_Ratio_vs_50d'].max() > 0:
                filtered_summary['Volume_Score'] = (filtered_summary['Volume_Ratio_vs_50d'] / filtered_summary['Volume_Ratio_vs_50d'].max() * 50).fillna(0)
            else:
                filtered_summary['Volume_Score'] = 0
                
            if filtered_summary['Last_Day_Change_Pct'].max() > 0:
                filtered_summary['Day_Change_Score'] = (filtered_summary['Last_Day_Change_Pct'] / filtered_summary['Last_Day_Change_Pct'].max() * 30).fillna(0)
            else:
                filtered_summary['Day_Change_Score'] = 0
                
            filtered_summary['MA50_Score'] = filtered_summary['Price_vs_MA50_Pct'].apply(
                lambda x: 20 - abs(x - 2.5) * 4 if pd.notna(x) else 0
            )
            
            filtered_summary['Total_Score'] = (
                filtered_summary['Trend_Score'] + 
                filtered_summary['Volume_Score'] + 
                filtered_summary['Day_Change_Score'] + 
                filtered_summary['MA50_Score']
            )
            
            # Mostrar top 10
            top_10 = filtered_summary.sort_values('Total_Score', ascending=False).head(10)
            for i, (_, row) in enumerate(top_10.iterrows()):
                vol_boost = ((row['Volume_Ratio_vs_50d'] - 1) * 100) if pd.notna(row['Volume_Ratio_vs_50d']) else 0
                print(f"{i+1:2d}. {row['Symbol']:6s} - ${row['Current_Price']:7.2f} - Score: {row['Total_Score']:5.1f} - "
                      f"MA50: {row['Price_vs_MA50_Pct']:+5.1f}% - Vol: {vol_boost:+4.0f}% - {row['Company_Name'][:25]}")
        
        print(f"\n🎯 Archivos CSV generados con datos de {len(all_stock_data):,} acciones")
        print(f"📱 Dashboard web listo con análisis completo del mercado")
        
    else:
        print("❌ No se pudieron obtener datos de ninguna acción")
        sys.exit(1)

if __name__ == "__main__":
    main()