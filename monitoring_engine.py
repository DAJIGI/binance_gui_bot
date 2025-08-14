# monitoring_engine.py
import time
import threading
import pandas as pd
import pandas_ta as ta
import math
from binance.exceptions import BinanceAPIException

from binance_client import get_usdt_futures_symbols, get_historical_klines
from telegram_notifier import send_telegram_message

def parse_params(params_str):
    """'length=14, std=2' 같은 문자열을 {'length': 14, 'std': 2} 딕셔너리로 변환"""
    if not params_str:
        return {}
    params = {}
    for p in params_str.split(','):
        try:
            key, value = p.strip().split('=')
            # 값을 적절한 타입으로 변환 (정수, 실수)
            if '.' in value:
                params[key] = float(value)
            else:
                params[key] = int(value)
        except ValueError:
            # 변환 실패 시 원본 문자열을 유지하거나 다른 처리를 할 수 있습니다.
            # 여기서는 일단 건너뜁니다.
            pass
    return params

class MonitoringEngine:
    def __init__(self, app):
        self.app = app
        self.is_running = False
        self.thread = None
        self.last_alert_times = {}

    def start(self):
        if self.is_running:
            self.app.log("모니터링이 이미 실행 중입니다.")
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.app.log("모니터링을 시작합니다.")

    def stop(self):
        if not self.is_running:
            self.app.log("모니터링이 이미 중지되어 있습니다.")
            return
        self.is_running = False
        self.app.log("모니터링을 중지합니다.")
        self.app.reset_progress()

    def run(self):
        """메인 모니터링 루프"""
        all_symbols = get_usdt_futures_symbols()
        
        while self.is_running:
            met_conditions_details_in_cycle = []
            try:
                conditions = self.app.get_conditions()
                if not conditions:
                    self.app.log("감시할 조건이 없습니다. 30초 후에 다시 확인합니다.")
                    self.app.reset_progress()
                    time.sleep(30)
                    continue

                # 전체 검사할 코인 수 계산 (중복 제거)
                symbols_to_check_in_cycle = set()
                for cond in conditions:
                    _, coin, _, _, _, _, _ = cond
                    if coin == "All Coins":
                        symbols_to_check_in_cycle.update(all_symbols)
                    else:
                        symbols_to_check_in_cycle.add(coin)
                total_count = len(symbols_to_check_in_cycle)
                self.app.update_progress(0, total_count)

                # 실제 검사 시작
                checked_count = 0
                for symbol in sorted(list(symbols_to_check_in_cycle)):
                    if not self.is_running: break
                    
                    checked_count += 1
                    self.app.update_progress(checked_count, total_count)

                    if checked_count % 50 == 0:
                        time.sleep(0.5)

                    for cond in conditions:
                        timeframe, coin_cond, indicator, params_str, detail, operator, value_str = cond
                        if coin_cond == symbol or coin_cond == "All Coins":
                            try:
                                self.check_condition(symbol, timeframe, indicator, params_str, detail, operator, value_str, met_conditions_details_in_cycle)
                            except BinanceAPIException as e:
                                if e.code == -1003:
                                    self.app.log(f"[경고] Rate Limit. 1분간 대기합니다: {e}")
                                    time.sleep(60)
                                else:
                                    self.app.log(f"[오류] 바이낸스 API: {e}")
                            except Exception as e:
                                self.app.log(f"[{symbol}] 조건 확인 중 오류: {e}")
                
                if not self.is_running: break
                
                if met_conditions_details_in_cycle:
                    TELEGRAM_MAX_MESSAGE_LENGTH = 4000
                    grouped_messages = {}
                    for item in met_conditions_details_in_cycle:
                        condition_key = item['full_condition'].split('(')[0].strip()
                        if condition_key not in grouped_messages:
                            grouped_messages[condition_key] = []
                        grouped_messages[condition_key].append(f"- {item['symbol']} ({item['timeframe']}): {item['full_condition']}")

                    for condition_key, details in grouped_messages.items():
                        message_header = f"[{condition_key} 조건 만족 코인]\n---\n"
                        current_message_part = message_header
                        for line in details:
                            if len(current_message_part) + len(line) + 1 > TELEGRAM_MAX_MESSAGE_LENGTH:
                                send_telegram_message(current_message_part)
                                current_message_part = message_header
                            current_message_part += line + "\n"
                        send_telegram_message(current_message_part)
                    self.app.log(f"이번 사이클에서 {len(met_conditions_details_in_cycle)}개 조건 만족. 텔레그램 알림 전송.")
                else:
                    self.app.log("이번 사이클에서 조건을 만족하는 코인이 없습니다.")

                self.app.log(f"모든 조건 확인 완료. 다음 확인까지 30초 대기...")
                self.app.reset_progress()
                time.sleep(30)

            except Exception as e:
                self.app.log(f"모니터링 루프 오류: {e}")
                self.app.reset_progress()
                time.sleep(60)

    def check_condition(self, symbol, timeframe, indicator, params_str, detail, operator, value_str, met_conditions_details_in_cycle):
        """개별 코인에 대한 조건을 확인하고 만족 시 알림 목록에 추가합니다."""
        alert_key = f"{symbol}|{timeframe}|{indicator}|{params_str}|{detail}|{operator}|{value_str}"
        now = time.time()
        if now - self.last_alert_times.get(alert_key, 0) < 300:
            return

        klines = get_historical_klines(symbol, timeframe, limit=200)
        if not klines or len(klines) < 50:
            return

        df = pd.DataFrame(klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        for col in ['close', 'high', 'low']:
            df[col] = pd.to_numeric(df[col])

        params = parse_params(params_str)
        
        indicator_value = None
        indicator_col_name = ""
        
        try:
            if indicator == "RSI":
                df.ta.rsi(length=params.get('length', 14), append=True)
                indicator_col_name = df.columns[-1]
            elif indicator == "Envelope":
                length = params.get('length', 20)
                percent = params.get('percent', 5) / 100.0
                sma = df['close'].rolling(window=length).mean()
                df['ENV_UPPER'] = sma * (1 + percent)
                df['ENV_LOWER'] = sma * (1 - percent)
                if "Upper" in detail:
                    indicator_col_name = 'ENV_UPPER'
                else:
                    indicator_col_name = 'ENV_LOWER'

            elif indicator == "BollingerBands":
                df.ta.bbands(length=params.get('length', 20), std=params.get('stddev', 2), append=True)
                # pandas-ta may generate slightly different column names, find it dynamically
                for col in df.columns:
                    if col.startswith("BBU_") and "Upper" in detail:
                        indicator_col_name = col
                        break
                    elif col.startswith("BBM_") and "Middle" in detail:
                        indicator_col_name = col
                        break
                    elif col.startswith("BBL_") and "Lower" in detail:
                        indicator_col_name = col
                        break
            
            if indicator_col_name and indicator_col_name in df.columns:
                indicator_value = df[indicator_col_name].iloc[-1]
            elif detail != 'Price': # 'Price' detail doesn't need an indicator value
                return
        except Exception as e:
            self.app.log(f"[{symbol}] 지표 계산 오류: {e}")
            return

        if indicator_value is not None and math.isnan(indicator_value):
            return

        current_price = df['close'].iloc[-1]
        
        lhs_val, rhs_val = None, None
        display_lhs, display_rhs = "", ""

        if detail == 'Price':
            lhs_val = current_price
            display_lhs = f"현재가({lhs_val:.4f})"
        else:
            lhs_val = indicator_value
            display_lhs = f"{indicator}({lhs_val:.4f})"

        if str(value_str).lower() == 'price':
            rhs_val = current_price
            display_rhs = f"현재가({rhs_val:.4f})"
        else:
            try:
                rhs_val = float(value_str)
                display_rhs = value_str
            except ValueError:
                return

        if lhs_val is None or rhs_val is None:
            return

        condition_met = False
        try:
            condition_met = eval(f"{lhs_val} {operator} {rhs_val}")
        except Exception as e:
            self.app.log(f"[{symbol}] 조건 평가식 오류: {e}")
            return

        if condition_met:
            full_display_str = f"{display_lhs} {operator} {display_rhs}"
            self.app.log(f"[조건 만족] {symbol} ({timeframe}) - {full_display_str}")
            self.last_alert_times[alert_key] = now
            met_conditions_details_in_cycle.append({
                'symbol': symbol,
                'timeframe': timeframe,
                'full_condition': full_display_str
            })
