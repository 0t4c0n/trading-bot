import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import json
from io import StringIO
import os
import numpy as np

class MinerviniStockScreener:
    def __init__(self):
        self.stock_symbols = []
        # --- CONSTANTES DE FILTRADO MINERVINI ---
        # Hacer estos valores configurables facilita el ajuste de la sensibilidad del screener.
        self.MIN_RS_RATING = 70
        self.MIN_PCT_ABOVE_LOW = 30.0  # El precio debe estar al menos un 30% por encima del mínimo de 52s.
        self.MAX_PCT_BELOW_HIGH = 25.0 # El precio debe estar a menos del 25% del máximo de 52s.
        self.MIN_EARNINGS_GROWTH = 0.25 # Crecimiento trimestral de beneficios (YoY) >= 25%
        self.MIN_REVENUE_GROWTH = 0.20  # Crecimiento de ingresos >= 20%
        self.MIN_ROE = 0.17             # Retorno sobre el patrimonio (ROE) >= 17%
        # --- CONSTANTES PARA EXCEPCIÓN DE LÍDERES DE MERCADO ---
        # Permite que acciones muy fuertes pasen el filtro del 30% sobre el mínimo si están muy cerca de máximos.
        self.MIN_PATTERN_SCORE = 5 # Puntuación mínima requerida en el análisis de patrones (VCP/Acumulación)
        self.STRONG_LEADER_MAX_PCT_BELOW_HIGH = 5.0 # Debe estar a menos del 5% del máximo de 52s.
        self.STRONG_LEADER_MIN_RS = 85              # Y tener un RS Rating superior a 85.
        # --- CONSTANTES PARA FILTRO DE CRECIMIENTO INTELIGENTE ---
        self.EXCEPTIONAL_EARNINGS_GROWTH = 0.40 # Umbral para "centrales de productividad"
        self.DECENT_REVENUE_GROWTH = 0.10       # Requisito de ingresos más bajo para esas centrales

    def get_nyse_nasdaq_symbols(self):
        """Obtiene símbolos de NYSE y NASDAQ combinados"""
        all_symbols = []
        
        try:
            nyse_symbols = self.get_exchange_symbols('NYSE')
            nasdaq_symbols = self.get_exchange_symbols('NASDAQ')
            
            # Combinar y eliminar duplicados ya se hace en el flujo principal
            return list(set(nyse_symbols + nasdaq_symbols))
            
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
                    rows = data['data']['table']['rows']
                    # La API ya no devuelve 'assetType', asumimos que todos son stocks.
                    # El filtro secundario en main() limpiará los tickers no deseados.
                    symbols = [row['symbol'] for row in rows]
                    
                    print(f"  Obtenidos {len(symbols)} símbolos de {exchange}.")
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
    
    def calculate_moving_averages(self, df):
        """Calcula las medias móviles de 10, 21, 50, 150 y 200 días"""
        try:
            df['MA_10'] = df['Close'].rolling(window=10).mean()
            df['MA_21'] = df['Close'].rolling(window=21).mean()
            df['MA_50'] = df['Close'].rolling(window=50).mean()
            df['MA_150'] = df['Close'].rolling(window=150).mean()
            df['MA_200'] = df['Close'].rolling(window=200).mean()
            
            return df
        except Exception as e:
            print(f"Error calculando medias móviles: {e}")
            return df
    
    def calculate_52_week_range(self, df):
        """Calcula máximo y mínimo de 52 semanas"""
        try:
            weeks_52 = 252  # ~52 semanas de trading
            
            recent_data = df.tail(weeks_52)
            high_52w = recent_data['High'].max()
            low_52w = recent_data['Low'].min()
            
            return high_52w, low_52w
        except Exception as e:
            print(f"Error calculando 52-week range: {e}")
            return None, None
    
    def analyze_vcp_characteristics(self, df, high_52w, volume_50d_avg):
        """Análisis multifactorial de VCP (Volatility Contraction Pattern)"""
        try:
            if len(df) < 60 or not high_52w or not volume_50d_avg:
                return {'vcp_detected': False, 'details': ['Datos insuficientes']}

            current_price = df['Close'].iloc[-1]
            
            # 1. CONTEXTO: Cerca del máximo de 52 semanas
            price_near_high = (high_52w - current_price) / high_52w <= 0.15  # Dentro del 15% del máximo
            if not price_near_high:
                return {'vcp_detected': False, 'is_in_pivot': False, 'details': ['No está cerca del máximo 52w']}
            
            # 2. CONTRACCIÓN DE VOLATILIDAD (VCP - Ingrediente #1): El resorte se comprime.
            # Volatilidad en los últimos 10 días vs los últimos 50 días
            vol_10d = (df['High'].tail(10).max() - df['Low'].tail(10).min()) / df['Close'].tail(10).mean()
            vol_50d = (df['High'].tail(50).max() - df['Low'].tail(50).min()) / df['Close'].tail(50).mean()
            
            volatility_tightening = vol_10d < (vol_50d * 0.6) # La volatilidad reciente es <60% de la anterior

            # 3. SEQUÍA DE VOLUMEN (LÓGICA MEJORADA): Los vendedores se agotan.
            # En lugar de una media, contamos el número de días con volumen por debajo del promedio.
            # Esto es más robusto contra picos de volumen aislados.
            low_volume_days = df['Volume'].tail(10) < volume_50d_avg
            # Requerimos que al menos 5 de los últimos 10 días tengan volumen bajo.
            volume_dry_up = low_volume_days.sum() >= 5
            
            # 4. PUNTO PIVOTE (La calma antes de la explosión): Rango de precio ultra-estrecho.
            # El precio se mueve lateralmente en un rango muy ajustado en los últimos días.
            price_range_5d = (df['High'].tail(5).max() - df['Low'].tail(5).min()) / current_price
            is_in_tight_range = price_range_5d < 0.025 # Rango ajustado a <2.5% en los últimos 5 días

            # --- LÓGICA DE DECISIÓN ---
            # Se considera que hay un patrón VCP general si la volatilidad se contrae Y el volumen se seca.
            vcp_detected = volatility_tightening and volume_dry_up
            
            # Se considera que está en un PUNTO PIVOTE accionable si se cumplen las condiciones de VCP
            # Y ADEMÁS el precio está en ese rango ultra-estrecho. Esta es la señal de mayor calidad.
            is_in_pivot = vcp_detected and is_in_tight_range
            
            details = []
            if volatility_tightening: details.append(f"Volatilidad contraída (10d: {vol_10d:.2%}, 50d: {vol_50d:.2%})")
            if volume_dry_up: details.append(f"Volumen seco ({low_volume_days.sum()}/10 días < media)")
            if is_in_tight_range: details.append("Rango estrecho (<3% en 5d)")
            if is_in_pivot: details.append("✅ SEÑAL PIVOTE ACTIVA")

            return {
                'vcp_detected': vcp_detected,
                'volatility_tightening': volatility_tightening,
                'volume_dry_up': volume_dry_up,
                'is_in_pivot': is_in_pivot,
                'details': details if details else ["Sin señales claras de VCP"]
            }
            
        except Exception as e:
            print(f"Error analizando VCP: {e}")
            return {'vcp_detected': False, 'is_in_pivot': False, 'details': [f'Error: {e}']}
    
    def detect_institutional_accumulation(self, df, volume_50d_avg):
        """Detecta evidencia básica de acumulación institucional"""
        try:
            if len(df) < 50:
                return False
            
            recent_data = df.tail(20)
            
            # 1. Días de acumulación superan a los de distribución
            accumulation_days = (recent_data['Close'] > recent_data['Open']) & (recent_data['Volume'] > volume_50d_avg)
            distribution_days = (recent_data['Close'] < recent_data['Open']) & (recent_data['Volume'] > volume_50d_avg)
            volume_increase = accumulation_days.sum() > distribution_days.sum()

            # 2. Ratio de volumen UP/DOWN (OBV-like)
            # Suma el volumen en días de subida y resta el de días de bajada. Un valor positivo indica presión compradora.
            up_volume = recent_data[recent_data['Close'] > recent_data['Open']]['Volume'].sum()
            down_volume = recent_data[recent_data['Close'] < recent_data['Open']]['Volume'].sum()
            up_days_ratio = up_volume > (down_volume * 1.2) # Volumen de subida es al menos un 20% mayor

            # 3. Detección de "Pocket Pivot" (señal institucional clave)
            # Un día de subida cuyo volumen es mayor que el de CUALQUIER día de bajada en los últimos 10 días.
            last_10_days = df.tail(10)
            down_day_volumes = last_10_days[last_10_days['Close'] < last_10_days['Open']]['Volume']
            max_down_volume = down_day_volumes.max() if not down_day_volumes.empty else 0
            
            # Buscamos si en los últimos 5 días hubo un pocket pivot
            up_days_last_5 = last_10_days.tail(5)[last_10_days['Close'] > last_10_days['Open']]
            neutral_volume_high = (up_days_last_5['Volume'] > max_down_volume).any() if not up_days_last_5.empty else False

            # Scoring de acumulación (requiere 2 de 3 señales)
            accumulation_score = 0
            if volume_increase: accumulation_score += 1
            if up_days_ratio > 0.65: accumulation_score += 1  # Aumentado threshold
            if neutral_volume_high: accumulation_score += 1
            
            return accumulation_score >= 2  # Require 2/3 criterios
            
        except Exception as e:
            print(f"Error detectando acumulación institucional: {e}")
            return False
    
    def hybrid_institutional_evidence(self, symbol, df, ticker_info, volume_50d_avg):
        """Sistema híbrido mejorado para detectar evidencia institucional real"""
        try:
            evidence_score = 0
            evidence_details = []
            
            # 1. ANÁLISIS BÁSICO DE VOLUMEN/PRECIO (0-2 puntos)
            basic_accumulation = self.detect_institutional_accumulation(df, volume_50d_avg)
            if basic_accumulation:
                evidence_score += 2
                evidence_details.append("Volume accumulation pattern detected")
            else:
                evidence_details.append("No clear volume accumulation")
            
            # 2. CRITERIOS DE TAMAÑO MINERVINI (0-2 puntos)
            market_cap = ticker_info.get('marketCap', 0) if ticker_info else 0
            if market_cap > 0:
                if 500_000_000 <= market_cap <= 50_000_000_000:  # $500M - $50B sweet spot
                    evidence_score += 2
                    evidence_details.append(f"Optimal market cap: ${market_cap/1_000_000_000:.1f}B")
                elif market_cap >= 100_000_000:  # Mínimo $100M
                    evidence_score += 1
                    evidence_details.append(f"Acceptable market cap: ${market_cap/1_000_000_000:.1f}B")
                else:
                    evidence_details.append(f"Too small market cap: ${market_cap/1_000_000:.0f}M")
            else:
                evidence_details.append("Market cap data unavailable")
            
            # 3. ANÁLISIS DE FLOAT INSTITUCIONAL (0-2 puntos)
            shares_outstanding = ticker_info.get('sharesOutstanding', 0) if ticker_info else 0
            float_shares = ticker_info.get('floatShares', 0) if ticker_info else 0
            
            if shares_outstanding > 0 and float_shares > 0:
                institutional_ratio = 1 - (float_shares / shares_outstanding)
                if institutional_ratio > 0.6:  # >60% locked up
                    evidence_score += 2
                    evidence_details.append(f"High institutional ownership: {institutional_ratio*100:.1f}%")
                elif institutional_ratio > 0.4:  # >40% locked up
                    evidence_score += 1
                    evidence_details.append(f"Moderate institutional ownership: {institutional_ratio*100:.1f}%")
                else:
                    evidence_details.append(f"Low institutional ownership: {institutional_ratio*100:.1f}%")
            else:
                evidence_details.append("Float/shares outstanding data unavailable")
            
            # 4. LIQUIDEZ INSTITUCIONAL (0-1 punto)
            current_price = df['Close'].iloc[-1] if not df.empty else 0
            avg_volume = volume_50d_avg if volume_50d_avg else 0
            daily_dollar_volume = avg_volume * current_price
            
            if daily_dollar_volume > 5_000_000:  # >$5M daily volume
                evidence_score += 1
                evidence_details.append(f"Adequate liquidity: ${daily_dollar_volume/1_000_000:.1f}M daily")
            else:
                evidence_details.append(f"Low liquidity: ${daily_dollar_volume/1_000_000:.1f}M daily")
            
            # 5. CRITERIO DE SHARES OUTSTANDING MINERVINI (0-1 punto)
            if shares_outstanding > 0:
                if shares_outstanding < 100_000_000:  # <100M shares (preferencia Minervini)
                    evidence_score += 1
                    evidence_details.append(f"Good share count: {shares_outstanding/1_000_000:.0f}M shares")
                else:
                    evidence_details.append(f"High share count: {shares_outstanding/1_000_000:.0f}M shares")
            
            # SCORING FINAL: Require 5/8 puntos para pasar el filtro
            passes_institutional = evidence_score >= 5
            
            # Para debugging - mostrar detalles solo para stocks que pasan otros filtros
            if passes_institutional:
                details_str = " | ".join(evidence_details[:2])  # Mostrar top 2 reasons
                print(f"    📊 {symbol} Institutional Evidence: {evidence_score}/8 - {details_str}")
            
            return passes_institutional, evidence_score, evidence_details
            
        except Exception as e:
            print(f"Error en análisis institucional híbrido para {symbol}: {e}")
            return False, 0, ["Error in analysis"]

    def get_pattern_score(self, vcp_analysis, institutional_accumulation):
        """
        Sistema de puntuación integrado para VCP y acumulación.
        Reemplaza la lógica binaria 'OR' por un score más matizado.
        """
        score = 0
        details = []

        # La señal de mayor calidad es un punto pivote accionable.
        if vcp_analysis.get('is_in_pivot', False):
            score += 8  # Puntuación muy alta
            details.append("Pivot Point (+8)")
        # Si no está en pivote, pero hay un VCP general, también es muy bueno.
        elif vcp_analysis.get('vcp_detected', False):
            score += 5
            details.append("VCP Detected (+5)")
        
        # La acumulación institucional siempre es una buena señal.
        if institutional_accumulation:
            # Si ya hay un VCP, la acumulación es una confirmación extra.
            # Si no hay VCP, es la señal principal.
            score += 4
            details.append("Institutional Accumulation (+4)")

        return score, details

    
    def calculate_minervini_score(self, analysis):
        """Calcula score Minervini (0-100) para ranking"""
        try:
            score = 0
            
            # 1. Stage Analysis (0-40 points) - PESO PRINCIPAL
            stage = analysis.get('stage_analysis', '')
            if 'Stage 2' in stage:
                score += 40
            elif 'Stage 1' in stage or 'Stage 3' in stage:
                score += 20
            elif 'Stage 4' in stage:
                score += 0
            else:
                score += 10  # Unknown/developing
            
            # 2. RS Rating (0-30 points) - SEGUNDO PESO
            rs_rating = analysis.get('rs_rating', 0)
            if rs_rating:
                score += min((rs_rating / 100) * 30, 30)
            
            # 3. 52-Week Position (0-20 points)
            dist_from_high = analysis.get('distance_to_52w_high', 100)
            dist_from_low = analysis.get('distance_from_52w_low', 0)
            
            if dist_from_high is not None and dist_from_low is not None:
                # Cerca del máximo (0-25% away) = más puntos
                high_score = max(10 - (dist_from_high / 25) * 10, 0) if dist_from_high <= 25 else 0
                # Lejos del mínimo (30%+ away) = más puntos  
                low_score = min((dist_from_low - 30) / 70 * 10, 10) if dist_from_low >= 30 else 0
                score += high_score + low_score
            
            # 4. Technical Patterns & Volume (0-10 points) - BONIFICACIONES
            # Usamos el nuevo pattern_score para una bonificación más precisa
            pattern_score = analysis.get('pattern_score', 0)
            score += min(pattern_score, 10) # Añade el score del patrón, con un máximo de 10 puntos

            if analysis.get('earnings_acceleration', False):
                score += 2
            if analysis.get('roe_strong', False):
                score += 2
                
            # Penalizar fuertemente si falla un filtro fundamental crítico.
            # Esto ajusta el ranking para que las acciones que fallan en fundamentales (ej. sin beneficios)
            # aparezcan más abajo que aquellas con solo fallos técnicos menores.
            if analysis.get('is_fundamental_failure', False):
                score *= 0.6 # Reducir el score en un 40%

            # Penalizar si el precio está extendido, bonificar si está en un punto de entrada accionable
            if analysis.get('is_extended', False):
                score *= 0.8  # Penalización del 20% por estar extendida
            if analysis.get('is_actionable_entry', False):
                score += 10 # Bonificación de 10 puntos por setup accionable
                
            return min(round(score, 1), 100)
            
        except Exception as e:
            print(f"Error calculando Minervini Score: {e}")
            return 0
    
    def get_minervini_analysis(self, df, rs_rating, ticker_info=None, symbol="UNKNOWN"):
        """Análisis completo y optimizado con 'early exit' según metodología SEPA de Minervini"""
        # --- INICIALIZAR DICCIONARIO DE RESULTADOS ---
        # Esto simplifica el retorno, ya que solo actualizamos los campos necesarios.
        result = {
            'current_price': None, 'stage_analysis': 'Unknown', 'passes_all_filters': False,
            'minervini_score': 0, 'filter_reasons': [], 'rs_rating': rs_rating,
            'passes_minervini_technical': False, 'passes_minervini_fundamental': False,
            'ma_50': None, 'ma_150': None, 'ma_200': None, 'high_52w': None, 'low_52w': None,
            'distance_from_52w_low': None, 'distance_to_52w_high': None, 'pattern_score': 0,
            'vcp_detected': False, 'entry_signal': 'N/A', 'is_extended': False, 'is_actionable_entry': False,
            'vcp_analysis': {}, 'institutional_accumulation': False, 'institutional_evidence': False,
            'institutional_score': 0, 'institutional_details': [], 'volume_50d_avg': None,
            'earnings_acceleration': False, 'roe_strong': False
        }

        try:
            result['rs_rating'] = rs_rating

            # --- GUARDIA INICIAL: DATOS INSUFICIENTES ---
            if df.empty or len(df) < 252:
                result['stage_analysis'] = 'Insufficient Data'
                result['filter_reasons'] = ['Datos insuficientes (<252 días)']
                return result
            
            # --- CÁLCULOS BÁSICOS INICIALES ---
            latest = df.iloc[-1]
            current_price = latest['Close']
            ma_10 = latest['MA_10']
            ma_21 = latest['MA_21']
            ma_50 = latest['MA_50']
            ma_150 = latest['MA_150'] 
            ma_200 = latest['MA_200']
            high_52w, low_52w = self.calculate_52_week_range(df)
            volume_50d_avg = df['Volume'].tail(50).mean()
            
            # --- ACTUALIZAR RESULTADO CON DATOS BÁSICOS (ANTES DE FILTRAR) ---
            # Esto asegura que los datos existan en el CSV incluso si la acción es rechazada.
            result.update({
                'current_price': round(current_price, 2),
                'ma_50': round(ma_50, 2) if pd.notna(ma_50) else None,
                'ma_150': round(ma_150, 2) if pd.notna(ma_150) else None,
                'ma_200': round(ma_200, 2) if pd.notna(ma_200) else None,
                'high_52w': round(high_52w, 2) if high_52w else None,
                'low_52w': round(low_52w, 2) if low_52w else None,
                'volume_50d_avg': int(volume_50d_avg) if volume_50d_avg else None
            })

            # --- ANÁLISIS DE PUNTO DE ENTRADA (SE CALCULA SIEMPRE PARA EL SCORE Y EL DASHBOARD) ---
            price_vs_ma10_pct = ((current_price - ma_10) / ma_10) * 100 if pd.notna(ma_10) else 999
            price_vs_ma21_pct = ((current_price - ma_21) / ma_21) * 100 if pd.notna(ma_21) else 999
            is_extended = price_vs_ma10_pct > 10 or price_vs_ma21_pct > 15 # Umbrales de extensión
            result['is_extended'] = is_extended

            vcp_analysis = self.analyze_vcp_characteristics(df, high_52w, volume_50d_avg)

            # --- EMBUDO DE FILTRADO TÉCNICO (EARLY EXIT) ---
            def reject_and_return(stage, reason, passes_technical=False):
                """Función interna para actualizar y devolver el diccionario de resultados en caso de rechazo."""
                result['stage_analysis'] = stage
                result['filter_reasons'] = [reason]
                result['passes_minervini_technical'] = passes_technical
                is_fundamental_failure = passes_technical # True if it's a fundamental failure
                
                # Para que el score de las acciones rechazadas sea más preciso,
                # calculamos las distancias y las pasamos al scorer.
                dist_from_high = ((high_52w - current_price) / high_52w) * 100 if high_52w else 100
                dist_from_low = ((current_price - low_52w) / low_52w) * 100 if low_52w else 0

                analysis_for_scoring = {
                    'stage_analysis': stage,
                    'rs_rating': rs_rating,
                    'is_fundamental_failure': is_fundamental_failure,
                    'distance_to_52w_high': dist_from_high,
                    'distance_from_52w_low': dist_from_low,
                    'is_extended': result.get('is_extended', False)
                }
                result['minervini_score'] = self.calculate_minervini_score(analysis_for_scoring)
                return result

            # FILTRO 1: TENDENCIA DE LARGO PLAZO (los más importantes y baratos)
            price_above_long_mas = current_price > ma_150 and current_price > ma_200 if pd.notna(ma_150) and pd.notna(ma_200) else False
            if not price_above_long_mas:
                return reject_and_return('Stage 4 (Decline)', "Precio por debajo de MA150 o MA200")

            ma150_above_ma200 = ma_150 > ma_200 if pd.notna(ma_150) and pd.notna(ma_200) else False
            if not ma150_above_ma200:
                return reject_and_return('Stage 1/3 (Base/Top)', "MA150 no está por encima de MA200")

            ma200_trending_up = False
            if pd.notna(ma_200):
                ma200_22_days_ago = df['MA_200'].iloc[-22]
                ma200_trending_up = ma_200 > ma200_22_days_ago if pd.notna(ma200_22_days_ago) else False
            if not ma200_trending_up:
                return reject_and_return('Stage 1/3 (Base/Top)', "MA200 no tiene tendencia alcista ≥1 mes")

            # FILTRO 2: JERARQUÍA DE MEDIAS MÓVILES
            ma_hierarchy = (current_price > ma_50 > ma_150 > ma_200) if all(pd.notna(x) for x in [ma_10, ma_21, ma_50, ma_150, ma_200]) else False
            if not ma_hierarchy:
                return reject_and_return('Stage 2 (Developing)', "Jerarquía MAs incorrecta (Price>MA50>MA150>MA200)")

            # FILTRO 3: POSICIÓN EN RANGO DE 52 SEMANAS
            if high_52w and low_52w:
                distance_from_low = ((current_price - low_52w) / low_52w) * 100
                price_above_low_threshold = distance_from_low >= self.MIN_PCT_ABOVE_LOW
            else:
                return reject_and_return('Stage 2 (Developing)', "No se pudo calcular rango 52w")

            if not price_above_low_threshold:
                # --- EXCEPCIÓN PARA LÍDERES DE BAJA VOLATILIDAD ---
                # Si la acción está muy cerca de su máximo (ej. <5%) y tiene un RS muy alto (ej. >85),
                # se le permite pasar aunque no esté un 30% sobre el mínimo.
                # Esto captura a los líderes que han subido de forma constante sin grandes correcciones.
                is_strong_leader_candidate = high_52w and ((high_52w - current_price) / high_52w) * 100 < self.STRONG_LEADER_MAX_PCT_BELOW_HIGH
                is_high_rs = rs_rating is not None and rs_rating > self.STRONG_LEADER_MIN_RS
                
                if not (is_strong_leader_candidate and is_high_rs):
                    return reject_and_return('Stage 2 (Developing)', "Precio no está 30%+ sobre mínimo 52w")
            
            if high_52w:
                distance_from_high = ((high_52w - current_price) / high_52w) * 100
                price_near_high = distance_from_high <= self.MAX_PCT_BELOW_HIGH
            else:
                return reject_and_return('Stage 2 (Developing)', "No se pudo calcular rango 52w")
            if not price_near_high:
                return reject_and_return('Stage 2 (Developing)', "Precio no está dentro del 25% del máximo 52w")

            # FILTRO 4: FUERZA RELATIVA
            rs_strong = rs_rating is not None and rs_rating >= self.MIN_RS_RATING
            if not rs_strong:
                return reject_and_return('Stage 2 (Developing)', "RS Rating insuficiente (<70)")

            # FILTRO ADICIONAL: PRECIO EXTENDIDO (GUARDIÁN CONTRA PERSECUCIÓN)
            # Este filtro es crucial en mercados alcistas fuertes para evitar comprar en picos.
            if result['is_extended']:
                return reject_and_return('Stage 2 (Developing)', "Precio extendido sobre MAs de corto plazo")

            # FILTRO 5: PATRONES DE PRECIO/VOLUMEN (más caros de calcular)
            # Actualizamos el resultado con el análisis VCP ahora que sabemos que no fue rechazado antes
            result['vcp_analysis'] = vcp_analysis
            result['vcp_detected'] = vcp_analysis['vcp_detected']

            vcp_detected = result['vcp_detected']
            institutional_accumulation = self.detect_institutional_accumulation(df, volume_50d_avg) if volume_50d_avg else False
            result['institutional_accumulation'] = institutional_accumulation
            
            pattern_score, pattern_details = self.get_pattern_score(vcp_analysis, institutional_accumulation)
            if pattern_score < self.MIN_PATTERN_SCORE:
                return reject_and_return('Stage 2 (Developing)', f"Patrón de precio/volumen insuficiente (Score: {pattern_score})")

            # --- SI LLEGA AQUÍ, PASA TODOS LOS FILTROS TÉCNICOS ---
            passes_technical = True
            stage_analysis = "Stage 2 (Uptrend)"
            result['passes_minervini_technical'] = True
            result['stage_analysis'] = stage_analysis

            # --- DETERMINAR SEÑAL DE ENTRADA (LÓGICA MEJORADA) ---
            entry_signal, is_actionable = self.get_entry_signal(df, vcp_analysis, is_extended)
            result['entry_signal'] = entry_signal
            result['is_actionable_entry'] = is_actionable

            # FILTRO FUNDAMENTAL CERO: BENEFICIOS POSITIVOS (NO NEGOCIABLE)
            # Descartar totalmente si no hay beneficios, como solicitado por el usuario.
            if ticker_info:
                net_income = ticker_info.get('netIncomeToCommon')
                # Si net_income es None, no podemos estar seguros, así que lo dejamos pasar.
                # Si es 0 o negativo, lo descartamos.
                if net_income is not None and net_income <= 0:
                    print(f"    - {symbol} Descartado: Beneficios negativos/nulos (${net_income/1_000_000:.1f}M)")
                    # Devolver None indica a la función que lo llama que descarte esta acción por completo.
                    return None

            # --- EMBUDO DE FILTRADO FUNDAMENTAL (EARLY EXIT) ---

            # FILTRO 6: EARNINGS
            strong_earnings = False
            earnings_acceleration = False
            if ticker_info:
                try:
                    quarterly_earnings_growth = ticker_info.get('earningsQuarterlyGrowth')
                    if quarterly_earnings_growth is not None:
                        strong_earnings = quarterly_earnings_growth >= self.MIN_EARNINGS_GROWTH
                        earnings_acceleration = quarterly_earnings_growth > 0.3  # >30% como proxy de aceleración
                    # Si 'earningsQuarterlyGrowth' es None, strong_earnings se mantendrá en False,
                    # lo que hará que la acción falle el filtro de crecimiento, como debe ser.
                except:
                    strong_earnings = False
            if not strong_earnings:
                reason = "Earnings growth <25.0% YoY o dato no disponible"
                return reject_and_return(stage_analysis, reason, passes_technical=True)

            # FILTRO 7: GROWTH (REVENUE + ROE)
            strong_growth = False
            roe_strong = False
            if ticker_info:
                quarterly_earnings_growth = ticker_info.get('earningsQuarterlyGrowth') # Necesario para la nueva lógica
                try: # Usamos un try-except más específico para evitar ocultar errores.
                    revenue_growth = ticker_info.get('revenueGrowth')
                    roe = ticker_info.get('returnOnEquity')

                    # --- LÓGICA DE FILTRO DE CRECIMIENTO INTELIGENTE (REFACTORIZADA) ---
                    # Un candidato debe tener datos de ROE y cumplir el mínimo.
                    # Esta es una condición común para ambos caminos de crecimiento.
                    has_strong_roe = roe is not None and roe >= self.MIN_ROE
                    roe_strong = has_strong_roe  # Guardamos para el scoring

                    if not has_strong_roe:
                        strong_growth = False
                    else:
                        # Ahora evaluamos los dos caminos posibles, sabiendo que el ROE es bueno.
                        # Camino 1: Líder de Crecimiento Clásico (altos ingresos)
                        has_classic_growth = revenue_growth is not None and revenue_growth >= self.MIN_REVENUE_GROWTH
                        
                        # Camino 2: Central de Productividad (beneficios excepcionales con ingresos decentes)
                        is_profit_powerhouse = (
                            quarterly_earnings_growth is not None and 
                            quarterly_earnings_growth >= self.EXCEPTIONAL_EARNINGS_GROWTH and
                            revenue_growth is not None and
                            revenue_growth >= self.DECENT_REVENUE_GROWTH
                        )

                        strong_growth = has_classic_growth or is_profit_powerhouse
                except Exception as e:
                    print(f"    - {symbol} Error en filtro de crecimiento: {e}")
                    strong_growth = False
            if not strong_growth:
                return reject_and_return(stage_analysis, "Growth/Profitability insuficiente", passes_technical=True)

            # FILTRO 8: EVIDENCIA INSTITUCIONAL
            institutional_evidence = False
            institutional_score = 0
            institutional_details = []
            if volume_50d_avg:
                passes_institutional, institutional_score, institutional_details = self.hybrid_institutional_evidence(
                    symbol, df, ticker_info, volume_50d_avg
                )
                institutional_evidence = passes_institutional
            if not institutional_evidence:
                reason = "Evidencia institucional insuficiente"
                return reject_and_return(stage_analysis, reason, passes_technical=True)

            # --- ¡ÉXITO! LA ACCIÓN PASA TODOS LOS FILTROS ---
            passes_fundamental = True
            passes_all_filters = passes_technical and passes_fundamental
            result['passes_minervini_fundamental'] = True

            analysis_for_scoring = {
                'stage_analysis': stage_analysis,
                'rs_rating': rs_rating,
                'distance_to_52w_high': distance_from_high,
                'distance_from_52w_low': distance_from_low,
                'pattern_score': pattern_score, # Usamos el nuevo score
                'vcp_detected': vcp_detected, # Mantenemos para info
                'institutional_evidence': institutional_evidence,
                'institutional_score': institutional_score,
                'earnings_acceleration': earnings_acceleration,
                'roe_strong': roe_strong,
                'is_extended': is_extended,  # Para penalizar en el score
                'is_actionable_entry': is_actionable  # Para bonificar en el score
            }
            minervini_score = self.calculate_minervini_score(analysis_for_scoring)

            # Actualizar el diccionario de resultados con todos los datos de la acción exitosa
            result.update({
                'ma_50': round(ma_50, 2) if pd.notna(ma_50) else None, 'ma_150': round(ma_150, 2) if pd.notna(ma_150) else None,
                'ma_200': round(ma_200, 2) if pd.notna(ma_200) else None, 'high_52w': round(high_52w, 2) if high_52w else None,
                'low_52w': round(low_52w, 2) if low_52w else None, 'distance_from_52w_low': round(distance_from_low, 1) if distance_from_low else None,
                'distance_to_52w_high': round(distance_from_high, 1) if distance_from_high else None, 'pattern_score': pattern_score, 'vcp_detected': vcp_detected,
                'entry_signal': entry_signal, 'is_extended': is_extended, 'is_actionable_entry': is_actionable,
                'vcp_analysis': vcp_analysis, 'institutional_accumulation': basic_accumulation, 'institutional_evidence': institutional_evidence, 
                'institutional_score': institutional_score, 'institutional_details': institutional_details,
                'volume_50d_avg': int(volume_50d_avg) if volume_50d_avg else None, 'earnings_acceleration': earnings_acceleration,
                'roe_strong': roe_strong, 'passes_all_filters': passes_all_filters, 'minervini_score': minervini_score,
                'filter_reasons': ["✅ PASA TODOS LOS FILTROS MINERVINI"]
            })
            return result
            
        except Exception as e:
            print(f"Error en análisis Minervini: {e}")
            result['stage_analysis'] = 'Error en cálculo'
            result['filter_reasons'] = ['Error de cálculo']
            return result

    def get_entry_signal(self, df, vcp_analysis, is_extended):
        """
        Determina la mejor señal de entrada analizando múltiples patrones.
        Devuelve la señal (string) y si es un punto de entrada accionable (boolean).
        """
        # Prioridad 1: Pivote VCP (la señal de más bajo riesgo)
        if vcp_analysis.get('is_in_pivot', False):
            return "Pivot Point", True

        current_price = df['Close'].iloc[-1]

        # Prioridad 2: Rebote en la media móvil de 50 días (una entrada de pullback clásica)
        ma_50_series = df['MA_50']
        if pd.notna(ma_50_series.iloc[-1]):
            ma_50 = ma_50_series.iloc[-1]
            # La MA50 debe estar en tendencia alcista
            ma_50_uptrend = ma_50 > ma_50_series.iloc[-20] if len(df) > 20 else False
            if ma_50_uptrend:
                # LÓGICA MEJORADA: Compara el Low de cada día con la MA50 de ese día.
                # El precio tocó o perforó ligeramente la MA50 en los últimos 10 días
                touched_ma50 = (df['Low'].tail(10) < ma_50_series.tail(10) * 1.03).any()
                # El precio ahora está rebotando, pero no se ha extendido demasiado (>7%)
                is_bouncing = current_price > ma_50 and ((current_price - ma_50) / ma_50) < 0.07
                if touched_ma50 and is_bouncing:
                    return "MA-Bounce-50", True

        # Prioridad 3: Rebote en la media móvil de 21 días (para pullbacks más cortos)
        ma_21_series = df['MA_21']
        if pd.notna(ma_21_series.iloc[-1]):
            ma_21 = ma_21_series.iloc[-1]
            # LÓGICA MEJORADA: Compara el Low de cada día con la MA21 de ese día.
            # El precio tocó o perforó ligeramente la MA21 en los últimos 5 días
            touched_ma21 = (df['Low'].tail(5) < ma_21_series.tail(5) * 1.02).any()
            # El precio ahora está rebotando, pero no se ha extendido demasiado (>5%)
            is_bouncing_21 = current_price > ma_21 and ((current_price - ma_21) / ma_21) < 0.05
            if touched_ma21 and is_bouncing_21:
                return "MA-Bounce-21", True

        # Si no hay señal de entrada, determinar si está extendido o consolidando
        if is_extended:
            return "Extendido", False
        
        return "Consolidando", False
    
    def process_stocks_with_minervini(self, symbols, all_historical_data, rs_ratings):
        """Aplica análisis Minervini a datos pre-descargados. Solo descarga ticker.info (fundamentales)."""
        stock_data = {}
        failed_symbols = []
        
        for i, symbol in enumerate(symbols, 1):
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # El historial ya está descargado, solo lo recuperamos del diccionario
                    hist = all_historical_data.get(symbol)
                    if hist is None or hist.empty:
                        raise ValueError("Datos históricos no encontrados en el diccionario pre-cargado.")
                    
                    if not hist.empty and len(hist) >= 250:  # Mínimo para análisis Minervini
                        hist_with_ma = self.calculate_moving_averages(hist)
                        
                        try:
                            # La única llamada de red aquí es para los datos fundamentales (.info)
                            ticker = yf.Ticker(symbol)
                            ticker_info = ticker.info
                            company_info = {
                                'name': ticker_info.get('longName', 'N/A'),
                                'sector': ticker_info.get('sector', 'N/A'),
                                'industry': ticker_info.get('industry', 'N/A'),
                                'market_cap': ticker_info.get('marketCap', 'N/A')
                            }
                        except Exception as info_error:
                            error_str = str(info_error).lower()
                            # Estrategia de reintento diferenciada
                            if "401" in error_str: # Error de autorización persistente
                                wait_time = 60 # Pausa larga para "enfriar" la conexión
                                print(f"⏳ {symbol} - Error 401 (Unauthorized). Pausa larga de {wait_time}s. Reintentando...")
                                time.sleep(wait_time)
                                retry_count += 1
                                continue
                            elif "rate" in error_str or "429" in error_str: # Rate limit normal
                                time.sleep(2 ** retry_count)
                                retry_count += 1
                                continue
                            else:
                                # CAMBIO CLAVE: Descartar si .info falla por otra razón
                                print(f"✗ {symbol} - Descartado: No se pudo obtener .info (fundamentales). Error: {info_error}")
                                failed_symbols.append(symbol)
                                success = True # Marcar como "manejado" para salir del bucle de reintentos
                                continue # Saltar al siguiente símbolo en el lote

                        # Verificación adicional: a veces .info devuelve un dict vacío sin error
                        if not ticker_info or 'sector' not in ticker_info:
                            print(f"✗ {symbol} - Descartado: .info devuelto vacío o incompleto.")
                            failed_symbols.append(symbol)
                            success = True # BUG FIX: Marcar como manejado para salir del bucle de reintentos
                            continue # Saltar al siguiente símbolo
                        
                        stock_rs_rating = rs_ratings.get(symbol)
                        minervini_analysis = self.get_minervini_analysis(hist_with_ma, stock_rs_rating, ticker_info, symbol)
                        
                        # Si el análisis devuelve None, es porque la acción fue descartada (ej. beneficios negativos)
                        if minervini_analysis is None:
                            success = True # Marcamos como éxito para no reintentar
                            # Al poner success=True, el bucle while terminará y pasará al siguiente símbolo.
                            # No se añadirá a stock_data.
                            continue

                        stock_data[symbol] = {
                            'data': hist_with_ma,
                            'minervini_analysis': minervini_analysis,
                            'info': company_info
                        }
                        
                        # Status reporting
                        stage = minervini_analysis.get('stage_analysis', 'Unknown')
                        rs_rating = minervini_analysis.get('rs_rating', 0)
                        price = minervini_analysis.get('current_price', 0)
                        score = minervini_analysis.get('minervini_score', 0)
                        
                        # Imprimir solo si la acción pasa todos los filtros para mantener el log limpio
                        if minervini_analysis.get('passes_all_filters', False):
                            status = f"✅ STAGE 2"
                            reason_str = f"Score:{score} | RS:{rs_rating} | {stage}"
                            retry_info = f" (retry {retry_count})" if retry_count > 0 else ""
                            print(f"{status} {symbol} - ${price:.2f} - {reason_str}{retry_info} - {i}/{len(symbols)}")
                        success = True
                        
                    else:
                        failed_symbols.append(symbol)
                        print(f"✗ {symbol} - Datos insuficientes (<250 días)")
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
                        print(f"✗ {symbol} - Error en el bucle principal de procesamiento: {e}")
                        break
                
                if success or retry_count >= max_retries:
                    time.sleep(0.5)  # Pausa aumentada para ser más amable con la API
                    
        return stock_data, failed_symbols

    def calculate_all_rs_scores(self, all_data):
        """Paso 1 y 2 para RS Rating: Calcula el score de rendimiento para todas las acciones."""
        print("\nCalculando scores de rendimiento para el RS Rating...")
        rs_scores = {}
        
        for symbol, df in all_data.items():
            try:
                if len(df) < 252:
                    continue

                current_price = df['Close'].iloc[-1]
                p3 = ((current_price / df['Close'].iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
                p6 = ((current_price / df['Close'].iloc[-126]) - 1) * 100 if len(df) >= 126 else 0
                p9 = ((current_price / df['Close'].iloc[-189]) - 1) * 100 if len(df) >= 189 else 0
                p12 = ((current_price / df['Close'].iloc[-252]) - 1) * 100
                
                # Fórmula IBD: RS = 40% × P3 + 20% × P6 + 20% × P9 + 20% × P12
                rs_score = (0.4 * p3) + (0.2 * p6) + (0.2 * p9) + (0.2 * p12)
                rs_scores[symbol] = rs_score
            except Exception:
                continue # Ignorar errores en acciones individuales
        
        print(f"✓ Scores de rendimiento calculados para {len(rs_scores)} acciones.")
        return pd.Series(rs_scores)

    def calculate_rs_ratings_from_scores(self, rs_scores):
        """Paso 3 para RS Rating: Convierte scores en un ranking percentil (0-100)."""
        if rs_scores.empty:
            return pd.Series()
        
        # Usar rank(pct=True) para obtener el percentil (0.0 a 1.0)
        rs_ratings = rs_scores.rank(pct=True) * 100
        print(f"✓ RS Ratings (percentiles) calculados. Ejemplo: {rs_ratings.head(1).to_dict()}")
        return rs_ratings.round(1)

    def download_all_data(self, symbols, period="2y"):
        """Descarga datos históricos en lotes para evitar rate limiting y fallos masivos."""
        print(f"Iniciando descarga robusta de datos para {len(symbols)} símbolos...")
        all_data = {}
        batch_size = 75 # Reducido para mayor fiabilidad
        total_batches = (len(symbols) + batch_size - 1) // batch_size
        
        for i in range(total_batches):
            start_idx = i * batch_size
            end_idx = min(start_idx + batch_size, len(symbols))
            batch_symbols = symbols[start_idx:end_idx]
            
            print(f"  Descargando lote {i+1}/{total_batches} ({len(batch_symbols)} símbolos)...")
            
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    batch_data = yf.download(batch_symbols, period=period, group_by='ticker', auto_adjust=True, threads=True, progress=False)
                    
                    for symbol in batch_symbols:
                        if symbol in batch_data.columns:
                            # Asegurarse de que el df no está vacío y tiene datos válidos
                            df = batch_data[symbol].dropna()
                            if not df.empty:
                                all_data[symbol] = df
                    
                    print(f"  ✓ Lote {i+1} descargado con éxito.")
                    success = True
                    
                except Exception as e:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    print(f"  ⚠️ Error en lote {i+1}: {e}. Reintentando en {wait_time}s... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
            
            if not success:
                print(f"  ❌ Lote {i+1} falló después de {max_retries} reintentos. Omitiendo este lote.")
            
            time.sleep(1) # Pausa de 1s entre lotes para no saturar la API
        
        print(f"\n✓ Descarga masiva completada. Total de datos obtenidos para {len(all_data)} símbolos.")
        return all_data
    
    def save_minervini_data(self, stock_data, filename_prefix="minervini_sepa_analysis"):
        """Guarda los datos con análisis Minervini"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        all_data = []
        stage2_data = []
        
        for symbol, data in stock_data.items():
            hist_df = data['data']
            analysis = data['minervini_analysis']
            info = data['info']
            
            if not hist_df.empty:
                row_data = {
                    'Symbol': symbol,
                    'Company_Name': info.get('name', 'N/A'),
                    'Sector': info.get('sector', 'N/A'),
                    'Industry': info.get('industry', 'N/A'),
                    'Current_Price': analysis.get('current_price'),
                    'Minervini_Score': analysis.get('minervini_score'),
                    'MA_50': analysis.get('ma_50'),
                    'MA_150': analysis.get('ma_150'),
                    'MA_200': analysis.get('ma_200'),
                    'High_52w': analysis.get('high_52w'),
                    'Low_52w': analysis.get('low_52w'),
                    'Distance_From_52w_Low': analysis.get('distance_from_52w_low'),
                    'Distance_To_52w_High': analysis.get('distance_to_52w_high'),
                    'RS_Rating': analysis.get('rs_rating'),
                    'VCP_Detected': analysis.get('vcp_detected'),
                    'Institutional_Accumulation': analysis.get('institutional_accumulation'),     # Basic
                    'Institutional_Evidence': analysis.get('institutional_evidence'),             # Advanced
                    'Institutional_Score': analysis.get('institutional_score'),                   # Detailed score
                    'Volume_50d_Avg': analysis.get('volume_50d_avg'),
                    'Earnings_Acceleration': analysis.get('earnings_acceleration'),
                    'ROE_Strong': analysis.get('roe_strong'),
                    'Stage_Analysis': analysis.get('stage_analysis'),
                    'Passes_Technical': analysis.get('passes_minervini_technical'),
                    'Entry_Signal': analysis.get('entry_signal'),
                    'Is_Extended': analysis.get('is_extended'),
                    'Passes_Fundamental': analysis.get('passes_minervini_fundamental'),
                    'Passes_All_Filters': analysis.get('passes_all_filters'),
                    'Filter_Reasons': "; ".join(analysis.get('filter_reasons', [])),
                    'Data_Points': len(hist_df),
                    'Start_Date': hist_df.index.min().strftime('%Y-%m-%d'),
                    'End_Date': hist_df.index.max().strftime('%Y-%m-%d')
                }
                
                all_data.append(row_data)
                
                if analysis.get('passes_all_filters', False):
                    stage2_data.append(row_data)
        
        # Guardar TODOS los datos
        all_df = pd.DataFrame(all_data)
        all_filename = f"{filename_prefix}_ALL_DATA_{timestamp}.csv"
        all_df.to_csv(all_filename, index=False)
        print(f"✓ Guardado: {all_filename}")
        
        # Guardar SOLO Stage 2 stocks que pasan todos los filtros
        if stage2_data:
            stage2_df = pd.DataFrame(stage2_data)
            stage2_filename = f"{filename_prefix}_STAGE2_ONLY_{timestamp}.csv"
            stage2_df.to_csv(stage2_filename, index=False)
            print(f"✓ Guardado: {stage2_filename}")
        else:
            print("❌ Ninguna acción pasó todos los filtros Minervini")
            stage2_df = pd.DataFrame()
        
        return all_df, stage2_df

def main():
    """Función principal para GitHub Actions - Análisis Minervini SEPA completo"""
    print("=== MINERVINI SEPA AUTOMATED SCREENER ===")
    print("Sistema basado en metodología SEPA de Mark Minervini")
    print("11 filtros: 8 técnicos + 3 fundamentales + Scoring System\n")
    
    screener = MinerviniStockScreener()
    
    print("Obteniendo símbolos NYSE + NASDAQ...")
    all_symbols = screener.get_nyse_nasdaq_symbols()
    original_count = len(all_symbols)
    
    # Filtro final para eliminar tickers con caracteres especiales que puedan causar problemas
    all_symbols = [s for s in all_symbols if '^' not in s and '.' not in s and '/' not in s]
    print(f"✓ Símbolos filtrados (eliminados preferentes/warrants): {original_count - len(all_symbols)} eliminados")
    print(f"Total de acciones a analizar: {len(all_symbols)}")
    
    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        exit(1)
    
    # --- NUEVO FLUJO PARA RS RATING PRECISO ---
    
    # PASO 1: Descarga masiva de datos
    symbols_to_process = all_symbols
    all_historical_data = screener.download_all_data(symbols_to_process)
    
    # PASO 2: Calcular scores de rendimiento
    rs_scores = screener.calculate_all_rs_scores(all_historical_data)
    
    # PASO 3: Calcular RS Ratings finales (percentiles)
    rs_ratings = screener.calculate_rs_ratings_from_scores(rs_scores)
    
    # PASO 4: Análisis Minervini completo usando los RS Ratings pre-calculados
    batch_size = 30  # Reducido para mayor fiabilidad y evitar rate limits en .info
    print(f"\nIniciando análisis de {len(symbols_to_process)} acciones con criterios Minervini SEPA...")
    print("Usando RS Ratings pre-calculados para mayor precisión.\n")

    total_batches = (len(symbols_to_process) + batch_size - 1) // batch_size
    all_stock_data = {}
    all_failed = []
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(symbols_to_process))
        batch_symbols = symbols_to_process[start_idx:end_idx]        
        print(f"\n=== LOTE {batch_num + 1}/{total_batches} ({start_idx + 1}-{end_idx}) ===")
        
        # La función ahora recibe los datos históricos y solo descarga .info si es necesario
        batch_data, batch_failed = screener.process_stocks_with_minervini(batch_symbols, all_historical_data, rs_ratings)
        
        all_stock_data.update(batch_data)
        all_failed.extend(batch_failed)
        
        batch_passed = sum(1 for data in batch_data.values() if data['minervini_analysis']['passes_all_filters'])
        batch_filtered = len(batch_data) - batch_passed
        avg_score = np.mean([data['minervini_analysis']['minervini_score'] for data in batch_data.values()]) if batch_data else 0
        print(f"Lote completado: {batch_passed} Stage 2 | {batch_filtered} Filtradas | {len(batch_failed)} Errores | Score Promedio: {avg_score:.1f}")
        
        if batch_num < total_batches - 1:
            print("Pausa 30s...")
            time.sleep(30)  # Pausa aumentada para ser más amable con la API
    
    # Resultados finales
    print(f"\n=== RESUMEN FINAL MINERVINI ===")
    print(f"Procesadas: {len(all_stock_data)} | Errores: {len(all_failed)}")
    
    if all_stock_data:
        all_summary, stage2_summary = screener.save_minervini_data(all_stock_data)
        
        stage2_count = len(stage2_summary) if not stage2_summary.empty else 0
        success_rate = (stage2_count / len(all_stock_data)) * 100 if len(all_stock_data) > 0 else 0
        
        print(f"Acciones Stage 2 (pasan todos los filtros): {stage2_count}")
        print(f"Tasa de éxito Minervini: {success_rate:.1f}%")
        
        # Mostrar top 10 por Minervini Score
        if not all_summary.empty:
            top_10 = all_summary.nlargest(10, 'Minervini_Score')
            print(f"\n🔝 TOP 10 (Score más alto, no necesariamente pasan todos los filtros):")
            print(f"   (✅ Pasa todos los filtros | ⚠️ No pasa todos los filtros)")
            for i, (_, row) in enumerate(top_10.iterrows()):
                icon = "✅" if row['Passes_All_Filters'] else "⚠️"
                stage = row['Stage_Analysis'][:10] 
                rs = row['RS_Rating'] if pd.notna(row['RS_Rating']) else 0
                score = row['Minervini_Score']
                price = row['Current_Price']
                print(f"{i+1:2d}. {icon} {row['Symbol']:6s} Score:{score:5.1f} ${price:7.2f} RS:{rs:5.1f} {stage}")
        
        # Análisis por Stage
        if len(all_summary) > 0:
            stage_distribution = all_summary['Stage_Analysis'].value_counts()
            print(f"\n=== DISTRIBUCIÓN POR STAGE ===")
            for stage, count in stage_distribution.items():
                percentage = (count / len(all_summary)) * 100
                avg_score = all_summary[all_summary['Stage_Analysis'] == stage]['Minervini_Score'].mean()
                print(f"  {stage}: {count} acciones ({percentage:.1f}%) - Score promedio: {avg_score:.1f}")
        
        # Top razones de filtrado
        print(f"\n=== RAZONES DE ELIMINACIÓN (TOP 10) ===")
        filter_reasons_count = {}
        total_stocks = len(all_summary)
        
        for _, row in all_summary.iterrows():
            if not row['Passes_All_Filters']:
                reasons = str(row['Filter_Reasons']).split(';')
                for reason in reasons:
                    reason = reason.strip()
                    if reason and reason != "✅ PASA TODOS LOS FILTROS MINERVINI" and reason != "nan":
                        filter_reasons_count[reason] = filter_reasons_count.get(reason, 0) + 1
        
        for reason, count in sorted(filter_reasons_count.items(), key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_stocks) * 100
            print(f"  {reason}: {count} acciones ({percentage:.1f}%)")
        
    else:
        print("❌ No se obtuvieron datos")
        exit(1)

if __name__ == "__main__":
    main()