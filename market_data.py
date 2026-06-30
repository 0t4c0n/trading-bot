# market_data.py — Infraestructura de datos de mercado (reutilizable)
#
# Universo (NYSE+NASDAQ, solo acciones comunes/ADRs), descarga de históricos y
# salud del mercado. Desacoplado de cualquier estrategia: lo usan el screener de
# momentum y los backtests.

import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
import yfinance as yf
from tqdm import tqdm


# === FILTRO DE TIPO DE INSTRUMENTO ===
# El screener de NASDAQ devuelve 'sector' vacío para todos los valores, así que NO
# se puede filtrar por sector. El campo 'name' (descripción) sí separa las acciones
# comunes del resto. KEEP: "Common Stock/Shares", ADRs. DROP: bonos, preferentes,
# fondos cerrados (CEF), SPACs, warrants, units. Truco "Trust": REITs operativos
# dicen "Common Stock" (se mantienen), los CEF dicen "Common Shares" (se descartan).
_INSTRUMENT_DROP_RE = re.compile(
    r'(\bnotes?\b|\bbond\b|debenture|%|\bwarrant|\bright(s)?\b|'
    r'preferred|\bseries\b|\bdue\s+20|\bunit(s)?\b|\betf\b|\betn\b|\bfund\b|'
    r'acquisition corp|\bordinary shares\b)', re.I)
_INSTRUMENT_KEEP_RE = re.compile(
    r'\b(common stock|common shares|american depositary shares|depositary shares)\b', re.I)


def is_common_stock(name):
    """True si el nombre del valor corresponde a una acción común (o ADR común)."""
    n = (name or '').strip()
    if not n or _INSTRUMENT_DROP_RE.search(n):
        return False
    if re.search(r'\btrust\b', n, re.I) and re.search(r'common shares', n, re.I):
        return False
    return bool(_INSTRUMENT_KEEP_RE.search(n))


class MarketData:
    def __init__(self, history_days=540):
        # 540 días naturales (~18 meses) — margen cómodo para MA200, máximo 52s y
        # momentum 6m (la estrategia evalúa la última barra y necesita ≥252 sesiones).
        self.history_days = history_days
        self.symbol_industries = {}
        self.session = requests.Session()

    # --- Universo ---
    def get_universe(self):
        """Símbolos NYSE + NASDAQ (solo acciones comunes), con respaldo."""
        try:
            nyse = self.get_exchange_symbols('NYSE')
            nasdaq = self.get_exchange_symbols('NASDAQ')
            syms = list(set(nyse + nasdaq))
            if syms:
                return [s for s in syms if '^' not in s and '.' not in s and '/' not in s]
        except Exception as e:
            print(f"Error obteniendo símbolos: {e}")
        backup = self.get_backup_symbols()
        print(f"Usando lista de respaldo: {len(backup)} símbolos")
        return backup

    def get_exchange_symbols(self, exchange):
        url = "https://api.nasdaq.com/api/screener/stocks"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        params = {'tableonly': 'true', 'limit': '25000', 'exchange': exchange}
        try:
            r = self.session.get(url, headers=headers, params=params, timeout=15)
            if r.status_code != 200:
                return []
            rows = r.json()['data']['table']['rows']
            symbols, skipped = [], 0
            for row in rows:
                name = row.get('name', '') or ''
                if not is_common_stock(name):
                    skipped += 1
                    continue
                sym = row['symbol']
                symbols.append(sym)
                self.symbol_industries[sym] = {
                    'name': name,
                    'industry': row.get('industry', 'Unknown') or 'Unknown',
                    'sector': row.get('sector', 'Unknown') or 'Unknown',
                }
            print(f"  {len(symbols)} acciones de {exchange} ({skipped} no-acciones descartadas).")
            return symbols
        except Exception as e:
            print(f"Error obteniendo símbolos de {exchange}: {e}")
            return []

    def get_backup_symbols(self):
        majors = [
            'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'AXP', 'SCHW', 'BLK', 'SPGI', 'V', 'MA',
            'CAT', 'DE', 'GE', 'HON', 'LMT', 'RTX', 'MMM', 'UPS', 'ETN', 'PH',
            'WMT', 'HD', 'PG', 'KO', 'PEP', 'COST', 'NKE', 'SBUX', 'MCD', 'DIS',
            'JNJ', 'PFE', 'ABT', 'MRK', 'LLY', 'AMGN', 'GILD', 'MDT', 'DHR', 'TMO', 'SYK', 'ISRG',
            'XOM', 'CVX', 'COP', 'EOG', 'SLB', 'PSX', 'VLO', 'MPC',
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NFLX', 'NVDA', 'ADBE', 'AVGO',
            'TXN', 'QCOM', 'INTU', 'AMD', 'KLAC', 'LRCX', 'AMAT', 'MU', 'MRVL', 'CRWD',
            'SNOW', 'PLTR', 'PANW', 'DDOG', 'NOW', 'ORCL', 'CRM',
        ]
        return list(set(majors))

    # --- Descarga ---
    def download_all_data(self, symbols, batch_size=75):
        """Descarga OHLCV (sin Open) en lotes con reintentos. Incluye '_MARKET_INDEX' (^GSPC)."""
        end = datetime.now()
        start = end - timedelta(days=self.history_days)
        print(f"Descargando {len(symbols)} símbolos | ventana {start:%Y-%m-%d} → {end:%Y-%m-%d}")
        all_data = {}
        n_batches = (len(symbols) + batch_size - 1) // batch_size
        for i in tqdm(range(n_batches), desc="Descarga", unit="lote"):
            batch = symbols[i * batch_size:(i + 1) * batch_size]
            for attempt in range(3):
                try:
                    bd = yf.download(batch, start=start, end=end, group_by='ticker',
                                     auto_adjust=True, threads=True, progress=False, timeout=30)
                    for s in batch:
                        if s in bd.columns:
                            df = bd[s].dropna()
                            if isinstance(df.columns, pd.MultiIndex):
                                df.columns = df.columns.droplevel(-1)
                            if not df.empty:
                                df = df[[c for c in ['High', 'Low', 'Close', 'Volume'] if c in df.columns]]
                                all_data[s] = df
                    break
                except Exception as e:
                    time.sleep(10 * (2 ** attempt))
        print(f"✓ Descargados {len(all_data)} símbolos.")
        try:
            spy = yf.download('^GSPC', start=start, end=end, auto_adjust=True, progress=False, timeout=30)
            if not spy.empty:
                if isinstance(spy.columns, pd.MultiIndex):
                    spy.columns = spy.columns.droplevel(-1)
                all_data['_MARKET_INDEX'] = spy[['Close']]
                print("✓ ^GSPC descargado.")
        except Exception as e:
            print(f"⚠️ Error ^GSPC: {e}")
        return all_data

    # --- Filtro de liquidez (calidad institucional) ---
    @staticmethod
    def liquid_symbols(data, min_dollar_vol=20_000_000, min_price=10.0, window=50):
        """Devuelve los símbolos con liquidez institucional: dólar-volumen MEDIANO
        de las últimas `window` sesiones ≥ min_dollar_vol y precio ≥ min_price.

        Es el filtro que faltaba: sin él, microcaps y chicharros (biotechs que se
        disparan con UNA noticia, etc.) inflan el percentil de fuerza relativa con
        'pops' irrepetibles y desplazan a los líderes reales (Micron, SanDisk, ADI...).
        Se usa la MEDIANA del dólar-volumen (no la media) para que un único día de
        volumen anómalo no cuele a un valor ilíquido.
        """
        keep = []
        for s, df in data.items():
            if 'Volume' not in df.columns or len(df) < window:
                continue
            c = df['Close'].astype(float)
            v = df['Volume'].astype(float)
            price = float(c.iloc[-1])
            dollar_vol = float((c.iloc[-window:] * v.iloc[-window:]).median())
            if price >= min_price and dollar_vol >= min_dollar_vol:
                keep.append(s)
        return keep

    # --- Exclusión de cripto-DIRECTO (mineras / tesorerías bitcoin / exchanges) ---
    # El usuario quiere fuera lo DIRECTAMENTE ligado a cripto/bitcoin (muy volátil y con
    # riesgo regulatorio: prohibiciones, etc.), pero MANTENER las de tecnología blockchain.
    # La API de NASDAQ no da industria fiable (RIOT figura como "Financial Services"), así
    # que se detecta por la DESCRIPCIÓN del negocio (yfinance) + una lista conocida.
    KNOWN_CRYPTO_DIRECT = {
        'COIN', 'MSTR', 'MARA', 'RIOT', 'CLSK', 'HUT', 'WULF', 'CORZ', 'BITF', 'BTBT',
        'CIFR', 'IREN', 'HIVE', 'BTDR', 'SDIG', 'GREE', 'BTCS', 'SOS', 'CAN', 'CANG',
        'EBON', 'NCTY', 'BTCM', 'DGHI', 'ARBK', 'BTM', 'BTCT', 'SLNH', 'GRYP',
    }
    CRYPTO_EXCLUDE_KEYWORDS = (
        'bitcoin mining', 'bitcoin miner', 'mine bitcoin', 'mining bitcoin',
        'cryptocurrency mining', 'crypto mining', 'digital asset mining',
        'mining of digital assets', 'mining of cryptocurrency', 'mines cryptocurrency',
        'mining of bitcoin', 'bitcoin treasury', 'cryptocurrency treasury',
        'crypto treasury', 'cryptocurrency exchange', 'crypto asset',
    )

    @classmethod
    def enrich_candidates(cls, symbols, retries=5, pause=0.6):
        """Consulta yfinance .info por candidato (solo ~decenas) para lo que el código no
        calcula: cripto-directo, sector, margen neto, crecimiento ventas/EPS, recomendación,
        objetivo y días al próximo resultado. dict[sym] -> dict(...).

        yfinance .info es FRÁGIL en lote (Yahoo lo throttlea tras descargas pesadas y
        devuelve vacío): por eso reintenta con backoff y pausa entre símbolos, y detecta
        respuestas vacías. Si aun así falla, deja los campos a None y marca enriched=False
        (el screener degrada con elegancia: no filtra por fundamental ni avisa de sector)."""
        import time as _t
        out = {}
        for s in symbols:
            d = dict(is_crypto=(s in cls.KNOWN_CRYPTO_DIRECT), name=None, sector=None, margin=None,
                     revg=None, epsg=None, rating=None, target=None, earnings_days=None,
                     enriched=False)
            for attempt in range(retries):
                try:
                    info = yf.Ticker(s).info or {}
                    # respuesta útil: debe traer al menos sector o un fundamental o la descripción
                    if not any(info.get(k) for k in
                               ('sector', 'profitMargins', 'longBusinessSummary', 'longName')):
                        raise ValueError('info vacío (throttle)')
                    summ = (info.get('longBusinessSummary', '') or '').lower()
                    if not d['is_crypto'] and any(k in summ for k in cls.CRYPTO_EXCLUDE_KEYWORDS):
                        d['is_crypto'] = True
                    d['name'] = info.get('longName') or info.get('shortName')
                    d['sector'] = info.get('sector')
                    d['margin'] = info.get('profitMargins')
                    d['revg'] = info.get('revenueGrowth')
                    d['epsg'] = info.get('earningsGrowth') or info.get('earningsQuarterlyGrowth')
                    d['rating'] = info.get('recommendationKey')
                    d['target'] = info.get('targetMeanPrice')
                    ts = info.get('earningsTimestamp') or info.get('earningsTimestampStart')
                    if ts:
                        d['earnings_days'] = int((ts - _t.time()) // 86400)
                    d['enriched'] = True
                    break
                except Exception:
                    _t.sleep(pause * (2 ** attempt))   # backoff: 0.5, 1, 2, 4 s
            out[s] = d
            _t.sleep(pause)                            # pausa cortés entre símbolos
        n_ok = sum(1 for v in out.values() if v['enriched'])
        print(f"  Enriquecidos {n_ok}/{len(out)} candidatos (yfinance .info)")
        return out

    # --- Salud del mercado ---
    def check_market_health(self, spy_df):
        """¿Mercado alcista? (SPY sobre MA200). Devuelve (healthy: bool, score 0-15).

        Robusto ante datos corruptos de yfinance: UNA sola vela basura del índice
        (print erróneo / barra parcial / dato adyacente mal ajustado) NO debe voltear
        el régimen y dejar el dashboard en 'bajista' con 0 candidatos. Pasó el
        27/06/2026: el run leyó cur≈6200 vs MA200≈6900 (score 0.0, 'bajista') cuando
        el ^GSPC estaba realmente ~+7% SOBRE su MA200. El filtro de régimen es lento
        por diseño: ninguna sesión normal mueve el índice >15%, así que un salto así
        es dato corrupto, no mercado."""
        if spy_df is None:
            return True, 7.5
        c = spy_df['Close'].astype(float).dropna()
        if len(c) < 200:
            return True, 7.5
        # Saneado: si el último cierre se desvía >15% de la mediana de los 5 cierres
        # previos (imposible en el S&P en una sesión), se descarta esa vela y se usa
        # el último cierre limpio para decidir el régimen.
        ref = float(c.iloc[-6:-1].median())
        if ref > 0 and abs(c.iloc[-1] / ref - 1) > 0.15:
            c = c.iloc[:-1]
            if len(c) < 200:
                return True, 7.5
        ma200 = float(c.rolling(200).mean().iloc[-1])
        ma50 = float(c.rolling(50).mean().iloc[-1])
        cur = float(c.iloc[-1])
        if cur > ma200:
            pct = (cur - ma200) / ma200 * 100
            score = min(15.0, 8.0 + pct * 0.5 + (3.0 if ma50 > ma200 else 0.0))
            return True, round(score, 1)
        pct = (ma200 - cur) / ma200 * 100
        return False, round(max(0.0, 4.0 - pct * 0.4), 1)
