# binance_client.py

from binance.client import Client
from config import BINANCE_API_KEY, BINANCE_API_SECRET

# 바이낸스 클라이언트 객체 생성
try:
    client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
except Exception as e:
    print(f"바이낸스 클라이언트 초기화 실패: {e}")
    client = None


def get_usdt_futures_symbols():
    """USDT 기반의 모든 선물 거래 페어 심볼 목록을 반환합니다."""
    try:
        exchange_info = client.futures_exchange_info()
        symbols = [s['symbol'] for s in exchange_info['symbols'] 
                   if s['quoteAsset'] == 'USDT' and s['contractType'] == 'PERPETUAL']
        print(f"총 {len(symbols)}개의 USDT 선물 코인을 찾았습니다.")
        return symbols
    except Exception as e:
        print(f"바이낸스 선물 코인 목록을 가져오는 데 실패했습니다: {e}")
        return []

def get_historical_klines(symbol, interval, limit=100):
    """특정 코인의 지정된 시간봉 과거 캔들 데이터를 가져옵니다."""
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        return klines
    except Exception as e:
        print(f"{symbol} {interval} 캔들 데이터를 가져오는 데 실패했습니다: {e}")
        return []

if __name__ == '__main__':
    # 파일 단독 실행 시 테스트
    print("USDT 선물 코인 목록:")
    symbols = get_usdt_futures_symbols()
    if symbols:
        print(symbols[:5]) # 처음 5개만 출력

        print("\nBTCUSDT 15분봉 데이터 (일부):")
        klines = get_historical_klines('BTCUSDT', '15m')
        if klines:
            print(klines[0]) # 첫번째 캔들 데이터 출력
