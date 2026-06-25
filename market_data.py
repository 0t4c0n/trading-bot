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

    # --- Salud del mercado ---
    def check_market_health(self, spy_df):
        """¿Mercado alcista? (SPY sobre MA200). Devuelve (healthy: bool, score 0-15)."""
        if spy_df is None or len(spy_df) < 200:
            return True, 7.5
        c = spy_df['Close'].astype(float)
        ma200 = float(c.rolling(200).mean().iloc[-1])
        ma50 = float(c.rolling(50).mean().iloc[-1])
        cur = float(c.iloc[-1])
        if cur > ma200:
            pct = (cur - ma200) / ma200 * 100
            score = min(15.0, 8.0 + pct * 0.5 + (3.0 if ma50 > ma200 else 0.0))
            return True, round(score, 1)
        pct = (ma200 - cur) / ma200 * 100
        return False, round(max(0.0, 4.0 - pct * 0.4), 1)
