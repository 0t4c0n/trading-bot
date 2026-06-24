import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
from tqdm import tqdm


class WyckoffSpringScreener:
    def __init__(self):
        self.stock_symbols = []
        # Parámetros Wyckoff Spring (Swing Trading Macro — Gráfico Diario)
        self.VOL_LOOKBACK = 252       # 1 año para Volume Profile (VPVR)
        self.SUPPORT_LOOKBACK = 150   # ~7 meses de historia para soporte estructural S1.
                                       # 150 (no 130) porque, anclado al shakeout, la ventana
                                       # [shakeout−150, shakeout−5] debe alcanzar soportes que se
                                       # formaron ~6-7 meses antes (p.ej. AAPL: mínimo de jun-2022
                                       # perforado por el Spring de ene-2023, a ~135 días).
        self.S1_ANCHOR_BUFFER = 5     # Días previos al shakeout que se excluyen del cálculo de S1
                                       # (evita que la caída inmediata hacia el shakeout contamine
                                       # el soporte, y evita la paradoja spring_low == S1).
        self.PIVOT_WIDTH = 5          # Un swing-low es el mínimo en ±PIVOT_WIDTH velas (significancia).
        self.SUPPORT_CLUSTER_TOL = 0.02  # Swing-lows a <2% se agrupan en un mismo nivel de soporte.
        self.MIN_SPRING_DEPTH_PCT = 1.0  # El shakeout debe perforar el soporte ≥1% para ser un
                                          # shakeout real (no un mero toque/test del soporte).
        self.SPRING_SEARCH_WINDOW = 60  # Últimos 60 días donde buscar el Spring
                                        # (S1 debe estar establecido ANTES de la ventana de Spring)
        self.FILTER_VOLUMEN = 1.3     # Multiplicador SMA(20) para validar el shakeout del Spring.
                                       # 1.3× (no 1.5×) porque la SMA20 ya está elevada durante el
                                       # descenso previo; el clímax de venta real ronda 1.3-1.5×.
        self.SPRING_RECOVERY_WINDOW = 10  # Días máx. tras el shakeout para que una vela cierre
                                           # de nuevo POR ENCIMA de S1 y confirme el Spring.
        self.ATR_PERIOD = 14          # Período ATR para Stop Loss
        self.VP_BINS = 100            # Bins del Volume Profile
        self.HVN_THRESHOLD = 1.5      # Multiplicador sobre media para HVN
        self.S1_CONFLUENCE_TOLERANCE = 0.015  # 1.5% tolerancia S1 cerca de POC/HVN
                                               # (gradiente de score interno preserva calidad)
        self.TEST_TOLERANCE = 0.02    # Banda (2%) por encima de S1 que el Test puede alcanzar.
                                       # El retroceso de Test rara vez toca S1 exacto; basta con que
                                       # regrese a la zona del soporte manteniéndose sobre el Spring Low.
        self.SPRING_MAX_AGE_WITHOUT_TEST = 30  # Días máx. desde Spring sin Test antes de caducar
        self.MIN_PRICE = 5.0          # Excluir penny stocks (<$5): spreads enormes,
                                       # alta manipulación, ruido y riesgo desproporcionado
        # === FILTRO ESTRICTO DE OPERABILIDAD ===
        # Solo entradas REALMENTE operables hoy aparecen en top picks.
        # Springs sin Test y entradas pasadas → watchlist (no operables).
        self.ACTIONABLE_TEST_MAX_AGE = 5         # Días máx. desde Test para entrada vigente
        self.ACTIONABLE_PRICE_MAX_ABOVE_S1 = 0.02 # 2% máx. sobre S1 para entrada vigente
        # Gate de CALIDAD para operabilidad (separa springs reales de rebotes cualquiera).
        # Validado AAPL-safe: AAPL tuvo base=115d y depth=3.48% (pasa con holgura). NO se puede
        # filtrar por OBV>0 ni vol≥1.5× ni touches≥2: AAPL falla esos (OBV −0.05, vol 1.36, 1 toque).
        self.ACTIONABLE_MIN_BASE_WIDTH = 60      # Wyckoff "cause": días de base requeridos
        self.ACTIONABLE_MIN_DEPTH_PCT = 1.5      # Profundidad mín. del shakeout para operar
        # === RANKING POR RIESGO ===
        # El Top 10 se ordena por Rank_Score = Wyckoff_Score + bonus por riesgo bajo.
        # El bonus premia un SL cercano al precio actual (menor % de pérdida si se opera hoy).
        self.RISK_BONUS_POINTS = 20.0   # Bonus máx. (SL pegado al precio: riesgo ~0%)
        self.RISK_BONUS_MAX_PCT = 8.0   # A partir de este % (precio→SL) el bonus es 0
        self.MIN_DATA_POINTS = 260    # Mínimo de velas diarias requeridas
        self.symbol_industries = {}
        self.session = requests.Session()

    # =================== OBTENCIÓN DE SÍMBOLOS ===================

    def get_nyse_nasdaq_symbols(self):
        """Obtiene símbolos de NYSE y NASDAQ combinados."""
        try:
            nyse_symbols = self.get_exchange_symbols('NYSE')
            nasdaq_symbols = self.get_exchange_symbols('NASDAQ')
            return list(set(nyse_symbols + nasdaq_symbols))
        except Exception as e:
            print(f"Error obteniendo símbolos: {e}")
            backup = self.get_backup_symbols()
            print(f"Usando lista de respaldo: {len(backup)} símbolos")
            return backup

    def get_exchange_symbols(self, exchange):
        """Obtiene símbolos de NYSE o NASDAQ desde la API de NASDAQ."""
        try:
            url = "https://api.nasdaq.com/api/screener/stocks"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            params = {'tableonly': 'true', 'limit': '25000', 'exchange': exchange}
            response = self.session.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'table' in data['data']:
                    rows = data['data']['table']['rows']
                    symbols = []
                    for row in rows:
                        sym = row['symbol']
                        symbols.append(sym)
                        self.symbol_industries[sym] = {
                            'name': row.get('name', '') or '',
                            'industry': row.get('industry', 'Unknown') or 'Unknown',
                            'sector': row.get('sector', 'Unknown') or 'Unknown',
                        }
                    print(f"  Obtenidos {len(symbols)} símbolos de {exchange}.")
                    return symbols
            return []
        except Exception as e:
            print(f"Error obteniendo símbolos de {exchange}: {e}")
            return []

    def get_backup_symbols(self):
        """Lista de respaldo con principales acciones de NYSE y NASDAQ."""
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
            'T', 'VZ', 'CMCSA', 'CHTR', 'TMUS', 'S',
        ]
        nasdaq_major = [
            'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'TSLA', 'META', 'NFLX',
            'NVDA', 'ADBE', 'PYPL', 'INTC', 'CSCO', 'AVGO', 'TXN', 'QCOM',
            'INTU', 'ISRG', 'FISV', 'ADP', 'BIIB', 'ILMN', 'MRNA', 'ZM', 'DOCU',
            'SNOW', 'PLTR', 'RBLX', 'U', 'TWLO', 'OKTA', 'DDOG', 'CRWD',
            'GILD', 'REGN', 'VRTX', 'BMRN', 'AMGN',
            'BKNG', 'EBAY', 'SBUX', 'ROST', 'ULTA', 'LULU', 'NTES', 'JD',
            'BABA', 'PDD', 'MELI', 'SE', 'SHOP', 'SQ', 'ROKU', 'SPOT',
            'AMD', 'ADI', 'KLAC', 'LRCX', 'AMAT', 'MU', 'MRVL', 'SWKS',
            'MCHP', 'NXPI', 'TSM', 'UBER', 'LYFT', 'DASH', 'ABNB',
            'TDOC', 'PTON', 'PINS', 'SNAP',
        ]
        return list(set(nyse_major + nasdaq_major))

    # =================== DESCARGA DE DATOS ===================

    def download_all_data(self, symbols):
        """
        Descarga datos históricos en lotes con reintentos y backoff.
        Ventana: 15 meses naturales (~327 días de trading), buffer de 67 días
        sobre el mínimo requerido (MIN_DATA_POINTS=260). ~35% menos datos
        descargados que con period='2y' sin sacrificar análisis.
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=465)  # ~15.3 meses naturales

        print(f"Iniciando descarga robusta para {len(symbols)} símbolos...")
        print(f"  Ventana: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')} (~15 meses)")
        all_data = {}
        batch_size = 75
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for i in tqdm(range(total_batches), desc="Descargando datos históricos", unit="lote"):
            start_idx = i * batch_size
            batch_symbols = symbols[start_idx:start_idx + batch_size]
            success = False

            for attempt in range(3):
                try:
                    batch_data = yf.download(
                        batch_symbols, start=start_date, end=end_date, group_by='ticker',
                        auto_adjust=True, threads=True, progress=False, timeout=30
                    )
                    for symbol in batch_symbols:
                        if symbol in batch_data.columns:
                            df = batch_data[symbol].dropna()
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = df.columns.droplevel(-1)
                            if not df.empty:
                                # Solo conservar columnas usadas (Open no se usa nunca)
                                # → −20% memoria por acción
                                df = df[[c for c in ['High', 'Low', 'Close', 'Volume']
                                         if c in df.columns]]
                                all_data[symbol] = df
                    success = True
                    break
                except Exception as e:
                    wait_time = 10 * (2 ** attempt)
                    print(f"  ⚠️ Error lote {i+1}: {e}. Reintentando en {wait_time}s...")
                    time.sleep(wait_time)

            if not success:
                print(f"  ❌ Lote {i+1} falló después de 3 intentos.")

        print(f"\n✓ Descarga de acciones completada: {len(all_data)} símbolos.")

        # Descargar S&P 500 como referencia de mercado y para RS
        print("Descargando índice de referencia (^GSPC)...")
        try:
            spy_data = yf.download(
                '^GSPC', start=start_date, end=end_date,
                auto_adjust=True, progress=False, timeout=30
            )
            if not spy_data.empty:
                if isinstance(spy_data.columns, pd.MultiIndex):
                    spy_data.columns = spy_data.columns.droplevel(-1)
                # check_market_health solo usa Close → resto descartado
                spy_data = spy_data[[c for c in ['Close'] if c in spy_data.columns]]
                all_data['_MARKET_INDEX'] = spy_data
                print("✓ ^GSPC descargado correctamente.")
        except Exception as e:
            print(f"⚠️ Error descargando ^GSPC: {e}")

        return all_data

    # =================== RS RATING ===================

    def calculate_all_rs_scores(self, all_data):
        """Calcula score de rendimiento relativo para todas las acciones (fórmula IBD)."""
        print("\nCalculando RS scores...")
        rs_scores = {}
        for symbol, df in all_data.items():
            if symbol == '_MARKET_INDEX':
                continue
            try:
                if len(df) < 252:
                    continue
                c = df['Close']
                p3   = ((c.iloc[-1] / c.iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
                p_q2 = ((c.iloc[-63] / c.iloc[-126]) - 1) * 100 if len(df) >= 126 else 0
                p_q3 = ((c.iloc[-126] / c.iloc[-189]) - 1) * 100 if len(df) >= 189 else 0
                p_q4 = ((c.iloc[-189] / c.iloc[-252]) - 1) * 100
                rs_scores[symbol] = 0.4 * p3 + 0.2 * p_q2 + 0.2 * p_q3 + 0.2 * p_q4
            except Exception:
                continue
        print(f"✓ RS scores calculados: {len(rs_scores)} acciones.")
        return pd.Series(rs_scores)

    def calculate_rs_ratings_from_scores(self, rs_scores):
        """Convierte scores en percentiles 0-100."""
        if rs_scores.empty:
            return pd.Series()
        rs_ratings = rs_scores.rank(pct=True) * 100
        print(f"✓ RS Ratings (percentiles) calculados.")
        return rs_ratings.round(1)

    def rank_industries_by_rs(self, rs_ratings):
        """Agrupa por industria y calcula percentil de RS mediana."""
        try:
            industry_rs = {}
            for symbol, score in rs_ratings.items():
                industry = self.symbol_industries.get(symbol, {}).get('industry', 'Unknown')
                industry_rs.setdefault(industry, []).append(score)
            industry_medians = {
                ind: pd.Series(scores).median()
                for ind, scores in industry_rs.items()
                if len(scores) >= 3
            }
            if not industry_medians:
                return {}
            return (pd.Series(industry_medians).rank(pct=True) * 100).round(1).to_dict()
        except Exception as e:
            print(f"Error en rank_industries_by_rs: {e}")
            return {}

    # =================== FILTRO DE MERCADO ===================

    def check_market_health(self, spy_df):
        """
        Evalúa si el mercado está en tendencia alcista (SPY sobre MA200).
        Devuelve (is_healthy: bool, health_score: 0-15 pts).
        Un mercado bajo MA200 es bajista — los Springs son mucho menos fiables.
        """
        if spy_df is None or len(spy_df) < 200:
            return True, 7.5  # Sin datos: asumir neutral

        close = spy_df['Close'].astype(float)
        ma200 = close.rolling(200).mean()
        ma50  = close.rolling(50).mean()

        current  = float(close.iloc[-1])
        ma200_v  = float(ma200.iloc[-1])
        ma50_v   = float(ma50.iloc[-1]) if pd.notna(ma50.iloc[-1]) else current

        if current > ma200_v:
            pct_above = (current - ma200_v) / ma200_v * 100
            # Bonus si además MA50 > MA200 (mercado fuerte)
            ma_aligned = ma50_v > ma200_v
            score = min(15.0, 8.0 + pct_above * 0.5 + (3.0 if ma_aligned else 0.0))
            return True, round(score, 1)
        else:
            # Mercado bajista: score reducido pero no cero (mercados laterales existen)
            pct_below = (ma200_v - current) / ma200_v * 100
            score = max(0.0, 4.0 - pct_below * 0.4)
            return False, round(score, 1)

    # =================== VOLUME PROFILE (VPVR) ===================

    def calculate_volume_profile(self, df):
        """
        Calcula POC y HVN del Volume Profile sobre VOL_LOOKBACK días.
        Distribuye el volumen de cada vela proporcionalmente entre los bins
        que cubre su rango High-Low.
        """
        try:
            data = df.tail(self.VOL_LOOKBACK)
            if len(data) < 50:
                return None, []

            lows    = data['Low'].values.astype(float)
            highs   = data['High'].values.astype(float)
            volumes = data['Volume'].values.astype(float)

            price_min = lows.min()
            price_max = highs.max()
            if price_max <= price_min:
                return None, []

            n_bins = self.VP_BINS
            price_range = price_max - price_min
            volume_by_price = np.zeros(n_bins)
            bins = np.linspace(price_min, price_max, n_bins + 1)

            for i in range(len(lows)):
                low_bin  = int((lows[i]  - price_min) / price_range * n_bins)
                high_bin = int((highs[i] - price_min) / price_range * n_bins)
                low_bin  = max(0, min(low_bin,  n_bins - 1))
                high_bin = max(0, min(high_bin, n_bins - 1))
                n_covered = high_bin - low_bin + 1
                if n_covered > 0:
                    volume_by_price[low_bin:high_bin + 1] += volumes[i] / n_covered

            poc_bin   = int(np.argmax(volume_by_price))
            poc_price = float((bins[poc_bin] + bins[poc_bin + 1]) / 2)

            active = volume_by_price[volume_by_price > 0]
            if len(active) == 0:
                return poc_price, []

            hvn_threshold = active.mean() * self.HVN_THRESHOLD
            bin_centers   = (bins[:-1] + bins[1:]) / 2
            hvn_prices    = bin_centers[volume_by_price >= hvn_threshold].tolist()

            return poc_price, [float(h) for h in hvn_prices]
        except Exception:
            return None, []

    # =================== SOPORTE ESTRUCTURAL S1 ===================

    def find_support_clusters(self, df, end_idx):
        """
        Detecta NIVELES de soporte por swing-lows (pivotes) en la ventana previa al shakeout
        [end_idx − SUPPORT_LOOKBACK, end_idx − S1_ANCHOR_BUFFER], y los agrupa en clusters.

        Un swing-low es una vela cuyo Low es el mínimo en ±PIVOT_WIDTH velas (mínimo local
        significativo). Los pivotes a <SUPPORT_CLUSTER_TOL entre sí se fusionan en un nivel;
        el 'floor' del cluster es el más bajo y 'touches' cuántas veces se testeó.

        Esto reemplaza el "mínimo absoluto de la ventana": permite que el Spring perfore el
        soporte del RANGO RECIENTE (p.ej. AMD $135) en vez del mínimo histórico profundo
        (AMD $93) que el precio ni siquiera tocó. Devuelve clusters ASCENDENTES por floor.
        """
        start = max(0, end_idx - self.SUPPORT_LOOKBACK)
        end = max(0, end_idx - self.S1_ANCHOR_BUFFER)
        p = self.PIVOT_WIDTH
        if end - start < (2 * p + 1):
            return []

        lows = df['Low'].values[start:end].astype(float)
        n = len(lows)
        pivot_prices = []
        for j in range(p, n - p):
            if lows[j] == lows[j - p:j + p + 1].min():
                pivot_prices.append(float(lows[j]))

        if not pivot_prices:
            return []

        pivot_prices.sort()
        tol = self.SUPPORT_CLUSTER_TOL
        clusters = []
        for pr in pivot_prices:
            if clusters and (pr - clusters[-1]['floor']) / clusters[-1]['floor'] <= tol:
                clusters[-1]['touches'] += 1  # floor ya es el menor (lista ordenada asc.)
            else:
                clusters.append({'floor': pr, 'touches': 1})
        return clusters  # ascendentes por floor

    def find_structural_support(self, df, anchor_idx=None):
        """
        S1 = mínimo del soporte estructural previo. Crítico para Wyckoff: el Spring debe
        perforar un soporte ESTABLECIDO ANTES de él. Si S1 incluyera la propia vela del
        Spring, sería imposible que spring_low < S1 (paradoja matemática).

        Dos modos:
          - ANCLADO (anchor_idx = índice de un Spring candidato): S1 = mínimo Low en
            [anchor_idx − SUPPORT_LOOKBACK, anchor_idx − S1_ANCHOR_BUFFER]. El soporte es el
            del rango previo a ESE Spring, así se capturan bases recientes (las que la ventana
            fija respecto a 'hoy' dejaba ciegas). Es el modo usado en el pipeline real.
          - VISTA ACTUAL (anchor_idx=None): ventana fija respecto al final del dataframe
            [-(SUPPORT_LOOKBACK+SPRING_SEARCH_WINDOW), -SPRING_SEARCH_WINDOW]. Solo para
            reportar un S1 orientativo cuando NO se detecta Spring.
        """
        if anchor_idx is not None:
            start = max(0, anchor_idx - self.SUPPORT_LOOKBACK)
            end = max(0, anchor_idx - self.S1_ANCHOR_BUFFER)
            s1_window = df.iloc[start:end]
            if s1_window.empty:
                fallback = df.iloc[:anchor_idx] if anchor_idx > 0 else df
                return float(fallback['Low'].min())
            return float(s1_window['Low'].min())

        window_end = self.SPRING_SEARCH_WINDOW
        window_start = self.SPRING_SEARCH_WINDOW + self.SUPPORT_LOOKBACK
        if len(df) <= window_start:
            # Datos insuficientes para separar las ventanas: usar todo lo disponible
            # excepto los últimos SPRING_SEARCH_WINDOW días
            s1_window = df.iloc[:-window_end] if len(df) > window_end else df
        else:
            s1_window = df.iloc[-window_start:-window_end]
        if s1_window.empty:
            return float(df['Low'].min())
        return float(s1_window['Low'].min())

    # =================== CONFLUENCIA S1 ↔ VP (gradual) ===================

    def check_s1_confluence(self, s1, poc, hvn_list):
        """
        Valida que S1 esté dentro del 1.5% de un HVN o del POC.
        Gradiente de calidad (a más cerca, más puntos):
          POC 0-0.5%: 30 pts  | 0.5-1.0%: 22 pts  | 1.0-1.5%: 14 pts
          HVN 0-0.5%: 25 pts  | 0.5-1.0%: 18 pts  | 1.0-1.5%: 10 pts
        Devuelve (válido, score 0-30, nivel más cercano).
        """
        tol = self.S1_CONFLUENCE_TOLERANCE

        def _graded_score(dist_pct, max_pts, mid_pts, min_pts):
            """Asigna puntos por banda: <0.33×tol, 0.33-0.66×tol, 0.66-1.0×tol."""
            if dist_pct <= tol / 3:
                return max_pts
            elif dist_pct <= tol * 2 / 3:
                return mid_pts
            else:
                return min_pts

        if poc is not None and poc > 0:
            dist = abs(s1 - poc) / poc
            if dist <= tol:
                return True, _graded_score(dist, 30.0, 22.0, 14.0), poc

        best_hvn, best_dist = None, float('inf')
        for hvn in hvn_list:
            if hvn > 0:
                dist = abs(s1 - hvn) / hvn
                if dist < best_dist:
                    best_dist, best_hvn = dist, hvn

        if best_hvn is not None and best_dist <= tol:
            return True, _graded_score(best_dist, 25.0, 18.0, 10.0), best_hvn

        return False, 0.0, None

    # =================== DETECCIÓN SPRING (FASE C WYCKOFF) ===================

    def detect_spring(self, df):
        """
        Spring de Wyckoff (Fase C) en DOS fases — la mecánica real del mercado:

          1. SHAKEOUT: vela reciente con volumen de clímax (> SMA(20) × FILTER_VOLUMEN) que
             perfora el soporte previo a ESA vela (S1 anclado, ver find_structural_support).
             El cierre suele quedar cerca de mínimos (pánico): NO se exige cierre sobre S1.

          2. RECUPERACIÓN: dentro de SPRING_RECOVERY_WINDOW días, una vela cierra DE NUEVO
             por encima de S1 ('jump back across the creek'), normalmente con volumen normal.
             Confirma que la perforación fue una trampa (absorción institucional).

        S1 NO es el mínimo absoluto de la ventana, sino el SWING-LOW MÁS BAJO que el shakeout
        perfora Y reconquista (ver find_support_clusters). Así el Spring se ancla al soporte del
        rango que realmente rompió, no a un mínimo histórico profundo que el precio ni tocó.
        spring_info['s1'] expone ese soporte para el resto del pipeline.

        El Spring se ancla en la RECUPERACIÓN (spring_info['index'] = recovery_index) porque
        el Test secundario ocurre después de ella. 'low' = mínimo del shake-out completo.
        Retorna el Spring confirmado más reciente dentro de SPRING_SEARCH_WINDOW.
        """
        if len(df) < 25:
            return None

        vol_sma = df['Volume'].rolling(20).mean()
        search_start = max(20, len(df) - self.SPRING_SEARCH_WINDOW)
        n = len(df)
        closes = df['Close'].values.astype(float)
        lows = df['Low'].values.astype(float)
        best_spring = None

        for i in range(search_start, n):
            row = df.iloc[i]
            low_i = lows[i]

            # --- Fase 1: shakeout (volumen de clímax) ---
            sma_vol = float(vol_sma.iloc[i]) if pd.notna(vol_sma.iloc[i]) else 0.0
            if sma_vol <= 0 or float(row['Volume']) <= sma_vol * self.FILTER_VOLUMEN:
                continue

            # Niveles de soporte (swing-lows agrupados) previos a este shakeout
            clusters = self.find_support_clusters(df, i)
            if not clusters:
                # Sin pivotes: respaldo al mínimo anclado de la ventana
                fb = self.find_structural_support(df, anchor_idx=i)
                clusters = [{'floor': fb, 'touches': 1}]

            # --- Fase 2: elegir el soporte MÁS BAJO que se perfora Y se reconquista ---
            # (ascendente por floor → el primero que cumple es el más bajo perforado+reclamado)
            chosen = None
            for c in clusters:
                s1 = c['floor']
                if low_i >= s1:
                    continue  # el shakeout no perfora este soporte
                if (s1 - low_i) / s1 * 100 < self.MIN_SPRING_DEPTH_PCT:
                    continue  # perforación trivial (mero toque), no es un shakeout real
                recovery_idx = None
                spring_low = low_i
                rec_end = min(n, i + 1 + self.SPRING_RECOVERY_WINDOW)
                for j in range(i, rec_end):
                    if lows[j] < spring_low:
                        spring_low = lows[j]
                    if closes[j] > s1:
                        recovery_idx = j
                        break
                if recovery_idx is not None:
                    chosen = (s1, recovery_idx, spring_low, c['touches'])
                    break
            if chosen is None:
                continue  # perforó algo pero no reconquistó ningún soporte → no confirmado

            s1, recovery_idx, spring_low, touches = chosen
            candle_range = float(row['High']) - low_i
            close_pos = (float(row['Close']) - low_i) / candle_range if candle_range > 0 else 0.0

            best_spring = {
                'index': recovery_idx,                      # ancla para el Test secundario
                'date': str(df.index[i].date()),            # fecha del shakeout (señal climática)
                'shakeout_index': i,
                'recovery_index': recovery_idx,
                'recovery_date': str(df.index[recovery_idx].date()),
                's1': round(s1, 4),                         # soporte (swing-low) perforado+reclamado
                'support_touches': touches,                 # veces que se testeó ese soporte
                'low': spring_low,                          # mínimo del shake-out → base del SL
                'close': float(row['Close']),
                'high': float(row['High']),
                'volume': float(row['Volume']),
                'vol_ratio': round(float(row['Volume']) / sma_vol, 2),
                'close_position': round(close_pos, 3),
                'spring_depth_pct': round((s1 - spring_low) / s1 * 100, 3),
            }

        return best_spring

    # =================== DETECCIÓN TEST (GATILLO ENTRADA) ===================

    def detect_test_signal(self, df, spring_idx, s1, spring_low=None):
        """
        Tras la recuperación del Spring, detecta el retroceso secundario de Test:
        el precio REGRESA a la zona del soporte (sin caer bajo el Spring Low) con
        volumen decreciente y por debajo de SMA(20). Es el gatillo de entrada.

        Zona válida: Low entre el Spring Low (suelo: el Test debe sostener un mínimo
        más alto) y S1 × (1 + TEST_TOLERANCE). El Test rara vez toca S1 exacto, por eso
        se admite una banda por encima; pero perder el Spring Low invalidaría el setup.

        Empieza la búsqueda DOS días después de la recuperación porque la vela inmediata
        suele ser continuación del rally, no un retroceso secundario.
        Retorna el Test más reciente.
        """
        # Necesitamos al menos 2 días tras la recuperación (rally + retest mínimo)
        if spring_idx is None or spring_idx >= len(df) - 2:
            return None

        vol_sma = df['Volume'].rolling(20).mean()
        floor = float(spring_low) if spring_low is not None else s1 * 0.97
        upper = s1 * (1 + self.TEST_TOLERANCE)
        latest_test = None

        for i in range(spring_idx + 2, len(df)):
            row = df.iloc[i]
            sma_vol = float(vol_sma.iloc[i]) if pd.notna(vol_sma.iloc[i]) else 0.0
            if sma_vol <= 0:
                continue

            # Retrocede a la zona del soporte manteniéndose sobre el Spring Low
            price_in_zone = floor <= float(row['Low']) <= upper

            if price_in_zone and float(row['Volume']) < sma_vol:
                # Comparar con vela anterior (ya no es el Spring porque empezamos en +2)
                vol_declining = float(row['Volume']) < float(df['Volume'].iloc[i - 1])
                if vol_declining:
                    latest_test = {
                        'index': i,
                        'date': str(df.index[i].date()),
                        'close': float(row['Close']),
                        'volume': float(row['Volume']),
                        'vol_ratio': round(float(row['Volume']) / sma_vol, 2),
                        'is_current': i == len(df) - 1,
                    }

        return latest_test

    # =================== VALIDACIÓN POST-SPRING ===================

    def check_spring_invalidation(self, df, spring_info):
        """
        Verifica si el Spring ha sido INVALIDADO tras formarse:
        si alguna vela posterior cierra POR DEBAJO del mínimo del Spring,
        el supuesto soporte ha fallado y el setup ya no es válido.

        Devuelve dict con 'failed': bool y 'fail_date': fecha si falló.
        """
        if spring_info is None:
            return {'failed': False, 'fail_date': None}

        spring_idx = spring_info['index']
        spring_low = spring_info['low']

        if spring_idx >= len(df) - 1:
            return {'failed': False, 'fail_date': None}

        post_spring = df.iloc[spring_idx + 1:]
        below_mask = post_spring['Close'] < spring_low
        if below_mask.any():
            first_fail_idx = below_mask.idxmax()
            return {'failed': True, 'fail_date': str(first_fail_idx.date())}

        return {'failed': False, 'fail_date': None}

    def check_spring_stale(self, df, spring_idx, test_idx):
        """
        Un Spring SIN Test después de SPRING_MAX_AGE_WITHOUT_TEST días
        pierde fiabilidad: el mercado debería haber retesteado el soporte
        para confirmar la acumulación.
        """
        if test_idx is not None:
            return False
        days_since_spring = (len(df) - 1) - spring_idx
        return days_since_spring > self.SPRING_MAX_AGE_WITHOUT_TEST

    # =================== ATR ===================

    def calculate_atr(self, df):
        """ATR(14) para cálculo de Stop Loss."""
        high  = df['High'].astype(float)
        low   = df['Low'].astype(float)
        prev_close = df['Close'].astype(float).shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(self.ATR_PERIOD).mean()

    # =================== OBV TREND EN LA BASE ===================

    def calculate_obv_trend_in_base(self, df, spring_idx):
        """
        Calcula la tendencia del OBV durante la ventana de acumulación
        previa al Spring. Un OBV con pendiente positiva indica compra
        institucional neta (acumulación silenciosa).
        Devuelve un valor normalizado: positivo = acumulación, negativo = distribución.
        """
        base_start = max(0, spring_idx - self.SUPPORT_LOOKBACK)
        base_df = df.iloc[base_start:spring_idx]

        if len(base_df) < 10:
            return 0.0

        closes  = base_df['Close'].values.astype(float)
        volumes = base_df['Volume'].values.astype(float)

        obv = np.zeros(len(closes))
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - volumes[i]
            else:
                obv[i] = obv[i - 1]

        # Pendiente lineal normalizada por volumen total del período
        x = np.arange(len(obv), dtype=float)
        slope = float(np.polyfit(x, obv, 1)[0])
        total_vol = volumes.sum()

        if total_vol <= 0:
            return 0.0

        # Normalizado: fracción del volumen diario promedio que es neta compradora
        return round(slope / (total_vol / len(obv)), 4)

    # =================== ANCHURA DE BASE (WYCKOFF CAUSE) ===================

    def calculate_base_width(self, df, spring_idx, s1):
        """
        Cuenta los días de trading donde el precio estuvo dentro del rango
        de acumulación (S1 a S1×1.20) antes del Spring.
        Más días en la base = mayor 'causa' = mayor potencial de subida.
        """
        base_start = max(0, spring_idx - self.SUPPORT_LOOKBACK)
        base_df = df.iloc[base_start:spring_idx]

        if base_df.empty:
            return 0

        upper_bound = s1 * 1.20
        in_range = (base_df['Close'] >= s1 * 0.97) & (base_df['Close'] <= upper_bound)
        return int(in_range.sum())

    # =================== TIMING DEL TEST ===================

    def score_test_timing(self, spring_idx, test_idx):
        """
        Puntúa el tiempo transcurrido entre Spring y Test.
        Ideal: 5-25 días de trading. Demasiado rápido o lento reduce la fiabilidad.
        Devuelve 0-20 pts.
        """
        if test_idx is None:
            return 0.0

        days = int(test_idx) - int(spring_idx)

        if 5 <= days <= 25:
            return 20.0                              # Timing ideal
        elif days < 5:
            return max(5.0, 20.0 - (5 - days) * 3) # Demasiado rápido
        elif days <= 40:
            return max(8.0, 20.0 - (days - 25))     # Ligeramente tarde
        else:
            return max(2.0, 8.0 - (days - 40) * 0.2) # Demasiado tarde

    # =================== GESTIÓN DE RIESGO ===================

    def calculate_risk_params(self, spring_info, df, s1, hvn_list):
        """
        SL  = Mínimo Spring − 0.5 × ATR(14)
        TP1 = Resistencia local: máximo de los 60 días previos al Spring
              (ventana ajustada para capturar el techo real del rango de acumulación)
        TP2 = Siguiente HVN superior (si R:R ≥ 1:3) o mínimo R:R 1:3.5
        """
        try:
            spring_idx  = spring_info['index']
            entry_price = s1 * 1.002

            atr_series  = self.calculate_atr(df)
            spring_atr  = float(atr_series.iloc[spring_idx])
            if not np.isfinite(spring_atr) or spring_atr <= 0:
                atr_clean = atr_series.dropna()
                if atr_clean.empty:
                    return None  # No se puede calcular SL sin ATR válido
                spring_atr = float(atr_clean.iloc[-1])
                if spring_atr <= 0:
                    return None

            sl   = spring_info['low'] - 0.5 * spring_atr
            risk = max(entry_price - sl, 1e-6)

            # TP1: resistencia del rango de acumulación (últimos 60 días antes del Spring)
            tp1_start  = max(0, spring_idx - 60)
            pre_spring = df.iloc[tp1_start:spring_idx]['High']
            tp1 = float(pre_spring.max()) if not pre_spring.empty else entry_price * 1.05

            # TP2: siguiente HVN por encima de la entrada, o R:R 1:3.5
            hvn_above = sorted(h for h in hvn_list if h > entry_price * 1.01)
            if hvn_above and (hvn_above[0] - entry_price) / risk >= 3.0:
                tp2 = hvn_above[0]
            else:
                tp2 = entry_price + 3.5 * risk

            return {
                'entry_price': round(entry_price, 2),
                'sl':          round(sl, 4),
                'tp1':         round(tp1, 2),
                'tp2':         round(tp2, 2),
                'risk_pct':    round(abs(entry_price - sl) / entry_price * 100, 2),
                'rr_tp1':      round((tp1 - entry_price) / risk, 2),
                'rr_tp2':      round((tp2 - entry_price) / risk, 2),
                'atr':         round(spring_atr, 4),
            }
        except Exception:
            return None

    # =================== SCORING DUAL: PROBABILIDAD + POTENCIAL ===================

    def calculate_scores(self, spring_info, test_info, test_timing_score,
                          market_health_score, industry_rank, obv_trend,
                          base_width_days, risk_params, confluence_score=0.0):
        """
        Score de Probabilidad (0-60): ¿Es probable que el rebote ocurra?
          - Salud del mercado    0-15 pts  (SPY sobre/bajo MA200)
          - Timing del Test      0-20 pts  (5-25 días = ideal)
          - OBV acumulación      0-15 pts  (pendiente positiva = acumulación real)
          - Sector/industria     0-10 pts  (sector en top 50% del universo)
          - Confluencia S1↔VP    0-10 pts  (bonus: S1 sobre POC/HVN refuerza el soporte)

        Score de Potencial (0-40): ¿Cuánto puede subir?
          - Anchura de base      0-15 pts  (Wyckoff Cause: más días = más fuerza)
          - Ratio R:R TP2        0-15 pts  (R:R ≥ 4 = máximo)
          - Profundidad shake-out 0-10 pts  (wick más profundo = más absorción)

        Total Wyckoff Score = Probabilidad + Potencial (0-100). Probabilidad se trunca a 60,
        así que la confluencia actúa como bonus que compensa otros componentes flojos.
        """
        # --- PROBABILIDAD ---
        prob = 0.0

        # 1. Salud mercado (0-15)
        prob += min(15.0, max(0.0, float(market_health_score)))

        # 2. Test timing (0-20) — 0 si no hay test
        prob += min(20.0, max(0.0, float(test_timing_score)))

        # Bonus confluencia (0-10): confluence_score viene en escala 0-30
        prob += min(10.0, max(0.0, float(confluence_score) / 3.0))

        # 3. OBV en base (0-15)
        if obv_trend > 0:
            obv_score = min(15.0, obv_trend * 30)
            prob += max(0.0, obv_score)
        # OBV negativo = distribución = 0 pts

        # 4. Rango de industria (0-10)
        rank = float(industry_rank)
        if rank >= 75:
            prob += 10.0
        elif rank >= 60:
            prob += 7.0
        elif rank >= 50:
            prob += 4.0
        elif rank >= 35:
            prob += 2.0

        # --- POTENCIAL ---
        pot = 0.0

        # 1. Anchura de base — Wyckoff Cause (0-15)
        if base_width_days >= 80:
            pot += 15.0
        elif base_width_days >= 50:
            pot += 10.0
        elif base_width_days >= 30:
            pot += 6.0
        elif base_width_days >= 15:
            pot += 3.0

        # 2. R:R TP2 (0-15)
        rr_tp2 = float((risk_params or {}).get('rr_tp2', 0))
        if rr_tp2 >= 4.0:
            pot += 15.0
        elif rr_tp2 >= 3.0:
            pot += 10.0
        elif rr_tp2 >= 2.0:
            pot += 6.0
        elif rr_tp2 >= 1.5:
            pot += 3.0

        # 3. Profundidad del shake-out (0-10)
        depth = float(spring_info.get('spring_depth_pct', 0))
        if depth >= 3.0:
            pot += 10.0
        elif depth >= 1.5:
            pot += 6.0
        elif depth >= 0.5:
            pot += 3.0

        probability_score = round(min(60.0, prob), 1)
        potential_score   = round(min(40.0, pot),  1)
        total_score       = round(probability_score + potential_score, 1)

        return probability_score, potential_score, total_score

    # =================== ANÁLISIS COMPLETO POR ACCIÓN ===================

    def analyze_wyckoff_stock(self, symbol, df, rs_rating,
                               market_healthy=True, market_health_score=10.0,
                               industry_rank=50.0):
        """
        Pipeline Wyckoff completo:
        VP → S1 → Confluencia → Spring → Test → Riesgo → Scoring dual.
        """
        result = {
            'current_price': None, 'rs_rating': rs_rating,
            # Volume Profile
            'poc_level': None, 'hvn_count': 0,
            # Soporte
            's1_level': None,
            # Confluencia
            'confluence_valid': False, 'confluence_score': 0.0,
            'nearest_confluence_level': None,
            # Spring
            'spring_detected': False, 'spring_info': None,
            'spring_failed': False, 'spring_fail_date': None,
            'spring_stale': False,
            # Test
            'test_detected': False, 'test_info': None,
            # Métricas de mercado y contexto
            'market_healthy': market_healthy,
            'market_health_score': market_health_score,
            'industry_rank': industry_rank,
            # Métricas de calidad
            'obv_trend_base': 0.0,
            'base_width_days': 0,
            'test_timing_days': None,
            'test_timing_score': 0.0,
            # Scores finales
            'probability_score': 0.0,
            'potential_score': 0.0,
            'wyckoff_score': 0.0,
            # Estado y riesgo
            'entry_status': 'Sin Señal',
            'is_actionable': False,  # True solo si el setup sigue vivo y operable
            'risk_params': None,
        }

        if len(df) < self.MIN_DATA_POINTS:
            return result

        result['current_price'] = float(df['Close'].iloc[-1])

        # Filtro penny stocks: precio < $5 → ruido, spreads enormes, manipulación
        if result['current_price'] < self.MIN_PRICE:
            result['entry_status'] = f'Filtrado (penny stock <${self.MIN_PRICE:.0f})'
            return result

        # Paso 1: Volume Profile
        poc, hvn_list = self.calculate_volume_profile(df)
        result['poc_level'] = round(poc, 4) if poc is not None else None
        result['hvn_count'] = len(hvn_list)

        # Paso 2: Spring (calcula su propio S1 anclado al shakeout, ver detect_spring)
        spring_info = self.detect_spring(df)

        # Paso 3: Soporte Estructural S1.
        # Si hay Spring, S1 = soporte anclado a ESE Spring (lo que perfora realmente).
        # Si no, S1 = vista actual (ventana fija) solo para reportar un nivel orientativo.
        s1 = spring_info['s1'] if spring_info else self.find_structural_support(df)
        result['s1_level'] = round(s1, 4)

        # Paso 4: Confluencia (NO bloqueante — bonus de calidad en el scoring).
        # En suelos de capitulación el POC/HVN suele quedar MUY por encima de S1, así que
        # exigir confluencia como gate descartaba justo los springs de fondo. Ahora informa
        # el ranking (a más cerca de POC/HVN, más puntos) pero su ausencia no descarta.
        confluence_valid, confluence_score, nearest_level = self.check_s1_confluence(s1, poc, hvn_list)
        result['confluence_valid'] = confluence_valid
        result['confluence_score'] = confluence_score
        result['nearest_confluence_level'] = round(float(nearest_level), 4) if nearest_level is not None else None

        if not spring_info:
            return result

        result['spring_detected'] = True
        result['spring_info'] = spring_info
        spring_idx = spring_info['index']

        # Paso 5: Validación post-Spring (¿el Spring ha sido invalidado?)
        invalidation = self.check_spring_invalidation(df, spring_info)
        result['spring_failed'] = invalidation['failed']
        result['spring_fail_date'] = invalidation['fail_date']

        # Paso 6: Test
        # El timing Wyckoff "Spring → Test" se mide desde el SHAKEOUT (no desde la
        # recuperación), que es el evento climático que da nombre al Spring.
        shakeout_idx = spring_info.get('shakeout_index', spring_idx)
        test_info = self.detect_test_signal(df, spring_idx, s1, spring_info['low'])
        if test_info:
            result['test_detected'] = True
            result['test_info'] = test_info
            result['test_timing_days'] = int(test_info['index']) - int(shakeout_idx)
        test_idx = test_info['index'] if test_info else None

        # Paso 7: Comprobar si está caduco (Spring sin Test tras N días)
        result['spring_stale'] = self.check_spring_stale(df, spring_idx, test_idx)

        # Paso 7b: Métricas de calidad de la base (necesarias para el gate de operabilidad)
        result['obv_trend_base'] = self.calculate_obv_trend_in_base(df, spring_idx)
        result['base_width_days'] = self.calculate_base_width(df, spring_idx, s1)
        result['test_timing_score'] = self.score_test_timing(shakeout_idx, test_idx)

        # Gate de CALIDAD: un setup solo es operable si tiene una base (causa Wyckoff) suficiente
        # y un shakeout con profundidad real. Separa springs genuinos de rebotes ordinarios.
        spring_depth = float(spring_info.get('spring_depth_pct', 0))
        quality_ok = (result['base_width_days'] >= self.ACTIONABLE_MIN_BASE_WIDTH and
                      spring_depth >= self.ACTIONABLE_MIN_DEPTH_PCT)

        # Paso 8: Determinar entry_status final.
        # FILTRO ESTRICTO: is_actionable=True SOLO para entradas operables HOY:
        #   - Test es la vela actual (entrada ideal inmediata), O
        #   - Test ocurrió en últimos ACTIONABLE_TEST_MAX_AGE días Y
        #     precio sigue dentro de ACTIONABLE_PRICE_MAX_ABOVE_S1 sobre S1.
        #   ...Y SIEMPRE que pase el gate de calidad (base + profundidad).
        # Springs sin Test, entradas superadas, fallidos, caducos y débiles → no operables.
        if result['spring_failed']:
            result['entry_status'] = f"Spring FALLIDO ({invalidation['fail_date']})"
            result['is_actionable'] = False
        elif result['spring_stale']:
            days = (len(df) - 1) - spring_idx
            result['entry_status'] = f'Spring Caducado (>{self.SPRING_MAX_AGE_WITHOUT_TEST}d sin Test, {days}d)'
            result['is_actionable'] = False
        elif test_info and not quality_ok:
            # Hay Test, pero la calidad del setup es insuficiente para operar
            result['entry_status'] = (
                f'Setup débil (base {result["base_width_days"]}d<{self.ACTIONABLE_MIN_BASE_WIDTH} '
                f'o depth {spring_depth:.1f}%<{self.ACTIONABLE_MIN_DEPTH_PCT})'
            )
            result['is_actionable'] = False
        elif test_info:
            days_since_test = int(len(df) - 1) - int(test_info['index'])
            price_above_s1_pct = (result['current_price'] - s1) / s1

            if test_info.get('is_current'):
                result['entry_status'] = '🎯 ENTRADA INMEDIATA (Test hoy)'
                result['is_actionable'] = True
            elif (days_since_test <= self.ACTIONABLE_TEST_MAX_AGE and
                  price_above_s1_pct <= self.ACTIONABLE_PRICE_MAX_ABOVE_S1):
                result['entry_status'] = (
                    f'✅ Entrada Vigente (Test hace {days_since_test}d, '
                    f'precio +{price_above_s1_pct*100:.1f}% sobre S1)'
                )
                result['is_actionable'] = True
            else:
                # Test sucedió pero entrada ya no es operable
                reasons = []
                if days_since_test > self.ACTIONABLE_TEST_MAX_AGE:
                    reasons.append(f'Test hace {days_since_test}d')
                if price_above_s1_pct > self.ACTIONABLE_PRICE_MAX_ABOVE_S1:
                    reasons.append(f'precio +{price_above_s1_pct*100:.1f}% sobre S1')
                result['entry_status'] = f'Entrada Superada ({"; ".join(reasons)})'
                result['is_actionable'] = False
        else:
            # Spring sin Test → watchlist, no operable hoy
            days_since_spring = (len(df) - 1) - spring_idx
            result['entry_status'] = f'Watchlist: Spring sin Test ({days_since_spring}d)'
            result['is_actionable'] = False

        # Paso 10: Gestión de riesgo
        risk_params = self.calculate_risk_params(spring_info, df, s1, hvn_list)
        result['risk_params'] = risk_params

        # Paso 11: Scoring dual — Springs fallidos / caducados reciben score 0
        if result['spring_failed'] or result['spring_stale']:
            result['probability_score'] = 0.0
            result['potential_score']   = 0.0
            result['wyckoff_score']     = 0.0
        else:
            prob, pot, total = self.calculate_scores(
                spring_info, test_info, result['test_timing_score'],
                market_health_score, industry_rank, result['obv_trend_base'],
                result['base_width_days'], risk_params, confluence_score
            )
            result['probability_score'] = prob
            result['potential_score']   = pot
            result['wyckoff_score']     = total

        return result

    # =================== PROCESAMIENTO MASIVO ===================

    def process_stocks_wyckoff(self, symbols, all_historical_data, rs_ratings,
                                spy_df=None, industry_ranks=None):
        """
        Procesa el universo completo aplicando el análisis Wyckoff Spring.
        Precomputa salud del mercado y pasa el contexto a cada análisis individual.
        """
        industry_ranks = industry_ranks or {}

        # Evaluar estado del mercado una sola vez para todos los análisis
        market_healthy, market_health_score = self.check_market_health(spy_df)
        if market_healthy:
            print(f"✓ Mercado ALCISTA (S&P sobre MA200) — Score de mercado: {market_health_score}/15")
        else:
            print(f"⚠️ ALERTA: Mercado BAJISTA (S&P bajo MA200) — Score de mercado: {market_health_score}/15")
            print(f"   Los Springs en mercado bajista tienen menor probabilidad de éxito.")

        stock_data = {}
        failed = []

        print(f"\nIniciando análisis Wyckoff de {len(symbols)} candidatos...")

        for symbol in tqdm(symbols, desc="Análisis Wyckoff", unit="acción"):
            try:
                df = all_historical_data.get(symbol)
                if df is None or len(df) < self.MIN_DATA_POINTS:
                    continue

                rs_rating    = float(rs_ratings.get(symbol, 0))
                industry     = self.symbol_industries.get(symbol, {}).get('industry', 'Unknown')
                industry_rank = float(industry_ranks.get(industry, 50.0))

                analysis = self.analyze_wyckoff_stock(
                    symbol, df, rs_rating,
                    market_healthy=market_healthy,
                    market_health_score=market_health_score,
                    industry_rank=industry_rank,
                )

                stock_data[symbol] = {
                    'data': df,
                    'wyckoff_analysis': analysis,
                    'info': self.symbol_industries.get(symbol, {}),
                }
            except Exception:
                failed.append(symbol)

        spring_count = sum(1 for d in stock_data.values() if d['wyckoff_analysis']['spring_detected'])
        test_count   = sum(1 for d in stock_data.values() if d['wyckoff_analysis']['test_detected'])
        print(f"\n✓ Análisis completado: {spring_count} springs | {test_count} tests activos | {len(failed)} errores")

        return stock_data, failed

    # =================== GUARDADO CSV ===================

    def compute_risk_ranking(self, current_price, sl, wyckoff_score):
        """
        Riesgo de operar HOY = % desde el precio actual al Stop Loss.
        Devuelve (current_to_sl_pct, rank_score) donde:
          rank_score = Wyckoff_Score + bonus(0-RISK_BONUS_POINTS) que premia un SL cercano.
        El bonus decae linealmente: SL pegado al precio → +RISK_BONUS_POINTS;
        SL a ≥RISK_BONUS_MAX_PCT% → +0. Así el Top 10 prioriza riesgo bajo sin ignorar la calidad.
        """
        ws = float(wyckoff_score or 0.0)
        try:
            cp = float(current_price); s = float(sl)
        except (TypeError, ValueError):
            return None, round(ws, 1)
        if cp <= 0 or s <= 0:
            return None, round(ws, 1)
        c2sl = (cp - s) / cp * 100.0
        bonus = self.RISK_BONUS_POINTS * max(0.0, 1.0 - max(0.0, c2sl) / self.RISK_BONUS_MAX_PCT)
        return round(c2sl, 2), round(ws + bonus, 1)

    def save_wyckoff_data(self, stock_data, filename_prefix="wyckoff_spring_analysis"):
        """Guarda ALL_DATA (universo completo) y SPRINGS (señales con Spring detectado)."""
        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_rows, springs_rows = [], []

        for symbol, data in stock_data.items():
            df = data['data']
            an = data['wyckoff_analysis']
            info = data['info']
            sp = an.get('spring_info') or {}
            te = an.get('test_info') or {}
            rp = an.get('risk_params') or {}

            row = {
                'Symbol':        symbol,
                'Company_Name':  info.get('name', 'N/A'),
                'Sector':        info.get('sector', 'N/A'),
                'Industry':      info.get('industry', 'N/A'),
                'Current_Price': an.get('current_price'),
                'RS_Rating':     an.get('rs_rating'),
                # Scores
                'Wyckoff_Score':     an.get('wyckoff_score'),
                'Probability_Score': an.get('probability_score'),
                'Potential_Score':   an.get('potential_score'),
                # Contexto de mercado
                'Market_Healthy':       an.get('market_healthy'),
                'Market_Health_Score':  an.get('market_health_score'),
                'Industry_Rank':        an.get('industry_rank'),
                # Volume Profile y Soporte
                'S1_Level':             an.get('s1_level'),
                'POC_Level':            an.get('poc_level'),
                'HVN_Count':            an.get('hvn_count'),
                'Confluence_Valid':     an.get('confluence_valid'),
                'Confluence_Score':     an.get('confluence_score'),
                'Nearest_Confluence':   an.get('nearest_confluence_level'),
                # Spring
                'Spring_Detected':      an.get('spring_detected'),
                'Spring_Date':          sp.get('date', ''),
                'Spring_Recovery_Date': sp.get('recovery_date', ''),
                'Spring_Low':           sp.get('low', ''),
                'Spring_Volume_Ratio':  sp.get('vol_ratio', ''),
                'Spring_Close_Position':sp.get('close_position', ''),
                'Spring_Depth_Pct':     sp.get('spring_depth_pct', ''),
                'Support_Touches':      sp.get('support_touches', ''),
                'Spring_Failed':        an.get('spring_failed', False),
                'Spring_Fail_Date':     an.get('spring_fail_date', ''),
                'Spring_Stale':         an.get('spring_stale', False),
                'Is_Actionable':        an.get('is_actionable', False),
                # Calidad de la base
                'OBV_Trend_Base':   an.get('obv_trend_base'),
                'Base_Width_Days':  an.get('base_width_days'),
                # Test
                'Test_Detected':     an.get('test_detected'),
                'Test_Date':         te.get('date', ''),
                'Test_Volume_Ratio': te.get('vol_ratio', ''),
                'Test_Timing_Days':  an.get('test_timing_days'),
                'Test_Timing_Score': an.get('test_timing_score'),
                # Estado y gestión de riesgo
                'Entry_Status': an.get('entry_status'),
                'Entry_Price':  rp.get('entry_price', ''),
                'SL':           rp.get('sl', ''),
                'TP1':          rp.get('tp1', ''),
                'TP2':          rp.get('tp2', ''),
                'Risk_Pct':     rp.get('risk_pct', ''),
                'RR_TP1':       rp.get('rr_tp1', ''),
                'RR_TP2':       rp.get('rr_tp2', ''),
                'ATR':          rp.get('atr', ''),
                # Metadatos
                'Data_Points': len(df),
                'Start_Date':  df.index.min().strftime('%Y-%m-%d'),
                'End_Date':    df.index.max().strftime('%Y-%m-%d'),
            }
            # Riesgo (precio actual → SL) y score de ranking (calidad + bonus por riesgo bajo)
            current_to_sl, rank_score = self.compute_risk_ranking(
                an.get('current_price'), rp.get('sl'), an.get('wyckoff_score')
            )
            row['Current_To_SL_Pct'] = current_to_sl if current_to_sl is not None else ''
            row['Rank_Score'] = rank_score
            all_rows.append(row)
            # Solo guardar como Spring activo si está detectado Y operable
            # (no fallido ni caduco)
            if an.get('spring_detected') and an.get('is_actionable'):
                springs_rows.append(row)

        all_df = pd.DataFrame(all_rows)
        all_filename = f"{filename_prefix}_ALL_DATA_{timestamp}.csv"
        all_df.to_csv(all_filename, index=False)
        print(f"✓ Guardado: {all_filename}")

        if springs_rows:
            # Orden por Rank_Score = Wyckoff_Score + bonus por riesgo bajo (SL cercano)
            springs_df = pd.DataFrame(springs_rows).sort_values('Rank_Score', ascending=False)
            springs_filename = f"{filename_prefix}_SPRINGS_{timestamp}.csv"
            springs_df.to_csv(springs_filename, index=False)
            print(f"✓ Guardado: {springs_filename} ({len(springs_rows)} springs)")
        else:
            print("❌ Ninguna acción detectó Spring de Wyckoff hoy")
            springs_df = pd.DataFrame()

        return all_df, springs_df


# =================== PIPELINE PRINCIPAL ===================

def _run_analysis_pipeline(screener):
    """Ejecuta el pipeline completo: símbolos → datos → RS → Wyckoff."""
    print("Obteniendo símbolos NYSE + NASDAQ...")
    all_symbols = screener.get_nyse_nasdaq_symbols()
    original_count = len(all_symbols)

    all_symbols = [s for s in all_symbols if '^' not in s and '.' not in s and '/' not in s]
    print(f"✓ Filtrados {original_count - len(all_symbols)} warrants/preferentes")
    print(f"Total acciones a analizar: {len(all_symbols)}")

    if not all_symbols:
        print("❌ No se pudieron obtener símbolos")
        return None, None

    # Paso 1: Descarga masiva (incluye ^GSPC)
    all_historical_data = screener.download_all_data(all_symbols)
    spy_df = all_historical_data.pop('_MARKET_INDEX', None)

    # Paso 2: RS Rating
    rs_scores  = screener.calculate_all_rs_scores(all_historical_data)
    rs_ratings = screener.calculate_rs_ratings_from_scores(rs_scores)

    # Paso 3: Ranking industrial
    print("\nCalculando ranking de grupos industriales...")
    industry_ranks = screener.rank_industries_by_rs(rs_ratings)
    print(f"✓ {len(industry_ranks)} grupos industriales rankeados.")

    # Paso 4: Análisis Wyckoff — sin pre-filtro por RS (Springs en cualquier stock)
    symbols_to_process = list(all_historical_data.keys())
    all_stock_data, all_failed = screener.process_stocks_wyckoff(
        symbols_to_process, all_historical_data, rs_ratings,
        spy_df=spy_df, industry_ranks=industry_ranks
    )

    return all_stock_data, all_failed


def _generate_final_report(screener, all_stock_data, all_failed):
    """Genera y muestra el TOP 10 final con scoring dual."""
    print(f"\n=== RESUMEN FINAL WYCKOFF SPRING ===")
    print(f"Procesadas: {len(all_stock_data)} | Errores: {len(all_failed)}")

    all_summary, springs_summary = screener.save_wyckoff_data(all_stock_data)

    spring_count = len(springs_summary) if not springs_summary.empty else 0
    test_count   = 0
    if not springs_summary.empty and 'Test_Detected' in springs_summary.columns:
        test_count = int(springs_summary['Test_Detected'].sum())

    # Estadísticas de invalidación sobre TODO el universo
    total_springs_raw = 0
    failed_count = 0
    stale_count = 0
    if not all_summary.empty:
        if 'Spring_Detected' in all_summary.columns:
            total_springs_raw = int(all_summary['Spring_Detected'].sum())
        if 'Spring_Failed' in all_summary.columns:
            failed_count = int(all_summary['Spring_Failed'].sum())
        if 'Spring_Stale' in all_summary.columns:
            stale_count = int(all_summary['Spring_Stale'].sum())

    pct = spring_count / len(all_stock_data) * 100 if all_stock_data else 0
    print(f"\nSprings detectados (brutos):  {total_springs_raw}")
    print(f"  └── Fallidos (invalidados): {failed_count}")
    print(f"  └── Caducados (sin Test):   {stale_count}")
    print(f"  └── ACTIVOS y operables:    {spring_count} ({pct:.1f}% del universo)")
    print(f"Tests activos (zona de entrada): {test_count}")

    if not springs_summary.empty:
        # Solo entradas operables HOY (springs_summary ya viene filtrado a is_actionable),
        # ordenadas por Rank_Score = Wyckoff_Score + bonus por riesgo bajo (SL cercano).
        top_10 = springs_summary.sort_values('Rank_Score', ascending=False).head(10)

        print(f"\n{'='*100}")
        print(f"🔝 TOP 10 — ENTRADAS OPERABLES HOY (orden: calidad + riesgo bajo)")
        print(f"{'='*100}")
        for i, (_, row) in enumerate(top_10.iterrows()):
            total = row.get('Wyckoff_Score', 0)
            rank  = row.get('Rank_Score', total)
            c2sl  = row.get('Current_To_SL_Pct', '')
            rp    = row.get('RR_TP2', '')
            status = str(row.get('Entry_Status', ''))
            mkt    = "✅" if row.get('Market_Healthy', True) else "⚠️"
            risk_str = f"{c2sl:.1f}%" if isinstance(c2sl, (int, float)) else "n/a"
            print(
                f"{i+1:2d}. {row['Symbol']:6s} | {mkt} | "
                f"Rank: {rank:5.1f} (Score {total:.0f}) | "
                f"Riesgo→SL: {risk_str:>5s} | "
                f"Precio:${row.get('Current_Price',0):7.2f} | "
                f"R:R={rp} | {status}"
            )

        print(f"\n=== DISTRIBUCIÓN DE SEÑALES ===")
        for status, count in springs_summary['Entry_Status'].value_counts().items():
            print(f"  {status}: {count}")

        # Estadísticas de scoring
        print(f"\n=== ESTADÍSTICAS DE SCORING ===")
        print(f"  Score promedio (springs): {springs_summary['Wyckoff_Score'].mean():.1f}/100")
        print(f"  Score prob. promedio:     {springs_summary['Probability_Score'].mean():.1f}/60")
        print(f"  Score potencial promedio: {springs_summary['Potential_Score'].mean():.1f}/40")
        print(f"  OBV positivo (acumulación): {(springs_summary['OBV_Trend_Base'] > 0).sum()} / {len(springs_summary)}")
        print(f"  Base > 50 días:             {(springs_summary['Base_Width_Days'] >= 50).sum()} / {len(springs_summary)}")


def main():
    """Función principal — Wyckoff Spring Swing Trading Screener."""
    print("=== WYCKOFF SPRING SCREENER ===")
    print("Estrategia: Swing Trading Macro | Temporalidad: Diario (1D)")
    print("Metodología: Fase C Wyckoff + Volume Profile (VPVR)")
    print("Filtro mercado: S&P 500 sobre MA200 = mercado alcista\n")

    screener = WyckoffSpringScreener()
    all_stock_data, all_failed = _run_analysis_pipeline(screener)

    if all_stock_data:
        _generate_final_report(screener, all_stock_data, all_failed)
    else:
        print("❌ No se obtuvieron datos")
        exit(1)


if __name__ == "__main__":
    main()
