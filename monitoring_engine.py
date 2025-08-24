# monitoring_engine.py
import time
import threading
import pandas as pd
import pandas_ta as ta
import math
import numpy as np
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
            pass
    return params

class MonitoringEngine:
    def __init__(self, app):
        self.app = app
        self.is_running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.last_alert_times = {}

    def start(self):
        if self.is_running:
            self.app.log("모니터링이 이미 실행 중입니다.")
            return
        
        self.stop_event.clear()
        self.is_running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.app.log("모니터링을 시작합니다.")

    def stop(self):
        if not self.is_running:
            self.app.log("모니터링이 이미 중지되어 있습니다.")
            return
        
        self.is_running = False
        self.stop_event.set() # 잠든 스레드를 즉시 깨움
        if self.thread and self.thread.is_alive():
            self.thread.join() # 스레드가 완전히 종료될 때까지 대기
        
        self.app.log("모니터링을 중지합니다.")
        self.app.reset_progress()

    def run(self):
        """메인 모니터링 루프"""
        all_symbols = get_usdt_futures_symbols()
        
        while self.is_running:
            final_alert_messages = []
            now = time.time()
            try:
                conditions = self.app.get_conditions()
                if not conditions:
                    self.app.log("감시할 조건이 없습니다. 30초 후에 다시 확인합니다.")
                    self.app.reset_progress()
                    if self.stop_event.wait(timeout=30): break
                    continue

                # 조건들을 그룹별로 분류
                grouped_conditions = {}
                individual_conditions = []
                symbols_to_check_in_cycle = set()

                for cond in conditions:
                    group, shift, timeframe, coin, indicator, params_str, detail, operator, value_str = cond
                    
                    if coin == "All Coins":
                        symbols_to_check_in_cycle.update(all_symbols)
                    else:
                        symbols_to_check_in_cycle.add(coin)

                    condition_data = (shift, timeframe, coin, indicator, params_str, detail, operator, value_str)
                    if group:
                        if group not in grouped_conditions:
                            grouped_conditions[group] = []
                        grouped_conditions[group].append(condition_data)
                    else:
                        individual_conditions.append(condition_data)

                total_count = len(symbols_to_check_in_cycle)
                self.app.update_progress(0, total_count)
                checked_count = 0

                for symbol in sorted(list(symbols_to_check_in_cycle)):
                    if not self.is_running: break
                    checked_count += 1
                    self.app.update_progress(checked_count, total_count)
                    if checked_count % 50 == 0: time.sleep(0.5)

                    # 1. 개별 조건 확인
                    for cond_data in individual_conditions:
                        if not self.is_running: break
                        shift, timeframe, coin_cond, indicator, params_str, detail, operator, value_str = cond_data
                        if coin_cond == symbol or coin_cond == "All Coins":
                            alert_key = f"{symbol}|{shift}|{timeframe}|{indicator}|{params_str}|{detail}|{operator}|{value_str}"
                            if now - self.last_alert_times.get(alert_key, 0) < 300:
                                continue
                            try:
                                is_met, display_str = self.check_condition(symbol, timeframe, indicator, params_str, detail, operator, value_str, shift)
                                if is_met:
                                    final_alert_messages.append(f"- {symbol} ({timeframe}, {shift}봉 전): {display_str}")
                                    self.last_alert_times[alert_key] = now
                            except Exception as e:
                                self.app.log(f"[{symbol}] 개별 조건 확인 중 오류: {e}")

                    # 2. 그룹 조건 확인
                    for group_name, group_conds in grouped_conditions.items():
                        if not self.is_running: break
                        
                        first_cond_coin = group_conds[0][2]
                        if first_cond_coin != symbol and first_cond_coin != "All Coins":
                            continue

                        group_alert_key = f"{symbol}|{group_name}"
                        if now - self.last_alert_times.get(group_alert_key, 0) < 300:
                            continue

                        all_conditions_in_group_met = True
                        group_display_strs = []
                        
                        for cond_data in group_conds:
                            shift, timeframe, _, indicator, params_str, detail, operator, value_str = cond_data
                            try:
                                is_met, display_str = self.check_condition(symbol, timeframe, indicator, params_str, detail, operator, value_str, shift)
                                if not is_met:
                                    all_conditions_in_group_met = False
                                    break 
                                group_display_strs.append(f"  - ({timeframe}, {shift}봉 전) {display_str}")
                            except Exception as e:
                                self.app.log(f"[{symbol}] 그룹 '{group_name}' 조건 확인 중 오류: {e}")
                                all_conditions_in_group_met = False
                                break
                        
                        if all_conditions_in_group_met:
                            alert_message = f"그룹 '{group_name}' 조건 동시 만족!\n- {symbol}\n" + "\n".join(group_display_strs)
                            final_alert_messages.append(alert_message)
                            self.last_alert_times[group_alert_key] = now

                    if not self.is_running: break
                
                if not self.is_running: break
                
                if final_alert_messages:
                    TELEGRAM_MAX_MESSAGE_LENGTH = 4000
                    message_header = f"[조건 만족 코인 알림]\n---\n"
                    current_message_part = message_header
                    
                    for line in final_alert_messages:
                        if len(current_message_part) + len(line) + 2 > TELEGRAM_MAX_MESSAGE_LENGTH:
                            send_telegram_message(current_message_part)
                            current_message_part = message_header
                        current_message_part += line + "\n\n"
                    
                    if current_message_part != message_header:
                        send_telegram_message(current_message_part)
                    
                    self.app.log(f"이번 사이클에서 {len(final_alert_messages)}개 알림 발생. 텔레그램 전송 완료.")
                else:
                    self.app.log("이번 사이클에서 조건을 만족하는 코인이 없습니다.")

                self.app.log(f"모든 조건 확인 완료. 다음 확인까지 30초 대기...")
                self.app.reset_progress()
                if self.stop_event.wait(timeout=30): break

            except Exception as e:
                import traceback
                self.app.log(f"모니터링 루프 오류: {traceback.format_exc()}")
                self.app.reset_progress()
                if self.stop_event.wait(timeout=60): break

    def check_condition(self, symbol, timeframe, indicator, params_str, detail, operator, value_str, shift=0):
        """개별 코인에 대한 조건을 확인하고 (만족 여부, 결과 문자열)을 반환합니다."""
        klines = get_historical_klines(symbol, timeframe, limit=200)
        if not klines or len(klines) < 50:
            return False, ""

        # shift 값 유효성 검사
        if not (0 <= shift < len(klines) - 5): # 최소 5개 캔들은 확보
            return False, ""

        df = pd.DataFrame(klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        for col in ['close', 'high', 'low', 'open']:
            df[col] = pd.to_numeric(df[col])

        params = parse_params(params_str)
        condition_met = False
        full_display_str = ""

        # ... (기존 지표 계산 로직)
        if indicator in ["RSI", "Envelope", "BollingerBands"]:
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
                    df['ENV_MIDDLE'] = sma
                    if "Upper" in detail: indicator_col_name = 'ENV_UPPER'
                    elif "Lower" in detail: indicator_col_name = 'ENV_LOWER'
                    elif "Middle" in detail: indicator_col_name = 'ENV_MIDDLE'
                elif indicator == "BollingerBands":
                    df.ta.bbands(length=params.get('length', 20), std=params.get('stddev', 2), append=True)
                    for col in df.columns:
                        if col.startswith("BBU_") and "Upper" in detail: indicator_col_name = col; break
                        elif col.startswith("BBM_") and "Middle" in detail: indicator_col_name = col; break
                        elif col.startswith("BBL_") and "Lower" in detail: indicator_col_name = col; break
                
                if indicator_col_name and indicator_col_name in df.columns:
                    indicator_value = df[indicator_col_name].iloc[-1 - shift]
                else: return False, ""

            except Exception as e:
                self.app.log(f"[{symbol}] 지표 계산 오류: {e}")
                return False, ""

            if indicator_value is not None and math.isnan(indicator_value): return False, ""

            lhs_val = indicator_value
            display_lhs = f"{indicator} {detail}({lhs_val:.4f})"

            rhs_val = None
            display_rhs = ""
            
            value_str_lower = str(value_str).lower()
            if value_str_lower in ["open", "high", "low", "close"]:
                rhs_val = df[value_str_lower].iloc[-1 - shift]
                display_rhs = f"{value_str}({rhs_val:.4f})"
            else:
                try: 
                    rhs_val = float(value_str)
                    display_rhs = value_str
                except ValueError: return False, ""

            if lhs_val is None or rhs_val is None: return False, ""
            
            eval_str = f"{lhs_val} {operator} {rhs_val}"
            condition_met = eval(eval_str)
            full_display_str = f"{display_lhs} {operator} {display_rhs}"

        elif indicator == "MASlope":
            length = params.get('length', 20)
            ma_series = df.ta.sma(length=length)
            if ma_series is None or len(ma_series) < 3 + shift: return False, ""

            ma_val_1 = ma_series.iloc[-1 - shift]
            ma_val_2 = ma_series.iloc[-2 - shift]
            ma_val_3 = ma_series.iloc[-3 - shift]

            if detail == "Direction":
                if value_str == "Rising" and ma_val_1 > ma_val_2: condition_met = True
                elif value_str == "Falling" and ma_val_1 < ma_val_2: condition_met = True
                full_display_str = f"MA({length}) {value_str}"

            elif detail == "Change":
                if value_str == "Turned Up" and ma_val_1 > ma_val_2 and ma_val_2 < ma_val_3: condition_met = True
                elif value_str == "Turned Down" and ma_val_1 < ma_val_2 and ma_val_2 > ma_val_3: condition_met = True
                full_display_str = f"MA({length}) {value_str}"

            elif detail == "Slope":
                if ma_val_1 == 0: return False, ""
                y = ma_series.iloc[-3 - shift:-1 - shift].values if shift > 0 else ma_series.tail(3).values
                x = np.arange(len(y))
                slope, _ = np.polyfit(x, y, 1)
                percent_slope = (slope / ma_val_1) * 100
                try: 
                    target_percent_slope = float(value_str)
                    condition_met = eval(f"{percent_slope} {operator} {target_percent_slope}")
                    full_display_str = f"MA({length}) Slope({percent_slope:.4f}%) {operator} {target_percent_slope}%"
                except (ValueError, TypeError): return False, ""

        elif indicator == "MA_Compare":
            short_length = params.get('short ma', 20)
            long_length = params.get('long ma', 60)
            short_ma = df.ta.sma(length=short_length)
            long_ma = df.ta.sma(length=long_length)
            if short_ma is None or long_ma is None or len(short_ma) < 1 + shift or len(long_ma) < 1 + shift: return False, ""
            short_ma_val = short_ma.iloc[-1 - shift]
            long_ma_val = long_ma.iloc[-1 - shift]
            if long_ma_val == 0: return False, ""
            percentage_diff = ((short_ma_val - long_ma_val) / long_ma_val) * 100
            try:
                target_percentage = float(value_str)
                condition_met = eval(f"{percentage_diff} {operator} {target_percentage}")
                full_display_str = f"MA({short_length}) vs MA({long_length}) Diff({percentage_diff:.2f}%) {operator} {target_percentage}%"
            except (ValueError, TypeError): return False, ""

        elif indicator == "Candle_Trend":
            try:
                n = int(value_str)
                price_series_key = detail.split(' ')[0].lower()
                price_series = df[price_series_key]
                
                if len(price_series) < 2 + shift:
                    return False, ""

                count = 0
                for i in range(len(price_series) - 1 - shift):
                    current_index = -1 - shift - i
                    previous_index = -2 - shift - i
                    if current_index < -len(price_series) or previous_index < -len(price_series):
                        break
                    
                    # 연속 상승 또는 하락 확인
                    if "상승" in detail and price_series.iloc[current_index] > price_series.iloc[previous_index]:
                        count += 1
                    elif "하락" in detail and price_series.iloc[current_index] < price_series.iloc[previous_index]:
                        count += 1
                    else:
                        break
                
                if eval(f"{count} {operator} {n}"):
                    condition_met = True
                    trend_type = "상승" if "상승" in detail else "하락"
                    full_display_str = f"{detail.replace(trend_type, '').strip()} {count}봉 연속 {trend_type}"

            except (ValueError, IndexError): return False, ""

        elif indicator == "MA_Trend":
            try:
                n = int(value_str)
                length = params.get('length', 20)
                if len(df) < length + n + shift:
                    return False, ""

                ma_series = df.ta.sma(length=length)
                if ma_series is None or len(ma_series) < 2 + shift:
                    return False, ""

                count = 0
                for i in range(len(ma_series) - 1 - shift):
                    current_index = -1 - shift - i
                    previous_index = -2 - shift - i
                    if current_index < -len(ma_series) or previous_index < -len(ma_series):
                        break
                    
                    current_val = ma_series.iloc[current_index]
                    previous_val = ma_series.iloc[previous_index]

                    if pd.isna(current_val) or pd.isna(previous_val):
                        break

                    if detail == "연속 상승" and current_val > previous_val:
                        count += 1
                    elif detail == "연속 하락" and current_val < previous_val:
                        count += 1
                    else:
                        break
                
                if eval(f"{count} {operator} {n}"):
                    condition_met = True
                    trend_type = "상승" if detail == "연속 상승" else "하락"
                    full_display_str = f"MA({length}) {count}봉 연속 {trend_type}"
            except (ValueError, IndexError): return False, ""

        if condition_met:
            self.app.log(f"[조건 만족] {symbol} ({timeframe}, {shift}봉 전) - {full_display_str}")
            return True, full_display_str
        
        return False, ""