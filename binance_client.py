# binance_client.py

from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET

# 바이낸스 클라이언트 객체 생성
try:
    client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
except Exception as e:
    print(f"바이낸스 클라이언트 초기화 실패: {e}")
    client = None

# Exchange 정보 캐싱
_exchange_info_cache = None

def get_usdt_futures_symbol_info():
    """
    USDT 기반의 모든 선물 거래 페어 정보를 반환합니다.
    심볼 리스트와, tickSize를 기반으로 계산된 가격 표시 정밀도 맵을 튜플로 반환합니다.
    """
    global _exchange_info_cache
    if _exchange_info_cache:
        return _exchange_info_cache

    try:
        exchange_info = client.futures_exchange_info()
        symbols = []
        price_precisions = {}
        for s in exchange_info['symbols']:
            if s['quoteAsset'] == 'USDT' and s['contractType'] == 'PERPETUAL' and s['status'] == 'TRADING':
                symbol = s['symbol']
                symbols.append(symbol)
                
                # 필터에서 tickSize를 찾아 표시 정밀도 계산
                tick_size = "0.01" # 기본값
                for f in s['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        tick_size = f['tickSize']
                        break
                
                # tickSize를 바탕으로 소수점 자릿수 계산
                if '.' in tick_size:
                    # rstrip('0')으로 불필요한 0 제거 후, 소수점 이하 자릿수 계산
                    precision = len(tick_size.rstrip('0').split('.')[1])
                else:
                    precision = 0
                price_precisions[symbol] = precision

        print(f"총 {len(symbols)}개의 USDT 선물 코인 및 정밀도 정보를 찾았습니다.")
        _exchange_info_cache = (symbols, price_precisions)
        return symbols, price_precisions
    except Exception as e:
        print(f"바이낸스 선물 코인 정보를 가져오는 데 실패했습니다: {e}")
        return [], {}

def get_usdt_futures_symbols():
    """USDT 기반의 모든 선물 거래 페어 심볼 목록을 반환합니다. (하위 호환성 유지)"""
    symbols, _ = get_usdt_futures_symbol_info()
    return symbols

def get_historical_klines(symbol, interval, limit=100):
    """특정 코인의 지정된 시간봉 과거 캔들 데이터를 가져옵니다."""
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        return klines
    except Exception as e:
        print(f"{symbol} {interval} 캔들 데이터를 가져오는 데 실패했습니다: {e}")
        return []

def get_futures_ticker_data():
    """USDT 기반 모든 선물 코인의 24시간 티커 정보를 가져옵니다."""
    try:
        tickers = client.futures_ticker()
        usdt_tickers = [t for t in tickers if t['symbol'].endswith('USDT')]
        return usdt_tickers
    except Exception as e:
        print(f"바이낸스 선물 티커 정보를 가져오는 데 실패했습니다: {e}")
        return []

if __name__ == '__main__':
    # 파일 단독 실행 시 테스트
    print("USDT 선물 코인 정보 테스트:")
    symbols, precisions = get_usdt_futures_symbol_info()
    if symbols:
        print("코인 목록 (처음 5개):", symbols[:5])
        # BTC, ETH, QNT, XNY(가상)의 정밀도 출력 테스트
        test_symbols = ['BTCUSDT', 'ETHUSDT', 'QNTUSDT', 'XRPUSDT']
        test_precisions = {s: precisions.get(s) for s in test_symbols if s in precisions}
        print(f"주요 코인 표시 정밀도: {test_precisions}")

        print("\nBTCUSDT 15분봉 데이터 (일부):")
        klines = get_historical_klines('BTCUSDT', '15m')
        if klines:
            print(klines[0])
