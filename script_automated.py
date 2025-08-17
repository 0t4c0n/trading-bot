import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import json
from io import StringIO
import os
from tqdm import tqdm
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
        # Se reduce a 4 para permitir que acciones con solo "Acumulación Institucional" (4 pts) pasen,
        # haciendo el filtro un poco menos restrictivo pero aún selectivo.
        self.MIN_PATTERN_SCORE = 4 # Puntuación mínima requerida en el análisis de patrones (VCP/Acumulación)
        self.STRONG_LEADER_MAX_PCT_BELOW_HIGH = 5.0 # Debe estar a menos del 5% del máximo de 52s.
        self.STRONG_LEADER_MIN_RS = 85              # Y tener un RS Rating superior a 85.
        # --- CONSTANTES PARA FILTRO DE CRECIMIENTO INTELIGENTE ---
        self.EXCEPTIONAL_EARNINGS_GROWTH = 0.40 # Umbral para "centrales de productividad"
        self.DECENT_REVENUE_GROWTH = 0.10       # Requisito de ingresos más bajo para esas centrales
        # --- CONSTANTES PARA ANÁLISIS DE PATRONES (VCP) ---
        self.VCP_MAX_PCT_FROM_HIGH = 0.15       # % máximo desde el máximo de 52s para ser considerado en contexto
        self.VCP_VOLATILITY_TIGHTENING_RATIO = 0.6 # La volatilidad de 10d debe ser <60% de la de 50d
        self.VCP_VOLUME_DRY_UP_DAYS = 10        # Días para analizar la sequía de volumen
        self.VCP_VOLUME_DRY_UP_MIN_DAYS = 5     # Mínimo de días con volumen bajo
        self.VCP_PIVOT_RANGE_DAYS = 5           # Días para analizar el rango de pivote
        self.VCP_PIVOT_MAX_PRICE_RANGE = 0.025  # Rango de precio máximo (<2.5%) para un pivote
        # --- SESIÓN DE RED COMPARTIDA PARA ROBUSTEZ ---
        # --- PARÁMETROS PARA REBOTE EN MEDIAS MÓVILES ---
        self.BOUNCE_PARAMS = {
            50: {'uptrend_days': 20, 'touch_days': 10, 'touch_proximity': 0.03, 'bounce_limit': 0.07},
            21: {'uptrend_days': 10, 'touch_days': 5, 'touch_proximity': 0.02, 'bounce_limit': 0.05}
        }
        self.session = requests.Session()

    def get_nyse_nasdaq_symbols(self):
        """Obtiene símbolos de NYSE y NASDAQ combinados"""
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
            
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            
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
            price_near_high = (high_52w - current_price) / high_52w <= self.VCP_MAX_PCT_FROM_HIGH
            if not price_near_high:
                return {'vcp_detected': False, 'is_in_pivot': False, 'details': ['No está cerca del máximo 52w']}
            
            # 2. CONTRACCIÓN DE VOLATILIDAD (VCP - Ingrediente #1): El resorte se comprime.
            # Volatilidad en los últimos 10 días vs los últimos 50 días
            vol_10d = (df['High'].tail(self.VCP_VOLUME_DRY_UP_DAYS).max() - df['Low'].tail(self.VCP_VOLUME_DRY_UP_DAYS).min()) / df['Close'].tail(self.VCP_VOLUME_DRY_UP_DAYS).mean()
            vol_50d = (df['High'].tail(50).max() - df['Low'].tail(50).min()) / df['Close'].tail(50).mean()
            
            volatility_tightening = vol_10d < (vol_50d * self.VCP_VOLATILITY_TIGHTENING_RATIO)

            # 3. SEQUÍA DE VOLUMEN (LÓGICA MEJORADA): Los vendedores se agotan.
            # En lugar de una media, contamos el número de días con volumen por debajo del promedio.
            # Esto es más robusto contra picos de volumen aislados.
            low_volume_days = df['Volume'].tail(self.VCP_VOLUME_DRY_UP_DAYS) < volume_50d_avg
            # Requerimos que al menos un número de días tengan volumen bajo.
            volume_dry_up = low_volume_days.sum() >= self.VCP_VOLUME_DRY_UP_MIN_DAYS
            
            # 4. PUNTO PIVOTE (La calma antes de la explosión): Rango de precio ultra-estrecho.
            # El precio se mueve lateralmente en un rango muy ajustado en los últimos días.
            price_range_5d = (df['High'].tail(self.VCP_PIVOT_RANGE_DAYS).max() - df['Low'].tail(self.VCP_PIVOT_RANGE_DAYS).min()) / current_price
            is_in_tight_range = price_range_5d < self.VCP_PIVOT_MAX_PRICE_RANGE

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
            # Un "pocket pivot" es un día de subida cuyo volumen es mayor que el volumen del día de bajada más alto de los últimos 10 días.
            # Buscamos esta señal en los últimos 5 días para confirmar un interés institucional reciente.
            last_10_days = df.tail(10)
            down_day_volumes = last_10_days[last_10_days['Close'] < last_10_days['Open']]['Volume']
            max_down_volume = down_day_volumes.max() if not down_day_volumes.empty else 0
            
            last_5_days = last_10_days.tail(5)
            up_days_last_5 = last_5_days[last_5_days['Close'] > last_5_days['Open']]
            has_pocket_pivot = (up_days_last_5['Volume'] > max_down_volume).any() if not up_days_last_5.empty else False

            # Scoring de acumulación (requiere 2 de 3 señales)
            accumulation_score = 0
            if volume_increase: accumulation_score += 1
            if up_days_ratio: accumulation_score += 1
            if has_pocket_pivot: accumulation_score += 1
            
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
            
            return passes_institutional, evidence_score, evidence_details
            
        except Exception as e:
            print(f"Error en análisis institucional híbrido para {symbol}: {e}")
            return False, 0, ["Error in analysis"]

    def get_pattern_score(self, vcp_analysis, institutional_accumulation):
        """
        Sistema de puntuación integrado para VCP y acumulación.
        Reemplaza la lógica binaria 'OR' por un score más matizado.
        Refactorizado para mayor claridad y mantenibilidad.
        """
        score = 0
        details = []

        # 1. Puntuación por Acumulación Institucional (señal de fondo)
        if institutional_accumulation:
            score += 4
            details.append("Institutional Accumulation (+4)")

        # 2. Puntuación por Patrón de Contracción de Volatilidad (VCP)
        # Estas condiciones son mutuamente excluyentes y representan la calidad del setup.
        # La señal de mayor calidad es un punto pivote accionable.
        if vcp_analysis.get('is_in_pivot', False):
            score += 8  # Puntuación máxima por setup de entrada ideal
            details.append("Pivot Point (+8)")
        # Si no está en pivote, pero hay un VCP general, también es muy bueno.
        elif vcp_analysis.get('vcp_detected', False):
            score += 5  # Puntuación estándar por contracción de volatilidad
            details.append("VCP Detected (+5)")

        return score, details

    
    def calculate_minervini_score(self, analysis):
        """
        Calcula un score Minervini (0-100) rediseñado para una mejor diferenciación y priorización de entradas.
        Utiliza un sistema de multiplicadores para las señales de entrada.
        """
        try:
            base_score = 0
            
            # 1. TENDENCIA Y ESTRUCTURA (Máx 35 puntos)
            stage = analysis.get('stage_analysis', '')
            if 'Stage 2' in stage:
                base_score += 35
            elif 'Stage 1' in stage or 'Stage 3' in stage:
                base_score += 15
            
            # 2. FUERZA RELATIVA (Máx 25 puntos)
            rs_rating = analysis.get('rs_rating', 0)
            if rs_rating:
                base_score += (rs_rating / 100) * 25
            
            # 3. PATRÓN DE PRECIO (Máx 20 puntos) - Usa directamente el pattern_score
            pattern_score = analysis.get('pattern_score', 0)
            # El score máximo de patrón es 12 (Pivot+Acum). Lo escalamos a 20 puntos.
            base_score += (pattern_score / 12) * 20

            # 4. PROXIMIDAD AL MÁXIMO (Máx 10 puntos) - Recompensa estar muy cerca del máximo
            dist_from_high = analysis.get('distance_to_52w_high', 100)
            if dist_from_high is not None:
                # Puntuación logarítmica inversa: más puntos cuanto más cerca de 0.
                proximity_score = 10 * (1 - (dist_from_high / self.MAX_PCT_BELOW_HIGH))
                base_score += max(0, proximity_score)

            # 5. BONIFICACIÓN FUNDAMENTAL (Máx 10 puntos)
            if analysis.get('earnings_acceleration', False):
                base_score += 5
            if analysis.get('roe_strong', False):
                base_score += 5

            # 6. MULTIPLICADOR DE SEÑAL DE ENTRADA (El factor decisivo)
            entry_signal = analysis.get('entry_signal', 'Consolidando')
            multipliers = {
                'Pivot Point': 1.15,  # Señal de máxima calidad
                'VCP Setup': 1.10,    # Setup de alta calidad, casi listo
                'MA-Bounce-50': 1.07, # Buen punto de entrada secundario
                'MA-Bounce-21': 1.05, # Buen punto de entrada, más agresivo
                'Consolidando': 1.0,  # Neutral, sin señal clara
                'Extendido': 0.8      # Penalización por estar extendido
            }
            final_score = base_score * multipliers.get(entry_signal, 1.0)
                
            return min(round(final_score, 1), 100)
            
        except Exception as e:
            print(f"Error calculando Minervini Score: {e}")
            return 0
    
    # --- FUNCIONES AUXILIARES DE FILTRADO (REFACTORIZACIÓN) ---
    # Estas funciones descomponen la lógica de get_minervini_analysis para mayor claridad.

    def _build_rejection_result(self, stage, reason, rs_rating, debug_mode=False, filter_name=""):
        """Construye y devuelve un diccionario MÍNIMO para una acción rechazada."""
        if debug_mode:
            print(f"    ❌ RECHAZADO [{filter_name}]: {reason}")

        # Devolvemos solo la información esencial para el resumen de filtrado.
        # No se calcula score ni se guardan datos detallados para optimizar.
        return {
            'passes_all_filters': False,
            'stage_analysis': stage,
            'filter_reasons': [reason],
            'rs_rating': rs_rating,
            'minervini_score': 0,
        }

    def _check_trend_and_mas(self, current_price, ma_50, ma_150, ma_200, df):
        """Filtro 1 y 2: Valida la tendencia de largo plazo y la jerarquía de las medias móviles."""
        if not all(pd.notna(x) for x in [current_price, ma_50, ma_150, ma_200]):
            return False, "Datos de MAs incompletos"

        if not (current_price > ma_150 and current_price > ma_200):
            return False, "Precio por debajo de MA150 o MA200"

        if not (ma_150 > ma_200):
            return False, "MA150 no está por encima de MA200"

        ma200_22_days_ago = df['MA_200'].iloc[-22] if len(df) > 22 else None
        if not (ma200_22_days_ago and pd.notna(ma200_22_days_ago) and ma_200 > ma200_22_days_ago):
            return False, "MA200 no tiene tendencia alcista ≥1 mes"

        # La condición Price > MA50 se elimina de este filtro inicial.
        # Esto permite que acciones en un pullback a la MA50 sean analizadas.
        # La lógica de `get_entry_signal` determinará si el rebote es válido.
        if not (ma_50 > ma_150 > ma_200):
            return False, "Jerarquía MAs incorrecta (MA50>MA150>MA200)"

        return True, ""

    def _check_52_week_range_position(self, current_price, high_52w, low_52w, rs_rating):
        """Filtro 3: Valida la posición del precio dentro del rango de 52 semanas."""
        if not all([current_price, high_52w, low_52w]):
            return False, "No se pudo calcular rango 52w", None, None

        distance_from_low = ((current_price - low_52w) / low_52w) * 100
        distance_from_high = ((high_52w - current_price) / high_52w) * 100

        price_above_low_threshold = distance_from_low >= self.MIN_PCT_ABOVE_LOW
        if not price_above_low_threshold:
            # Excepción para líderes de mercado fuertes
            is_strong_leader_candidate = distance_from_high < self.STRONG_LEADER_MAX_PCT_BELOW_HIGH
            is_high_rs = rs_rating is not None and rs_rating > self.STRONG_LEADER_MIN_RS
            if not (is_strong_leader_candidate and is_high_rs):
                return False, "Precio no está 30%+ sobre mínimo 52w", distance_from_low, distance_from_high

        price_near_high = distance_from_high <= self.MAX_PCT_BELOW_HIGH
        if not price_near_high:
            return False, "Precio no está dentro del 25% del máximo 52w", distance_from_low, distance_from_high

        return True, "", distance_from_low, distance_from_high

    def _check_price_volume_pattern(self, df, vcp_analysis, volume_50d_avg):
        """Filtro 5: Valida si existe un patrón de precio/volumen constructivo."""
        institutional_accumulation = self.detect_institutional_accumulation(df, volume_50d_avg) if volume_50d_avg else False
        pattern_score, _ = self.get_pattern_score(vcp_analysis, institutional_accumulation)
        
        if pattern_score < self.MIN_PATTERN_SCORE:
            return False, f"Patrón de precio/volumen insuficiente (Score: {pattern_score})", pattern_score, institutional_accumulation
        
        return True, "", pattern_score, institutional_accumulation

    def _check_fundamental_health(self, ticker_info):
        """Filtros 0, 6 y 7: Valida la salud fundamental (beneficios, crecimiento, ROE)."""
        if not ticker_info:
            return False, "Datos fundamentales no disponibles", False, False

        # Filtro 0: Beneficios positivos
        net_income = ticker_info.get('netIncomeToCommon')
        if net_income is not None and net_income <= 0: # Este es un filtro crítico
            return False, f"Beneficios negativos/nulos (${net_income/1_000_000:.1f}M)", False, False

        # Filtro 6: Crecimiento de beneficios
        earnings_growth = ticker_info.get('earningsQuarterlyGrowth')
        if earnings_growth is None:
            return False, "Dato de Earnings Growth no disponible", False, False
        if earnings_growth < self.MIN_EARNINGS_GROWTH:
            return False, f"Earnings growth < {self.MIN_EARNINGS_GROWTH:.0%} YoY", False, False
        
        earnings_acceleration = earnings_growth > 0.3

        # Filtro 7: Crecimiento de ingresos y ROE (Lógica Inteligente)
        roe = ticker_info.get('returnOnEquity')
        if not (roe is not None and roe >= self.MIN_ROE):
            return False, f"ROE < {self.MIN_ROE:.0%} o no disponible", earnings_acceleration, False
        
        has_strong_roe = True # Si llega aquí, el ROE es fuerte

        revenue_growth = ticker_info.get('revenueGrowth')

        # Escenario 1: Crecimiento clásico (buenos ingresos)
        if revenue_growth is not None and revenue_growth >= self.MIN_REVENUE_GROWTH:
            return True, "", earnings_acceleration, has_strong_roe

        # Escenario 2: "Central de productividad" (beneficios excepcionales compensan ingresos más bajos)
        if earnings_growth >= self.EXCEPTIONAL_EARNINGS_GROWTH and \
           revenue_growth is not None and revenue_growth >= self.DECENT_REVENUE_GROWTH:
            return True, "", earnings_acceleration, has_strong_roe
        
        # Si no cumple ninguno de los dos escenarios, falla.
        return False, "Crecimiento de ingresos/beneficios insuficiente", earnings_acceleration, has_strong_roe

    def _check_ma_bounce(self, df, current_price, ma_period, uptrend_days, touch_days, touch_proximity, bounce_limit):
        """
        Helper genérico para detectar un rebote en una media móvil específica.
        Devuelve True si se detecta un rebote válido, False en caso contrario.
        """
        ma_col = f'MA_{ma_period}'
        ma_series = df.get(ma_col)

        if ma_series is None or pd.isna(ma_series.iloc[-1]):
            return False

        ma_value = ma_series.iloc[-1]
        
        # 1. La MA debe estar en tendencia alcista
        is_uptrending = ma_value > ma_series.iloc[-uptrend_days] if len(df) > uptrend_days else False
        if not is_uptrending:
            return False

        # 2. El precio debe haber tocado (o estado muy cerca) de la MA recientemente
        # La lógica `low < ma * (1 + proximity)` significa que el mínimo del día estuvo por debajo o ligeramente por encima de la MA.
        touched_ma = (df['Low'].tail(touch_days) < ma_series.tail(touch_days) * (1 + touch_proximity)).any()
        if not touched_ma:
            return False
            
        # 3. El precio debe estar rebotando ahora, pero no demasiado extendido
        return current_price > ma_value and ((current_price - ma_value) / ma_value) < bounce_limit

    def get_minervini_analysis(self, df, rs_rating, symbol, cache_manager, session, debug_mode=False):
        """Análisis completo y optimizado con 'early exit' según metodología SEPA de Minervini"""
        try:
            # --- GUARDIA INICIAL: DATOS INSUFICIENTES ---
            if df.empty or len(df) < 252:
                return self._build_rejection_result(
                    stage='Insufficient Data',
                    reason='Datos insuficientes (<252 días)',
                    rs_rating=rs_rating,
                    debug_mode=debug_mode,
                    filter_name="Datos"
                ), False
            
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
            
            # --- ANÁLISIS DE PUNTO DE ENTRADA (SE CALCULA SIEMPRE PARA EL SCORE Y EL DASHBOARD) ---
            price_vs_ma10_pct = ((current_price - ma_10) / ma_10) * 100 if pd.notna(ma_10) else 999
            price_vs_ma21_pct = ((current_price - ma_21) / ma_21) * 100 if pd.notna(ma_21) else 999
            is_extended = price_vs_ma10_pct > 10 or price_vs_ma21_pct > 15 # Umbrales de extensión

            # FILTROS TÉCNICOS
            passed, reason = self._check_trend_and_mas(current_price, ma_50, ma_150, ma_200, df)
            if not passed: return self._build_rejection_result('Stage 1/3/4', reason, rs_rating, debug_mode, "Tendencia/MAs"), False

            passed, reason, dist_low, dist_high = self._check_52_week_range_position(current_price, high_52w, low_52w, rs_rating)
            if not passed: return self._build_rejection_result('Stage 2 (Developing)', reason, rs_rating, debug_mode, "Rango 52w"), False
            distance_from_low, distance_from_high = dist_low, dist_high # Guardar para el score final

            if not (rs_rating is not None and rs_rating >= self.MIN_RS_RATING):
                return self._build_rejection_result('Stage 2 (Developing)', f"RS Rating insuficiente (<{self.MIN_RS_RATING})", rs_rating, debug_mode, "RS Rating"), False

            # --- ANÁLISIS DE PATRONES (VCP) - Se calcula solo si pasa los filtros anteriores ---
            vcp_analysis = self.analyze_vcp_characteristics(df, high_52w, volume_50d_avg)

            passed, reason, pattern_score, institutional_accumulation = self._check_price_volume_pattern(df, vcp_analysis, volume_50d_avg)
            if not passed: return self._build_rejection_result('Stage 2 (Developing)', reason, rs_rating, debug_mode, "Patrón Precio/Volumen"), False

            # --- SI LLEGA AQUÍ, PASA TODOS LOS FILTROS TÉCNICOS ---
            if debug_mode: print("\n    --- ✅ PASA TODOS LOS FILTROS TÉCNICOS --- \n")
            passes_technical = True
            stage_analysis = "Stage 2 (Uptrend)"

            # --- OBTENER DATOS FUNDAMENTALES (SOLO SI PASA FILTROS TÉCNICOS) ---
            # Esta es una optimización clave: solo hacemos la llamada a la API/caché
            # para las acciones que ya son técnicamente prometedoras.
            ticker_info, had_to_retry = fetch_info_for_symbol(symbol, cache_manager, session=session)
            if not ticker_info or 'sector' not in ticker_info:
                return self._build_rejection_result(stage_analysis, "Datos fundamentales (.info) no disponibles", rs_rating, debug_mode, "Fundamentales"), had_to_retry

            # FILTRO 8: SALUD FUNDAMENTAL (CRECIMIENTO Y RENTABILIDAD)
            passed, reason, earnings_acceleration, roe_strong = self._check_fundamental_health(ticker_info)
            if not passed:
                return self._build_rejection_result(stage_analysis, reason, rs_rating, debug_mode, "Salud Fundamental"), had_to_retry

            # FILTRO 9: EVIDENCIA INSTITUCIONAL (HÍBRIDO)
            passes_institutional, institutional_score, institutional_details = self.hybrid_institutional_evidence(symbol, df, ticker_info, volume_50d_avg)
            if not passes_institutional:
                return self._build_rejection_result(stage_analysis, "Evidencia institucional insuficiente", rs_rating, debug_mode, "Evidencia Institucional"), had_to_retry

            if debug_mode: print("\n    --- ✅ PASA TODOS LOS FILTROS FUNDAMENTALES --- \n")

            # --- ¡ÉXITO! LA ACCIÓN PASA TODOS LOS FILTROS ---
            # Calcular la señal de entrada solo para las acciones que pasan todos los filtros
            entry_signal, is_actionable = self.get_entry_signal(df, vcp_analysis, is_extended)

            # CORRECCIÓN CLAVE: Asegurarse de que 'entry_signal' se incluye para el cálculo del score.
            analysis_for_scoring = {
                'stage_analysis': stage_analysis, 'rs_rating': rs_rating,
                'distance_to_52w_high': distance_from_high, 'distance_from_52w_low': distance_from_low,
                'pattern_score': pattern_score, 'vcp_detected': vcp_analysis['vcp_detected'],
                'institutional_evidence': passes_institutional, 'institutional_score': institutional_score,
                'earnings_acceleration': earnings_acceleration, 'roe_strong': roe_strong,
                'is_extended': is_extended, 'is_actionable_entry': is_actionable,
                'entry_signal': entry_signal
            }
            minervini_score = self.calculate_minervini_score(analysis_for_scoring)

            # Actualizar el diccionario de resultados con todos los datos de la acción exitosa
            result = {
                'current_price': round(current_price, 2),
                'stage_analysis': stage_analysis,
                'passes_all_filters': True,
                'minervini_score': minervini_score,
                'filter_reasons': ["✅ PASA TODOS LOS FILTROS MINERVINI"],
                'rs_rating': rs_rating,
                'passes_minervini_technical': passes_technical,
                'passes_minervini_fundamental': True,
                'ma_50': round(ma_50, 2) if pd.notna(ma_50) else None,
                'ma_150': round(ma_150, 2) if pd.notna(ma_150) else None,
                'ma_200': round(ma_200, 2) if pd.notna(ma_200) else None,
                'high_52w': round(high_52w, 2) if high_52w else None,
                'low_52w': round(low_52w, 2) if low_52w else None,
                'distance_from_52w_low': round(distance_from_low, 1) if distance_from_low else None,
                'distance_to_52w_high': round(distance_from_high, 1) if distance_from_high else None,
                'pattern_score': pattern_score,
                'vcp_detected': vcp_analysis['vcp_detected'],
                'entry_signal': entry_signal, 'is_extended': is_extended, 'is_actionable_entry': is_actionable,
                'vcp_analysis': vcp_analysis,
                'institutional_accumulation': institutional_accumulation,
                'institutional_evidence': passes_institutional, 'institutional_score': institutional_score,
                'institutional_details': institutional_details,
                'volume_50d_avg': int(volume_50d_avg) if volume_50d_avg else None,
                'earnings_acceleration': earnings_acceleration,
                'roe_strong': roe_strong,
                # Añadir información de la compañía para su uso posterior
                'company_name': ticker_info.get('longName', symbol),
                'sector': ticker_info.get('sector', 'N/A'),
                'industry': ticker_info.get('industry', 'N/A'),
                'market_cap': ticker_info.get('marketCap', 'N/A')
            }
            return result, had_to_retry
            
        except Exception as e:
            print(f"Error en análisis Minervini para {symbol}: {e}")
            return self._build_rejection_result('Error', f'Error de cálculo: {e}', rs_rating, debug_mode, "Error Interno"), False

    def get_entry_signal(self, df, vcp_analysis, is_extended):
        """
        Determina la mejor señal de entrada analizando múltiples patrones.
        Devuelve la señal (string) y si es un punto de entrada accionable (boolean).
        """
        # Prioridad 1: Pivote VCP (la señal de más bajo riesgo)
        if vcp_analysis.get('is_in_pivot', False):
            return "Pivot Point", True

        # Prioridad 1.5: VCP general detectado (setup en formación)
        if vcp_analysis.get('vcp_detected', False):
            return "VCP Setup", True

        # Prioridad 2 y 3: Rebote en medias móviles (50 y 21 días)
        # Itera sobre los parámetros definidos en __init__ para mayor claridad y mantenibilidad.
        # El orden en el diccionario (si Python >= 3.7) o la definición de la lista de prioridades
        # asegura que se compruebe primero la MA50.
        current_price = df['Close'].iloc[-1]
        for ma_period, params in self.BOUNCE_PARAMS.items():
            if self._check_ma_bounce(df, current_price, ma_period=ma_period, **params):
                return f"MA-Bounce-{ma_period}", True

        # Si no hay señal de entrada, determinar si está extendido o consolidando
        if is_extended:
            return "Extendido", False
        
        return "Consolidando", False
    
    def process_stocks_with_minervini(self, symbols, all_historical_data, rs_ratings, cache_manager):
        """Aplica análisis Minervini a datos pre-descargados. Solo descarga ticker.info (fundamentales)."""
        stock_data = {}
        failed_symbols = []
        info_retry_count = 0
        
        for i, symbol in enumerate(tqdm(symbols, desc="    Analizando símbolos del lote", unit="símbolo", leave=False, ncols=120), 1):
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # El historial ya está descargado, solo lo recuperamos del diccionario
                    hist = all_historical_data.get(symbol)
                    if hist is None or hist.empty:
                        raise ValueError("Datos históricos no encontrados en el diccionario pre-cargado.")
                    
                    if len(hist) >= 250:  # Mínimo para análisis Minervini
                        hist_with_ma = self.calculate_moving_averages(hist)
                        
                        stock_rs_rating = rs_ratings.get(symbol)
                        # La obtención de .info se ha movido DENTRO de get_minervini_analysis
                        # para que solo se ejecute en acciones que pasan los filtros técnicos.
                        minervini_analysis, had_info_retry = self.get_minervini_analysis(
                            hist_with_ma, stock_rs_rating, symbol, cache_manager, self.session, debug_mode=False
                        )

                        if had_info_retry:
                            info_retry_count += 1

                        # Siempre se procesa el resultado, ya que incluso las acciones rechazadas se guardan en el informe.

                        stock_data[symbol] = {
                            'data': hist_with_ma,
                            'minervini_analysis': minervini_analysis,
                            # La información de la compañía ahora se extrae del análisis si pasa los filtros
                            'info': { # Simplificado: los datos ahora vienen directamente del análisis
                                'name': minervini_analysis.get('company_name', symbol), # Fallback a symbol
                                'sector': minervini_analysis.get('sector', 'N/A'),
                                'industry': minervini_analysis.get('industry', 'N/A'),
                                'market_cap': minervini_analysis.get('market_cap', 'N/A')
                            } 
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
                        # No se añade a failed_symbols porque es un descarte esperado, no un error.
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
                
                # Se elimina la pausa de 0.5s por símbolo. La gestión de rate limits ya se hace
                # con backoff exponencial en las llamadas a la API, haciendo esta pausa redundante y muy lenta.
                    
        return stock_data, failed_symbols, info_retry_count

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
        
        for i in tqdm(range(total_batches), desc="Descargando datos históricos", unit="lote"):
            start_idx = i * batch_size
            end_idx = min(start_idx + batch_size, len(symbols))
            batch_symbols = symbols[start_idx:end_idx]
            
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    batch_data = yf.download(batch_symbols, period=period, group_by='ticker', auto_adjust=True, threads=True, progress=False, timeout=30)
                    
                    for symbol in batch_symbols:
                        if symbol in batch_data.columns:
                            # Asegurarse de que el df no está vacío y tiene datos válidos
                            df = batch_data[symbol].dropna()
                            if not df.empty:
                                all_data[symbol] = df
                    success = True
                    
                except Exception as e:
                    retry_count += 1
                    # Backoff más conservador para la descarga masiva: 10s, 20s, 40s
                    wait_time = 10 * (2 ** (retry_count - 1))
                    print(f"  ⚠️ Error en lote {i+1}: {e}. Reintentando en {wait_time}s... ({retry_count}/{max_retries})")
                    time.sleep(wait_time)
            
            if not success:
                print(f"  ❌ Lote {i+1} falló después de {max_retries} reintentos. Omitiendo este lote.")
            
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

class TickerInfoCacheManager:
    """
    Gestiona un caché de datos de tickers en un único archivo JSON para evitar
    crear miles de archivos en el repositorio.
    """
    def __init__(self, cache_path="ticker_info_cache/ticker_cache.json", ttl_hours=168):
        self.cache_path = cache_path
        self.ttl_seconds = ttl_hours * 3600
        self.cache_data = self._load_cache()
        self.updated = False

    def _load_cache(self):
        """Carga el archivo de caché JSON si existe."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    print(f"✓ Caché de .info cargado desde {self.cache_path}")
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️ No se pudo cargar el caché de .info, se creará uno nuevo. Error: {e}")
                return {}
        print("ℹ️ No se encontró caché de .info, se creará uno nuevo.")
        return {}

    def get(self, symbol):
        """Obtiene datos del caché si no están obsoletos."""
        entry = self.cache_data.get(symbol)
        if not entry:
            return None

        # 1. Validación por tiempo (TTL)
        if (time.time() - entry.get('timestamp', 0)) >= self.ttl_seconds:
            return None # Expirado por tiempo

        # 2. Validación por fecha de beneficios (la nueva lógica inteligente)
        earnings_date_str = entry.get('earnings_date')
        if earnings_date_str:
            try:
                # Compara la fecha de hoy con la fecha de beneficios guardada.
                # Si hoy es igual o posterior a la fecha de beneficios, el caché está obsoleto.
                today_str = datetime.now().strftime('%Y-%m-%d')
                if today_str >= earnings_date_str:
                    print(f"  - ℹ️ Invalidando caché para {symbol} por fecha de beneficios pasada ({earnings_date_str}).")
                    return None # Expirado por evento de beneficios
            except Exception:
                pass # Si hay error en la fecha, se ignora y se confía en el TTL

        return entry.get('data')

    def get_stale(self, symbol):
        """Obtiene datos del caché, incluso si están obsoletos (para fallback)."""
        if symbol in self.cache_data:
            return self.cache_data[symbol].get('data')
        return None

    def set(self, symbol, data, calendar_data=None):
        """Actualiza el caché en memoria para un símbolo."""
        self.cache_data[symbol] = {
            'timestamp': time.time(),
            'data': data,
            'earnings_date': self._extract_earnings_date(calendar_data)
        }
        self.updated = True

    def save_cache_if_updated(self):
        """Guarda el caché en disco solo si ha habido cambios."""
        if self.updated:
            print(f"\n💾 Guardando caché de .info actualizado en {self.cache_path}...")
            cache_dir = os.path.dirname(self.cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache_data, f)
            print("✓ Caché guardado.")
        else:
            print("\nℹ️ No hubo actualizaciones en el caché de .info, no se guarda nada.")

    def _extract_earnings_date(self, calendar_data):
        """Extrae y formatea la próxima fecha de beneficios del diccionario de calendario."""
        if not calendar_data or 'Earnings Date' not in calendar_data:
            return None
        
        try:
            # La fecha puede venir como una lista de datetimes
            earnings_date = calendar_data['Earnings Date'][0]
            return earnings_date.strftime('%Y-%m-%d')
        except (TypeError, IndexError, AttributeError):
            # Si el formato es inesperado, devuelve None
            return None

def fetch_info_for_symbol(symbol, cache_manager, session=None, max_retries=3):
    """
    Obtiene .info de yfinance de forma robusta, con reintentos y fallback a caché.
    Devuelve (info, tuvo_reintentos).
    """
    # 1. Intentar obtener datos frescos del caché (TTL de varias horas)
    cached_info = cache_manager.get(symbol)
    if cached_info:
        return cached_info, False # No hubo reintentos

    # 2. Si no hay caché fresco, intentar llamada a la API con reintentos
    for attempt in range(max_retries):
        try:
            # Usar la sesión compartida para robustez. El timeout se gestiona a nivel de la sesión.
            ticker = yf.Ticker(symbol, session=session)
            ticker_info = ticker.info  # Obtiene los datos fundamentales
            
            try:
                calendar_data = ticker.calendar # Obtiene la fecha de beneficios
            except Exception:
                # Si falla la obtención del calendario, continuamos sin él.
                # El caché no tendrá fecha de beneficios y se basará solo en el TTL.
                calendar_data = None
            
            if ticker_info and 'symbol' in ticker_info:
                cache_manager.set(symbol, ticker_info, calendar_data)
                # Si tuvo éxito pero no en el primer intento, fue un reintento exitoso.
                return ticker_info, attempt > 0
            else:
                raise ValueError("API devolvió .info vacío o inválido.")

        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit_error = (
                "rate" in error_msg or 
                "429" in error_msg or 
                "too many requests" in error_msg or
                "401" in error_msg # yfinance a veces usa 401 para bloqueos temporales
            )

            # Reintentar SOLO si es un error de rate limit y aún quedan intentos.
            if is_rate_limit_error and attempt < max_retries - 1:
                wait_time = 5 * (2 ** attempt) # Exponential backoff: 5s, 10s
                print(f"  - ⏳ Rate limit detectado para {symbol}. Pausa de {wait_time}s... (Intento {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                # Si es otro tipo de error (ej. datos no existen) o se agotaron los reintentos,
                # no tiene sentido seguir. Salimos del bucle de reintentos inmediatamente.
                break

    # 3. Después de todos los reintentos, usar caché obsoleto como último recurso
    stale_info = cache_manager.get_stale(symbol)
    if not stale_info:
        # Solo loguear si ni siquiera hay caché obsoleto, es un fallo total.
        # Este es un evento raro y digno de ser logueado.
        print(f"  - ❌ API falló para {symbol} tras {max_retries} intentos y sin caché de fallback.")
    
    return stale_info if stale_info else {}, True  # Tuvo que reintentar (y falló)

def _run_analysis_pipeline(screener, cache_manager):
    """
    Ejecuta el pipeline completo de análisis: obtención de símbolos, descarga de datos,
    cálculo de RS y procesamiento Minervini.
    """
    print("Obteniendo símbolos NYSE + NASDAQ...")
    all_symbols = screener.get_nyse_nasdaq_symbols()
    original_count = len(all_symbols)

    # Filtro final para eliminar tickers con caracteres especiales que puedan causar problemas
    all_symbols = [s for s in all_symbols if '^' not in s and '.' not in s and '/' not in s]
    print(f"✓ Símbolos filtrados (eliminados preferentes/warrants): {original_count - len(all_symbols)} eliminados")
    print(f"Total de acciones a analizar: {len(all_symbols)}")

    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        return None, None

    # PASO 1: Descarga masiva de datos
    symbols_to_process = all_symbols
    all_historical_data = screener.download_all_data(symbols_to_process)

    # PASO 2: Calcular scores de rendimiento
    rs_scores = screener.calculate_all_rs_scores(all_historical_data)

    # PASO 3: Calcular RS Ratings finales (percentiles)
    rs_ratings = screener.calculate_rs_ratings_from_scores(rs_scores)

    # PASO 4: Análisis Minervini completo usando los RS Ratings pre-calculados
    batch_size = 30
    print(f"\nIniciando análisis de {len(symbols_to_process)} acciones con criterios Minervini SEPA...")
    print("Usando RS Ratings pre-calculados para mayor precisión.\n")

    total_batches = (len(symbols_to_process) + batch_size - 1) // batch_size
    all_stock_data = {}
    all_failed = []

    for batch_num in range(total_batches):
        print(f"\n--- Procesando Lote {batch_num + 1}/{total_batches} ---")
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(symbols_to_process))
        batch_symbols = symbols_to_process[start_idx:end_idx]

        batch_data, batch_failed, batch_retries = screener.process_stocks_with_minervini(batch_symbols, all_historical_data, rs_ratings, cache_manager)

        all_stock_data.update(batch_data)
        all_failed.extend(batch_failed)

        batch_passed = sum(1 for data in batch_data.values() if data['minervini_analysis']['passes_all_filters'])
        batch_filtered = len(batch_data) - batch_passed
        avg_score = np.mean([data['minervini_analysis']['minervini_score'] for data in batch_data.values()]) if batch_data else 0

        summary_str = f"Lote completado: {batch_passed} Stage 2 | {batch_filtered} Filtradas | Score Promedio: {avg_score:.1f}"
        problems = [f"{len(batch_failed)} Errores"] if batch_failed else []
        if batch_retries > 0: problems.append(f"{batch_retries} Reintentos API")
        if problems: summary_str += f" | ({', '.join(problems)})"
        print(summary_str)

        if batch_num < total_batches - 1:
            pause_duration = 2
            print(f"Pausa {pause_duration}s...")
            time.sleep(pause_duration)

    return all_stock_data, all_failed

def _generate_final_report(screener, all_stock_data, all_failed):
    """Genera y muestra el reporte final con los resultados del análisis."""
    print(f"\n=== RESUMEN FINAL MINERVINI ===")
    print(f"Procesadas: {len(all_stock_data)} | Errores: {len(all_failed)}")

    all_summary, stage2_summary = screener.save_minervini_data(all_stock_data)
    stage2_count = len(stage2_summary) if not stage2_summary.empty else 0
    success_rate = (stage2_count / len(all_stock_data)) * 100 if len(all_stock_data) > 0 else 0

    print(f"Acciones Stage 2 (pasan todos los filtros): {stage2_count}")
    print(f"Tasa de éxito Minervini: {success_rate:.1f}%")

    if not stage2_summary.empty:
        top_10 = stage2_summary.nlargest(10, 'Minervini_Score')
        print(f"\n🔝 TOP 10 ACCIONES (ordenadas por Minervini Score):")
        for i, (_, row) in enumerate(top_10.iterrows()):
            print(f"{i+1:2d}. {row['Symbol']:6s} | Score:{row['Minervini_Score']:5.1f} | RS:{row['RS_Rating']:5.1f} | Precio:${row['Current_Price']:7.2f} | Señal: {row['Entry_Signal']}")

        # NUEVO: Resumen de los tipos de señales de entrada encontradas
        print(f"\n=== TIPOS DE SEÑALES DE ENTRADA (STAGE 2) ===")
        signal_distribution = stage2_summary['Entry_Signal'].value_counts()
        for signal, count in signal_distribution.items():
            percentage = (count / stage2_count) * 100
            print(f"  {signal}: {count} acciones ({percentage:.1f}%)")

    stage_distribution = all_summary['Stage_Analysis'].value_counts()
    print(f"\n=== DISTRIBUCIÓN POR STAGE ===")
    for stage, count in stage_distribution.items():
        percentage = (count / len(all_summary)) * 100
        avg_score = all_summary[all_summary['Stage_Analysis'] == stage]['Minervini_Score'].mean()
        print(f"  {stage}: {count} acciones ({percentage:.1f}%) - Score promedio: {avg_score:.1f}")

    print(f"\n=== RAZONES DE ELIMINACIÓN (TOP 10) ===")
    reasons = all_summary[~all_summary['Passes_All_Filters']]['Filter_Reasons'].str.split(';').explode().str.strip()
    top_reasons = reasons[reasons.ne('') & reasons.ne('nan')].value_counts().nlargest(10)
    for reason, count in top_reasons.items():
        percentage = (count / len(all_summary)) * 100
        print(f"  {reason}: {count} acciones ({percentage:.1f}%)")

def main():
    """Función principal para GitHub Actions - Análisis Minervini SEPA completo"""
    print("=== MINERVINI SEPA AUTOMATED SCREENER ===")
    print("Sistema basado en metodología SEPA de Mark Minervini")
    print("11 filtros: 8 técnicos + 3 fundamentales + Scoring System\n")
    
    screener = MinerviniStockScreener() # La sesión de red se crea aquí
    cache_manager = TickerInfoCacheManager()
    
    # Ejecutar el pipeline de análisis
    all_stock_data, all_failed = _run_analysis_pipeline(screener, cache_manager)

    # Generar el reporte final si el pipeline tuvo éxito
    if all_stock_data:
        _generate_final_report(screener, all_stock_data, all_failed)
        # Guardar el caché al final de todo el proceso
        cache_manager.save_cache_if_updated()
    else:
        print("❌ No se obtuvieron datos")
        exit(1)

if __name__ == "__main__":
    main()