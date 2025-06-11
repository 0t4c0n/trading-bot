import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import json
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
        """Obtiene datos de NYSE y calcula medias móviles"""
        stock_data = {}
        failed_symbols = []
        
        print(f"Descargando datos y calculando medias móviles para {len(symbols)} acciones del NYSE...")
        
        for i, symbol in enumerate(symbols):
            try:
                # Descargar datos históricos
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if not hist.empty and len(hist) >= 10:  # Mínimo 10 días para MA_10
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
                    
                    # Obtener estado actual de las MAs (con info de earnings)
                    ma_status = self.get_current_ma_status(hist_with_ma, ticker_info)
                    
                    stock_data[symbol] = {
                        'data': hist_with_ma,
                        'ma_status': ma_status,
                        'info': company_info
                    }
                    
                    # Debug: mostrar valores de filtros para verificación
                    debug_info = []
                    if ma_status.get('volume_50d_avg'):
                        debug_info.append(f"Vol50d:{int(ma_status['volume_50d_avg']/1000)}K")
                    if ma_status.get('price_vs_ma50_pct') is not None:
                        debug_info.append(f"MA50:{ma_status['price_vs_ma50_pct']:+.1f}%")
                    if ma_status.get('volume_ratio_vs_50d'):
                        vol_pct = (ma_status['volume_ratio_vs_50d'] - 1) * 100
                        debug_info.append(f"VolR:{vol_pct:+.0f}%")
                    
                    debug_str = " | ".join(debug_info[:3]) if debug_info else ""
                    
                    filter_status = "✅ PASA" if ma_status['passes_filters'] else "❌ FILTRADO"
                    last_day = f"+{ma_status['last_day_change_pct']:.1f}%" if ma_status.get('last_day_change_pct', 0) > 0 else f"{ma_status.get('last_day_change_pct', 0):.1f}%"
                    vol_ratio = f"{((ma_status.get('volume_ratio_vs_50d', 1) - 1) * 100):+.0f}%" if ma_status.get('volume_ratio_vs_50d') else "N/A"
                    reasons = ", ".join(ma_status['filter_reasons'][:2])  # Mostrar máximo 2 razones
                    print(f"{filter_status} {symbol} - {last_day} - Vol:{vol_ratio} - {debug_str} - {reasons[:50]} - {i+1}/{len(symbols)}")
                else:
                    failed_symbols.append(symbol)
                    print(f"✗ {symbol} - Datos insuficientes")
                
                # Pausa para evitar rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                failed_symbols.append(symbol)
                print(f"✗ {symbol} - Error: {e}")
                
        print(f"\n=== DESCARGA COMPLETADA ===")
        print(f"Exitosas: {len(stock_data)}")
        print(f"Fallidas: {len(failed_symbols)}")
        
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
        
        # Guardar TODOS los datos (con y sin filtrar)
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
        
        # Guardar datos históricos de una muestra de acciones filtradas
        if filtered_data:
            sample_symbols = [row['Symbol'] for row in filtered_data[:3]]  # Primeras 3 que pasan filtros
            for symbol in sample_symbols:
                if symbol in stock_data:
                    hist_df = stock_data[symbol]['data']
                    hist_filename = f"{filename_prefix}_{symbol}_historical_{timestamp}.csv"
                    hist_df.to_csv(hist_filename)
                    print(f"✓ Datos históricos guardados: {hist_filename}")
        
        return all_df, filtered_df
    
    def analyze_ma_signals(self, all_df, filtered_df):
        """Analiza señales basadas en medias móviles con filtros aplicados"""
        print(f"\n=== ANÁLISIS CON FILTROS APLICADOS ===")
        
        if all_df.empty:
            print("No hay datos para analizar")
            return
        
        total_stocks = len(all_df)
        passed_filters = len(filtered_df) if not filtered_df.empty else 0
        
        print(f"📊 Total acciones analizadas: {total_stocks}")
        print(f"✅ Acciones que PASAN filtros: {passed_filters}")
        print(f"❌ Acciones ELIMINADAS: {total_stocks - passed_filters}")
        print(f"📈 Tasa de filtrado: {((total_stocks - passed_filters) / total_stocks * 100):.1f}%")
        
        # Análisis de razones de filtrado
        print(f"\n=== RAZONES DE ELIMINACIÓN (TOP 10) ===")
        filter_reasons_count = {}
        
        for _, row in all_df.iterrows():
            if not row['Passes_Filters']:
                reasons = str(row['Filter_Reasons']).split(';')
                for reason in reasons:
                    reason = reason.strip()
                    if reason and reason != "✅ PASA TODOS LOS FILTROS" and reason != "nan":
                        filter_reasons_count[reason] = filter_reasons_count.get(reason, 0) + 1
        
        # Mostrar top 10 razones
        for reason, count in sorted(filter_reasons_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_stocks) * 100
            print(f"  {reason}: {count} acciones ({percentage:.1f}%)")
        
        if filtered_df.empty:
            print(f"\n❌ NINGUNA ACCIÓN PASÓ TODOS LOS FILTROS")
            print("📋 RECOMENDACIONES:")
            print("   - Revisar si los filtros son demasiado estrictos")
            print("   - Considerar relajar el filtro de earnings (muchas empresas no reportan)")
            print("   - Verificar el filtro de volumen +25% (puede ser muy exigente)")
            print("   - Comprobar datos de fin de semana/días no bursátiles")
            return
        
        # Análisis de acciones que pasan filtros
        print(f"\n=== ACCIONES QUE PASAN TODOS LOS FILTROS ===")
        
        # Ordenar por múltiples criterios para crear el ranking
        print(f"📊 CRITERIOS DE RANKING PARA TOP 10:")
        print(f"   1. Tendencia general (MA_Trend) - Alcista fuerte > Alcista > Lateral")
        print(f"   2. Ratio de volumen vs 50d (mayor actividad = mejor)")
        print(f"   3. Cambio último día (mayor = mejor)")
        print(f"   4. Proximidad óptima a MA50 (entre 2-4% ideal)")
        
        # Crear score compuesto para ranking
        filtered_df_scored = filtered_df.copy()
        
        # Score por tendencia (0-100)
        trend_scores = {
            'Alcista fuerte': 100,
            'Alcista': 80,
            'Lateral/Mixta': 60,
            'Bajista': 20,
            'Bajista fuerte': 0
        }
        filtered_df_scored['Trend_Score'] = filtered_df_scored['MA_Trend'].map(trend_scores).fillna(50)
        
        # Score por ratio de volumen (0-50) - normalizado
        max_vol_ratio = filtered_df_scored['Volume_Ratio_vs_50d'].max()
        filtered_df_scored['Volume_Score'] = (filtered_df_scored['Volume_Ratio_vs_50d'] / max_vol_ratio * 50).fillna(0)
        
        # Score por cambio último día (0-30)
        max_day_change = filtered_df_scored['Last_Day_Change_Pct'].max()
        filtered_df_scored['Day_Change_Score'] = (filtered_df_scored['Last_Day_Change_Pct'] / max_day_change * 30).fillna(0)
        
        # Score por proximidad óptima a MA50 (0-20) - penalizar extremos
        filtered_df_scored['MA50_Score'] = filtered_df_scored['Price_vs_MA50_Pct'].apply(
            lambda x: 20 - abs(x - 2.5) * 4 if pd.notna(x) else 0  # Óptimo en 2.5%
        )
        
        # Score total
        filtered_df_scored['Total_Score'] = (
            filtered_df_scored['Trend_Score'] + 
            filtered_df_scored['Volume_Score'] + 
            filtered_df_scored['Day_Change_Score'] + 
            filtered_df_scored['MA50_Score']
        )
        
        # Ordenar por score total
        filtered_sorted = filtered_df_scored.sort_values('Total_Score', ascending=False)
        
        print(f"\n🔝 TOP 10 ACCIONES FILTRADAS (por Score Total):")
        for i, (_, row) in enumerate(filtered_sorted.head(10).iterrows()):
            vol_50d_m = row['Volume_50d_Avg'] / 1000000 if row['Volume_50d_Avg'] else 0
            vol_last_m = row['Last_Day_Volume'] / 1000000 if row['Last_Day_Volume'] else 0
            vol_ratio_pct = ((row['Volume_Ratio_vs_50d'] - 1) * 100) if row['Volume_Ratio_vs_50d'] else 0
            last_day = row['Last_Day_Change_Pct'] if row['Last_Day_Change_Pct'] else 0
            earnings_status = "✓" if row['Quarterly_Earnings_Positive'] else "?" if pd.isna(row['Quarterly_Earnings_Positive']) else "✗"
            total_score = row['Total_Score'] if 'Total_Score' in row else 0
            
            print(f"{i+1:2d}. {row['Symbol']:6s} (Score: {total_score:5.1f}) ${row['Current_Price']:7.2f} | "
                  f"MA50: {row['Price_vs_MA50_Pct']:+5.1f}% | "
                  f"Día: {last_day:+5.1f}% | "
                  f"Vol: {vol_last_m:.1f}M ({vol_ratio_pct:+.0f}%) | "
                  f"Earn: {earnings_status} | "
                  f"{row['Company_Name'][:20]}")
        
        # Mostrar desglose de scores para las top 3
        if len(filtered_sorted) >= 3:
            print(f"\n📊 DESGLOSE DE SCORES (Top 3):")
            for i, (_, row) in enumerate(filtered_sorted.head(3).iterrows()):
                trend_score = row.get('Trend_Score', 0)
                volume_score = row.get('Volume_Score', 0)
                day_score = row.get('Day_Change_Score', 0)
                ma50_score = row.get('MA50_Score', 0)
                total = row.get('Total_Score', 0)
                
                print(f"{i+1}. {row['Symbol']:6s}: Tendencia({trend_score:4.1f}) + "
                      f"Volumen({volume_score:4.1f}) + Día({day_score:4.1f}) + "
                      f"MA50({ma50_score:4.1f}) = {total:5.1f}")
        
        # Distribución por tendencia (solo filtradas)
        print(f"\n=== DISTRIBUCIÓN POR TENDENCIA (FILTRADAS) ===")
        if 'MA_Trend' in filtered_df.columns:
            trend_counts = filtered_df['MA_Trend'].value_counts()
            for trend, count in trend_counts.items():
                percentage = (count / len(filtered_df)) * 100
                print(f"{trend:15s}: {count:3d} acciones ({percentage:4.1f}%)")
        
        # Estadísticas de volumen y precio vs MA50
        print(f"\n=== ESTADÍSTICAS DE ACCIONES FILTRADAS ===")
        if len(filtered_df) > 0:
            avg_volume_50d = filtered_df['Volume_50d_Avg'].mean() / 1000000
            avg_volume_last = filtered_df['Last_Day_Volume'].mean() / 1000000
            avg_volume_ratio = filtered_df['Volume_Ratio_vs_50d'].mean()
            avg_price_vs_ma50 = filtered_df['Price_vs_MA50_Pct'].mean()
            avg_last_day = filtered_df['Last_Day_Change_Pct'].mean()
            earnings_positive_count = filtered_df['Quarterly_Earnings_Positive'].sum()
            earnings_data_available = filtered_df['Quarterly_Earnings_Positive'].notna().sum()
            
            print(f"Volumen promedio 50d: {avg_volume_50d:.1f}M")
            print(f"Volumen último día promedio: {avg_volume_last:.1f}M")
            print(f"Ratio volumen promedio: {avg_volume_ratio:.2f}x (+{((avg_volume_ratio-1)*100):.0f}%)")
            print(f"Precio vs MA50 promedio: {avg_price_vs_ma50:+.1f}%")
            print(f"Rango precio vs MA50: {filtered_df['Price_vs_MA50_Pct'].min():+.1f}% a {filtered_df['Price_vs_MA50_Pct'].max():+.1f}%")
            print(f"Cambio último día promedio: {avg_last_day:+.1f}%")
            print(f"Acciones con earnings positivos: {earnings_positive_count}/{earnings_data_available} (datos disponibles)")

def main():
    print("=== EXTRACTOR DE MEDIAS MÓVILES - NYSE + NASDAQ ===\n")
    
    # Crear instancia del extractor
    extractor = USStockMovingAveragesExtractor()
    
    # Obtener símbolos de NYSE y NASDAQ
    print("1. Obteniendo símbolos de NYSE y NASDAQ...")
    all_symbols = extractor.get_nyse_nasdaq_symbols()
    
    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        return
    
    # Opción para muestra o completo
    print(f"\nSe encontraron {len(all_symbols)} símbolos únicos (NYSE + NASDAQ)")
    choice = input("¿Desea procesar una muestra (100 acciones) o todos? (muestra/todos): ").lower()
    
    if choice == 'muestra':
        symbols_to_process = all_symbols[:100]
        print(f"Procesando muestra de {len(symbols_to_process)} acciones...")
    else:
        symbols_to_process = all_symbols
        print(f"Procesando {len(symbols_to_process)} acciones completas...")
        print("⚠️  Esto puede tomar varias horas para completar")
    
    # Procesar datos
    print(f"\n2. Descargando datos y calculando medias móviles...")
    stock_data, failed = extractor.get_stock_data_with_ma(symbols_to_process)
    
    if stock_data:
        print(f"\n3. Guardando resultados...")
        all_summary, filtered_summary = extractor.save_ma_data(stock_data)
        
        print(f"\n4. Analizando señales...")
        extractor.analyze_ma_signals(all_summary, filtered_summary)
        
        print(f"\n=== RESUMEN FINAL ===")
        print(f"📊 Mercados analizados: NYSE + NASDAQ")
        print(f"✓ Acciones procesadas exitosamente: {len(stock_data)}")
        print(f"✗ Acciones con errores: {len(failed)}")
        print(f"🔍 Acciones que PASAN todos los filtros: {len(filtered_summary) if not filtered_summary.empty else 0}")
        print(f"📊 Archivos CSV generados con datos completos y filtrados")
        print(f"📈 Medias móviles calculadas: MA_10, MA_21, MA_50, MA_200")
        print(f"🎯 Filtros aplicados:")
        print(f"   - Volumen 50d ≥ 300,000")
        print(f"   - Precio: 0% ≤ vs MA50 ≤ +5%") 
        print(f"   - Tendencia MA200 positiva")
        print(f"   - Último día de mercado positivo")
        print(f"   - Beneficios último trimestre positivos")
        print(f"   - Volumen último día ≥ +25% vs promedio 50d")
        
    else:
        print("❌ No se pudieron obtener datos de ninguna acción")

if __name__ == "__main__":
    main()