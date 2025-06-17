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
            nyse_symbols = self.get_exchange_symbols('NYSE')
            nasdaq_symbols = self.get_exchange_symbols('NASDAQ')
            
            # Combinar y eliminar duplicados
            all_symbols = list(set(nyse_symbols + nasdaq_symbols))
            print(f"✓ NYSE: {len(nyse_symbols)} | NASDAQ: {len(nasdaq_symbols)} | Total: {len(all_symbols)} símbolos")
            
            return all_symbols
            
        except Exception as e:
            print(f"Error obteniendo símbolos: {e}")
            backup_symbols = self.get_backup_symbols()
            print(f"Usando lista de respaldo: {len(backup_symbols)} símbolos")
            return backup_symbols
    
    def get_exchange_symbols(self, exchange):
        """Obtiene símbolos de un exchange específico (NYSE o NASDAQ)"""
        try:
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
        nyse_major = [
            'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'AXP', 'USB', 'PNC', 'TFC',
            'COF', 'SCHW', 'BLK', 'SPGI', 'ICE', 'CME', 'MCO', 'AON', 'MMC',
            'CAT', 'BA', 'GE', 'HON', 'LMT', 'RTX', 'MMM', 'UPS', 'DE', 'EMR',
            'ITW', 'ETN', 'PH', 'ROK', 'DOV', 'XYL', 'IEX', 'FTV', 'AME',
            'WMT', 'HD', 'PG', 'KO', 'PEP', 'COST', 'TGT', 'LOW', 'NKE', 'SBUX',
            'MCD', 'DIS', 'CL', 'KMB', 'CHD', 'SJM', 'GIS', 'K', 'CPB',
            'JNJ', 'PFE', 'ABT', 'MRK', 'LLY', 'BMY', 'AMGN', 'GILD', 'MDT',
            'DHR', 'TMO', 'A', 'SYK', 'BSX', 'EW', 'HOLX', 'ZBH', 'BAX', 'BDX',
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PXD', 'KMI', 'OKE', 'WMB', 'EPD',
            'ET', 'MPLX', 'PSX', 'VLO', 'MPC', 'HES', 'DVN', 'FANG', 'APA',
            'T', 'VZ', 'CMCSA', 'CHTR', 'TMUS', 'S'
        ]
        
        nasdaq_major = [
            'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 'META', 'NFLX',
            'NVDA', 'ADBE', 'PYPL', 'INTC', 'CSCO', 'AVGO', 'TXN', 'QCOM',
            'INTU', 'ISRG', 'FISV', 'ADP', 'BIIB', 'ILMN', 'MRNA', 'ZM', 'DOCU',
            'SNOW', 'PLTR', 'RBLX', 'U', 'TWLO', 'OKTA', 'DDOG', 'CRWD',
            'GILD', 'REGN', 'VRTX', 'BMRN', 'ALXN', 'CELG', 'BIIB', 'AMGN',
            'BKNG', 'EBAY', 'SBUX', 'ROST', 'ULTA', 'LULU', 'NTES', 'JD',
            'BABA', 'PDD', 'MELI', 'SE', 'SHOP', 'SQ', 'ROKU', 'SPOT',
            'NVDA', 'AMD', 'INTC', 'QCOM', 'AVGO', 'TXN', 'ADI', 'KLAC', 'LRCX',
            'AMAT', 'MU', 'MRVL', 'SWKS', 'MCHP', 'XLNX', 'NXPI', 'TSM',
            'NFLX', 'ROKU', 'SPOT', 'UBER', 'LYFT', 'DASH', 'ABNB', 'ZOOM',
            'TDOC', 'PTON', 'PINS', 'SNAP', 'TWTR', 'FB', 'WORK'
        ]
        
        all_backup = list(set(nyse_major + nasdaq_major))
        return all_backup
    
    def calculate_spy_return_20d(self):
        """Calcula el rendimiento de SPY en 20 días - SOLO UNA VEZ CON RETRY"""
        print("Descargando SPY para Relative Strength...")
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                spy_ticker = yf.Ticker("SPY")
                spy_data = spy_ticker.history(period="2mo")
                
                if spy_data.empty or len(spy_data) < 21:
                    print("⚠️ SPY: Datos insuficientes - Relative Strength deshabilitado")
                    return None
                else:
                    spy_current = spy_data['Close'].iloc[-1]
                    spy_20d_ago = spy_data['Close'].iloc[-21]
                    spy_return_20d = ((spy_current / spy_20d_ago) - 1) * 100
                    
                    print(f"✅ SPY rendimiento 20d: {spy_return_20d:+.2f}%")
                    return spy_return_20d
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                if "rate" in error_msg or "429" in error_msg or "too many requests" in error_msg:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 5 * (2 ** retry_count)
                        print(f"⏳ SPY Rate limit - Retry {retry_count}/{max_retries} en {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ SPY: Rate limit persistente")
                        return None
                else:
                    print(f"⚠️ Error SPY: {e}")
                    return None
    
    def calculate_moving_averages(self, df):
        """Calcula las medias móviles de 10, 21, 50 y 200 días"""
        try:
            df['MA_10'] = df['Close'].rolling(window=10).mean()
            df['MA_21'] = df['Close'].rolling(window=21).mean() 
            df['MA_50'] = df['Close'].rolling(window=50).mean()
            df['MA_200'] = df['Close'].rolling(window=200).mean()
            
            return df
        except Exception as e:
            print(f"Error calculando medias móviles: {e}")
            return df
    
    def get_current_ma_status(self, df, ticker_info=None, spy_return_20d=None):
        """Obtiene el estado actual de las medias móviles y métricas de filtrado"""
        try:
            if df.empty or len(df) < 200:
                return {
                    'current_price': None,
                    'ma_10': None, 'ma_21': None, 'ma_50': None, 'ma_200': None,
                    'above_ma_10': None, 'above_ma_21': None, 'above_ma_50': None, 'above_ma_200': None,
                    'ma_trend': 'Insuficientes datos',
                    'volume_50d_avg': None, 'last_day_volume': None, 'volume_ratio_vs_50d': None,
                    'volume_above_25pct': None, 'price_vs_ma50_pct': None, 'ma200_trend_positive': None,
                    'last_day_positive': None, 'quarterly_earnings_positive': None,
                    'revenue_growth_positive': None, 'earnings_growth_positive': None, 'growth_criteria_met': None,
                    'relative_strength_vs_spy': None, 'relative_strength_value': None,
                    'passes_filters': False, 'filter_reasons': ['Datos insuficientes']
                }
            
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) >= 2 else None
            current_price = latest['Close']
            
            # Medias móviles
            ma_10 = latest['MA_10']
            ma_21 = latest['MA_21'] 
            ma_50 = latest['MA_50']
            ma_200 = latest['MA_200']
            
            # Filtro 1: Volumen promedio últimos 50 días
            volume_50d_avg = df['Volume'].tail(50).mean() if len(df) >= 50 else None
            
            # Filtro 2: Volumen último día vs promedio 50 días
            last_day_volume = latest['Volume']
            volume_ratio_vs_50d = None
            volume_above_25pct = None
            if volume_50d_avg and volume_50d_avg > 0:
                volume_ratio_vs_50d = (last_day_volume / volume_50d_avg)
                volume_above_25pct = volume_ratio_vs_50d >= 1.25
            
            # Filtro 3: Porcentaje respecto a MA50
            price_vs_ma50_pct = None
            if pd.notna(ma_50) and ma_50 > 0:
                price_vs_ma50_pct = ((current_price - ma_50) / ma_50) * 100
            
            # Filtro 4: Tendencia de MA200
            ma200_trend_positive = None
            if len(df) >= 220 and pd.notna(df['MA_200'].iloc[-1]) and pd.notna(df['MA_200'].iloc[-11]):
                ma200_recent = df['MA_200'].tail(10).mean()
                ma200_previous = df['MA_200'].iloc[-20:-10].mean()
                ma200_trend_positive = ma200_recent > ma200_previous
            
            # Filtro 5: Último día positivo
            last_day_positive = None
            last_day_change_pct = None
            if previous is not None:
                last_day_change_pct = ((current_price - previous['Close']) / previous['Close']) * 100
                last_day_positive = last_day_change_pct > 0
            
            # Filtro 6: Beneficios último trimestre
            quarterly_earnings_positive = None
            if ticker_info:
                try:
                    quarterly_earnings = ticker_info.get('quarterlyEarningsGrowthYOY')
                    if quarterly_earnings is not None:
                        quarterly_earnings_positive = quarterly_earnings > 0
                    else:
                        net_income = ticker_info.get('netIncomeToCommon')
                        if net_income is not None:
                            quarterly_earnings_positive = net_income > 0
                        else:
                            quarterly_earnings_positive = None
                except:
                    quarterly_earnings_positive = None
            
            # FILTRO 7: CRECIMIENTO FLEXIBLE (Ingresos >15% OR Beneficios >25%)
            revenue_growth_positive = None
            earnings_growth_positive = None
            growth_criteria_met = None
            
            if ticker_info:
                try:
                    # Crecimiento de ingresos > 15%
                    revenue_growth = ticker_info.get('revenueGrowth')
                    if revenue_growth is not None:
                        revenue_growth_positive = revenue_growth > 0.15
                    
                    # Crecimiento de beneficios > 25%
                    earnings_growth = ticker_info.get('earningsGrowthYOY')
                    if earnings_growth is not None:
                        earnings_growth_positive = earnings_growth > 0.25
                    
                    # CRITERIO OR: Cualquiera de los dos debe cumplirse
                    if revenue_growth_positive is not None or earnings_growth_positive is not None:
                        growth_criteria_met = (revenue_growth_positive == True) or (earnings_growth_positive == True)
                    else:
                        growth_criteria_met = None
                        
                except:
                    revenue_growth_positive = None
                    earnings_growth_positive = None
                    growth_criteria_met = None
            
            # FILTRO 8: RELATIVE STRENGTH VS SPY (+3% outperformance en 20 días)
            relative_strength_vs_spy = None
            relative_strength_value = None
            
            if spy_return_20d is not None and len(df) >= 21:
                try:
                    # Calcular rendimiento de la acción últimos 20 días
                    stock_return = ((current_price / df['Close'].iloc[-21]) - 1) * 100
                    
                    # Comparar con rendimiento de SPY pre-calculado
                    relative_strength_value = stock_return - spy_return_20d
                    relative_strength_vs_spy = relative_strength_value > 3.0  # 3% mejor que SPY
                    
                except Exception as e:
                    relative_strength_vs_spy = None
                    relative_strength_value = None
            
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
            
            # APLICAR LOS 8 FILTROS
            passes_filters = True
            filter_reasons = []
            
            # Filtro 1: Volumen promedio mínimo 300,000
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
            
            # Filtro 5: Beneficios último trimestre positivos
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
            
            # Filtro 7: CRECIMIENTO FLEXIBLE (Ingresos >15% OR Beneficios >25%)
            if growth_criteria_met == None:
                passes_filters = False
                filter_reasons.append("Sin datos growth")
            elif growth_criteria_met == False:
                rev_status = f"Ingresos:{revenue_growth*100:.1f}%" if revenue_growth_positive is not None else "Ingresos:N/A"
                earn_status = f"Beneficios:{earnings_growth*100:.1f}%" if earnings_growth_positive is not None else "Beneficios:N/A"
                passes_filters = False
                filter_reasons.append(f"Growth insuficiente ({rev_status}, {earn_status})")
            
            # Filtro 8: RELATIVE STRENGTH VS SPY (+3% outperformance)
            if relative_strength_vs_spy == None:
                passes_filters = False
                filter_reasons.append("Sin datos SPY comparison")
            elif relative_strength_vs_spy == False:
                passes_filters = False
                if relative_strength_value is not None:
                    filter_reasons.append(f"Underperform SPY: {relative_strength_value:+.1f}%")
                else:
                    filter_reasons.append("Underperform SPY")
            
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
                'last_day_change_pct': round(last_day_change_pct, 2) if last_day_change_pct else None,
                'quarterly_earnings_positive': quarterly_earnings_positive,
                'revenue_growth_positive': revenue_growth_positive,
                'earnings_growth_positive': earnings_growth_positive,
                'growth_criteria_met': growth_criteria_met,
                'relative_strength_vs_spy': relative_strength_vs_spy,
                'relative_strength_value': round(relative_strength_value, 2) if relative_strength_value else None,
                'passes_filters': passes_filters,
                'filter_reasons': filter_reasons
            }
            
        except Exception as e:
            print(f"Error analizando estado de MAs: {e}")
            return {'ma_trend': 'Error en cálculo', 'passes_filters': False, 'filter_reasons': ['Error de cálculo']}
    
    def get_stock_data_with_ma(self, symbols, spy_return_20d=None, period="1y"):
        """Obtiene datos y calcula medias móviles usando SPY pre-calculado - CON RATE LIMITING"""
        stock_data = {}
        failed_symbols = []
        
        for i, symbol in enumerate(symbols):
            # Retry logic para manejar rate limiting
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=period)
                    
                    if not hist.empty and len(hist) >= 10:
                        hist_with_ma = self.calculate_moving_averages(hist)
                        
                        try:
                            ticker_info = ticker.info
                            company_info = {
                                'name': ticker_info.get('longName', 'N/A'),
                                'sector': ticker_info.get('sector', 'N/A'),
                                'industry': ticker_info.get('industry', 'N/A'),
                                'market_cap': ticker_info.get('marketCap', 'N/A')
                            }
                        except Exception as info_error:
                            if "rate" in str(info_error).lower() or "429" in str(info_error):
                                time.sleep(2 ** retry_count)
                                retry_count += 1
                                continue
                            else:
                                ticker_info = {}
                                company_info = {'name': 'N/A', 'sector': 'N/A', 'industry': 'N/A', 'market_cap': 'N/A'}
                        
                        ma_status = self.get_current_ma_status(hist_with_ma, ticker_info, spy_return_20d)
                        
                        stock_data[symbol] = {
                            'data': hist_with_ma,
                            'ma_status': ma_status,
                            'info': company_info
                        }
                        
                        filter_status = "✅ PASA" if ma_status['passes_filters'] else "❌ FILTRADO"
                        price = ma_status.get('current_price', 0)
                        rel_strength = ma_status.get('relative_strength_value', 0)
                        rel_str = f"SPY{rel_strength:+.1f}%" if rel_strength else "SPY:N/A"
                        
                        # Mostrar razón de filtrado si no pasa
                        if ma_status['passes_filters']:
                            reason_str = ""
                        else:
                            reasons = ma_status.get('filter_reasons', ['Sin razón'])
                            first_reason = reasons[0] if reasons else 'Sin razón'
                            reason_str = f" - [{first_reason}]"
                        
                        retry_info = f" (retry {retry_count})" if retry_count > 0 else ""
                        print(f"{filter_status} {symbol} - ${price:.2f} - {rel_str}{reason_str}{retry_info} - {i+1}/{len(symbols)}")
                        success = True
                        
                    else:
                        failed_symbols.append(symbol)
                        print(f"✗ {symbol} - Datos insuficientes")
                        success = True
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    if "rate" in error_msg or "429" in error_msg or "too many requests" in error_msg:
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count
                            print(f"⏳ {symbol} - Rate limit - Retry {retry_count}/{max_retries} en {wait_time}s")
                            time.sleep(wait_time)
                        else:
                            failed_symbols.append(symbol)
                            print(f"❌ {symbol} - Rate limit persistente")
                            break
                    else:
                        failed_symbols.append(symbol)
                        print(f"✗ {symbol} - Error: {e}")
                        break
                
                if success or retry_count >= max_retries:
                    time.sleep(0.2)  # 0.2s entre acciones
                    
        return stock_data, failed_symbols
    
    def save_ma_data(self, stock_data, filename_prefix="us_stocks_filtered_moving_averages"):
        """Guarda los datos con medias móviles y aplicación de filtros"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
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
                    'Revenue_Growth_Positive': ma_status.get('revenue_growth_positive'),
                    'Earnings_Growth_Positive': ma_status.get('earnings_growth_positive'),
                    'Growth_Criteria_Met': ma_status.get('growth_criteria_met'),
                    'Relative_Strength_vs_SPY': ma_status.get('relative_strength_vs_spy'),
                    'Relative_Strength_Value': ma_status.get('relative_strength_value'),
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
                
                if ma_status.get('passes_filters', False):
                    filtered_data.append(row_data)
        
        all_df = pd.DataFrame(all_data)
        all_filename = f"{filename_prefix}_ALL_DATA_{timestamp}.csv"
        all_df.to_csv(all_filename, index=False)
        print(f"✓ Guardado: {all_filename}")
        
        if filtered_data:
            filtered_df = pd.DataFrame(filtered_data)
            filtered_filename = f"{filename_prefix}_FILTERED_ONLY_{timestamp}.csv"
            filtered_df.to_csv(filtered_filename, index=False)
            print(f"✓ Guardado: {filtered_filename}")
        else:
            print("❌ Ninguna acción pasó todos los filtros")
            filtered_df = pd.DataFrame()
        
        return all_df, filtered_df

def main():
    """Función principal para GitHub Actions - ANÁLISIS COMPLETO CON 8 FILTROS + ANÁLISIS DE ELIMINACIÓN"""
    print("=== TRADING BOT AUTOMATIZADO - 8 FILTROS ===")
    
    extractor = USStockMovingAveragesExtractor()
    
    print("Obteniendo símbolos NYSE + NASDAQ...")
    all_symbols = extractor.get_nyse_nasdaq_symbols()
    
    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        exit(1)
    
    # Calcular SPY return solo UNA VEZ al inicio
    spy_return_20d = extractor.calculate_spy_return_20d()
    
    # Procesar acciones
    symbols_to_process = all_symbols
    print(f"\nProcesando {len(symbols_to_process)} acciones...")
    
    # Dividir en lotes
    batch_size = 50  # batch_size = 50
    total_batches = (len(symbols_to_process) + batch_size - 1) // batch_size
    
    all_stock_data = {}
    all_failed = []
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(symbols_to_process))
        batch_symbols = symbols_to_process[start_idx:end_idx]
        
        print(f"\n=== LOTE {batch_num + 1}/{total_batches} ({start_idx + 1}-{end_idx}) ===")
        
        batch_data, batch_failed = extractor.get_stock_data_with_ma(batch_symbols, spy_return_20d)
        
        all_stock_data.update(batch_data)
        all_failed.extend(batch_failed)
        
        batch_passed = sum(1 for data in batch_data.values() if data['ma_status']['passes_filters'])
        print(f"Lote completado: {len(batch_data)} procesadas, {batch_passed} pasan filtros, {len(batch_failed)} errores")
        
        if batch_num < total_batches - 1:
            print("Pausa 10s...")
            time.sleep(10)  # delay_between_batches = 15s
    
    # Resultados finales
    print(f"\n=== RESUMEN FINAL ===")
    print(f"Procesadas: {len(all_stock_data)} | Errores: {len(all_failed)}")
    
    if all_stock_data:
        all_summary, filtered_summary = extractor.save_ma_data(all_stock_data)
        
        passed_count = len(filtered_summary) if not filtered_summary.empty else 0
        filter_rate = (passed_count / len(all_stock_data)) * 100 if len(all_stock_data) > 0 else 0
        
        print(f"Acciones que PASAN filtros: {passed_count}")
        print(f"Tasa de éxito: {filter_rate:.1f}%")
        
        if spy_return_20d:
            print(f"SPY 20d: {spy_return_20d:+.2f}%")
        
        # ANÁLISIS DE RAZONES DE ELIMINACIÓN (TOP 10)
        if len(all_summary) > 0:
            print(f"\n=== RAZONES DE ELIMINACIÓN (TOP 10) ===")
            filter_reasons_count = {}
            total_stocks = len(all_summary)
            
            for _, row in all_summary.iterrows():
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
            
            if not filter_reasons_count:
                print("  (Todas las acciones pasaron los filtros)")
        
    else:
        print("❌ No se obtuvieron datos")
        exit(1)

if __name__ == "__main__":
    main()