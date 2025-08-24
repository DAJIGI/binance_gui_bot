# main_gui.py
import tkinter as tk
import threading
import time
from tkinter import ttk, scrolledtext
from binance_client import get_usdt_futures_symbol_info, get_futures_ticker_data

from monitoring_engine import MonitoringEngine

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("바이낸스 선물 자동 알리미")
        self.geometry("1200x720") # 가로 크기 늘림

        # 정렬 상태 변수
        self.sort_column = "No"
        self.sort_reverse = False

        # 엔진 초기화
        self.engine = MonitoringEngine(self)

        # 시세 업데이트 스레드 관련
        self.price_updater_thread = None
        self.price_updater_stop_event = threading.Event()
        self.symbol_item_map = {} # {symbol: item_id}
        self.price_precisions = {} # {symbol: precision}

        # --- 메인 레이아웃 (좌우 분할) ---
        main_paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- 왼쪽 프레임 (코인 목록) ---
        left_frame = ttk.LabelFrame(main_paned_window, text="코인 시세 (3초마다 자동 갱신)", padding="10")
        main_paned_window.add(left_frame, weight=1)

        self.coin_list_tree = ttk.Treeview(
            left_frame,
            columns=("No", "Coin", "Price", "Change", "Volume"),
            show="headings",
            height=25
        )
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.coin_list_tree.yview)
        self.coin_list_tree.configure(yscrollcommand=scrollbar.set)

        # 칼럼 제목 및 정렬 기능 추가
        self.coin_list_tree.heading("No", text="순번", command=lambda: self.sort_treeview_column("No", False))
        self.coin_list_tree.column("No", width=50, anchor=tk.CENTER)
        self.coin_list_tree.heading("Coin", text="코인", command=lambda: self.sort_treeview_column("Coin", False))
        self.coin_list_tree.column("Coin", width=120, anchor=tk.W)
        self.coin_list_tree.heading("Price", text="현재가", command=lambda: self.sort_treeview_column("Price", False))
        self.coin_list_tree.column("Price", width=100, anchor=tk.E)
        self.coin_list_tree.heading("Change", text="등락률", command=lambda: self.sort_treeview_column("Change", False))
        self.coin_list_tree.column("Change", width=80, anchor=tk.E)
        self.coin_list_tree.heading("Volume", text="거래대금($)", command=lambda: self.sort_treeview_column("Volume", True))
        self.coin_list_tree.column("Volume", width=120, anchor=tk.E)
        
        self.coin_list_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


        # --- 오른쪽 프레임 (기존 기능) ---
        right_frame = ttk.Frame(main_paned_window)
        main_paned_window.add(right_frame, weight=2)


        # --- 1. 상태 로그 프레임 ---
        log_frame = ttk.LabelFrame(right_frame, text="상태 로그", padding="10")
        log_frame.pack(fill=tk.X, expand=False, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, expand=True)

        # --- 2. 조건 목록 프레임 ---
        list_frame = ttk.LabelFrame(right_frame, text="알림 조건 목록", padding="10")
        list_frame.pack(fill=tk.X, expand=False, pady=5)

        self.condition_tree = ttk.Treeview(
            list_frame, 
            columns=("Group", "Shift", "Timeframe", "Coin", "Indicator", "Parameters", "Detail", "Operator", "Value"), 
            show="headings",
            height=5
        )
        self.condition_tree.pack(fill=tk.X, expand=True)

        self.condition_tree.heading("Group", text="그룹")
        self.condition_tree.column("Group", width=60, anchor=tk.CENTER)
        self.condition_tree.heading("Shift", text="N봉 전")
        self.condition_tree.column("Shift", width=50, anchor=tk.CENTER)
        self.condition_tree.heading("Timeframe", text="시간봉")
        self.condition_tree.column("Timeframe", width=60, anchor=tk.CENTER)
        self.condition_tree.heading("Coin", text="코인")
        self.condition_tree.column("Coin", width=100, anchor=tk.CENTER)
        self.condition_tree.heading("Indicator", text="지표")
        self.condition_tree.column("Indicator", width=100)
        self.condition_tree.heading("Parameters", text="파라미터")
        self.condition_tree.column("Parameters", width=120)
        self.condition_tree.heading("Detail", text="세부 항목")
        self.condition_tree.column("Detail", width=100)
        self.condition_tree.heading("Operator", text="조건")
        self.condition_tree.column("Operator", width=50, anchor=tk.CENTER)
        self.condition_tree.heading("Value", text="기준값")
        self.condition_tree.column("Value", width=80, anchor=tk.CENTER)

        # --- 3. 조건 추가 프레임 ---
        self.add_condition_frame = ttk.LabelFrame(right_frame, text="조건 추가", padding="10")
        self.add_condition_frame.pack(fill=tk.X, pady=5)
        
        # --- 위젯 데이터 ---
        self.timeframe_options = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
        coin_list, self.price_precisions = get_usdt_futures_symbol_info()
        self.coin_options = ["All Coins"] + coin_list
        self.indicator_options = ["RSI", "Envelope", "BollingerBands", "MASlope", "MA_Compare", "Candle_Trend", "MA_Trend"]
        self.operator_options = [">", ">=", "<", "<=", "=="]

        # --- 위젯 생성 및 배치 ---
        self.add_condition_frame.columnconfigure(1, weight=1)
        self.add_condition_frame.columnconfigure(3, weight=1)

        # 기본 조건 설정
        ttk.Label(self.add_condition_frame, text="시간봉:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.timeframe_combo = ttk.Combobox(self.add_condition_frame, values=self.timeframe_options, state="readonly")
        self.timeframe_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.timeframe_combo.set('5m')

        ttk.Label(self.add_condition_frame, text="코인:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.coin_combo = ttk.Combobox(self.add_condition_frame, values=self.coin_options, state="readonly")
        self.coin_combo.grid(row=0, column=3, padx=5, pady=5, sticky=tk.EW)
        self.coin_combo.set('All Coins')

        ttk.Label(self.add_condition_frame, text="그룹:").grid(row=0, column=4, padx=5, pady=5, sticky=tk.W)
        self.group_entry = ttk.Entry(self.add_condition_frame, width=10)
        self.group_entry.grid(row=0, column=5, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.add_condition_frame, text="N봉 전:").grid(row=1, column=4, padx=5, pady=5, sticky=tk.W)
        self.shift_entry = ttk.Entry(self.add_condition_frame, width=10)
        self.shift_entry.grid(row=1, column=5, padx=5, pady=5, sticky=tk.W)
        self.shift_entry.insert(0, "0")

        ttk.Label(self.add_condition_frame, text="지표:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.indicator_combo = ttk.Combobox(self.add_condition_frame, values=self.indicator_options, state="readonly")
        self.indicator_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.indicator_combo.set("RSI")
        
        ttk.Label(self.add_condition_frame, text="세부 항목:").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.indicator_detail_combo = ttk.Combobox(self.add_condition_frame, state="readonly")
        self.indicator_detail_combo.grid(row=1, column=3, padx=5, pady=5, sticky=tk.EW)

        # 지표 파라미터 프레임
        self.param_frame = ttk.Frame(self.add_condition_frame)
        self.param_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky=tk.EW)
        self.param_widgets = {}

        # 비교 조건 설정
        ttk.Label(self.add_condition_frame, text="조건:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.operator_combo = ttk.Combobox(self.add_condition_frame, values=self.operator_options, state="readonly")
        self.operator_combo.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)
        self.operator_combo.set('>')

        ttk.Label(self.add_condition_frame, text="기준값:").grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
        self.value_entry = ttk.Entry(self.add_condition_frame)
        self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

        # --- 버튼 프레임 (오른쪽에 세로로 배치) ---
        button_frame = ttk.Frame(self.add_condition_frame)
        button_frame.grid(row=0, column=6, rowspan=4, sticky='ns', padx=(10, 0))

        self.add_button = ttk.Button(button_frame, text="추가하기", command=self.add_condition)
        self.add_button.pack(fill='x', pady=2)

        self.modify_button = ttk.Button(button_frame, text="수정하기", command=self.modify_condition, state=tk.DISABLED)
        self.modify_button.pack(fill='x', pady=2)
        
        self.remove_button = ttk.Button(button_frame, text="선택 삭제", command=self.remove_condition)
        self.remove_button.pack(fill='x', pady=2)

        self.clear_button = ttk.Button(button_frame, text="선택 해제", command=self.clear_condition_selection)
        self.clear_button.pack(fill='x', pady=2)

        # 이벤트 바인딩
        self.indicator_combo.bind("<<ComboboxSelected>>", self.update_indicator_details)
        self.condition_tree.bind("<<TreeviewSelect>>", self.on_condition_select)
        
        # --- 4. 제어 프레임 ---
        control_frame = ttk.Frame(right_frame)
        control_frame.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(control_frame, text="모니터링 시작", command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        self.stop_button = ttk.Button(control_frame, text="모니터링 중지", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        # --- 5. 상태 표시줄 프레임 ---
        status_frame = ttk.Frame(self, padding="5")
        status_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False)

        self.progress_label = ttk.Label(status_frame, text="대기 중...")
        self.progress_label.pack(side=tk.LEFT, padx=5)

        self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_indicator_details()
        self.populate_coin_list_table()
        self.start_price_updater()


    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar["maximum"] = total
            self.progress_bar["value"] = current
            self.progress_label.config(text=f"코인 확인 중: {current} / {total}")
        else:
            self.progress_bar["value"] = 0
            self.progress_label.config(text="대기 중...")
        self.update_idletasks() # GUI 업데이트 강제

    def reset_progress(self):
        self.update_progress(0, 0)

    def update_indicator_details(self, event=None):
        # 이전 파라미터 위젯 삭제
        for widget in self.param_frame.winfo_children():
            widget.destroy()
        self.param_widgets = {}

        # 조건 입력 위젯들을 일단 모두 숨김
        self.value_entry.grid_remove()
        if hasattr(self, 'maslope_value_combo'):
            self.maslope_value_combo.grid_remove()
        if hasattr(self, 'price_value_combo'):
            self.price_value_combo.grid_remove()

        # 다른 지표 선택 시, MASlope 전용 이벤트 바인딩 해제
        self.indicator_detail_combo.unbind("<<ComboboxSelected>>")
        self.operator_combo.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)

        indicator = self.indicator_combo.get()
        details = []
        
        # Set operator options based on indicator
        if indicator in ["Candle_Consecutive_Rise", "MA_Consecutive_Rise"]:
            self.operator_combo['values'] = ['==', '>', '>=']
            self.operator_combo.set('==')
        else:
            self.operator_combo['values'] = self.operator_options
            self.operator_combo.set('>')
        
        if indicator == "RSI":
            details = ["RSI Value"]
            self.add_param_entry("Length:", "14")
            self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

        elif indicator in ["Envelope", "BollingerBands"]:
            if not hasattr(self, 'price_value_combo'):
                self.price_value_combo = ttk.Combobox(self.add_condition_frame, state="readonly", width=15, values=["Close", "Open", "High", "Low"])
            self.price_value_combo.set("Close")
            self.price_value_combo.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)
            
            if indicator == "Envelope":
                details = ["Upper Band", "Lower Band", "Middle Band"]
                self.add_param_entry("Length:", "20")
                self.add_param_entry("Percent:", "5")
            else: # BollingerBands
                details = ["Upper Band", "Middle Band", "Lower Band"]
                self.add_param_entry("Length:", "20")
                self.add_param_entry("StdDev:", "2")

        elif indicator == "MASlope":
            details = ["Direction", "Change", "Slope"]
            self.add_param_entry("Length:", "20")
            self.indicator_detail_combo.bind("<<ComboboxSelected>>", self.update_maslope_options)

        elif indicator == "MA_Compare":
            details = ["Percentage"]
            self.add_param_entry("Short MA:", "20")
            self.add_param_entry("Long MA:", "60")
            self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

        elif indicator == "Candle_Trend":
            details = ["Open 상승", "Open 하락", "High 상승", "High 하락", "Low 상승", "Low 하락", "Close 상승", "Close 하락"]
            self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

        elif indicator == "MA_Trend":
            details = ["연속 상승", "연속 하락"]
            self.add_param_entry("Length:", "20")
            self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)
        
        self.indicator_detail_combo['values'] = details
        if details:
            self.indicator_detail_combo.set(details[0])
        else:
            self.indicator_detail_combo.set("")
        
        if indicator == "MASlope":
            self.update_maslope_options()

    def update_maslope_options(self, event=None):
        indicator = self.indicator_combo.get()
        if indicator != "MASlope":
            return

        detail = self.indicator_detail_combo.get()

        # Hide all conditional widgets first
        self.value_entry.grid_remove()
        if hasattr(self, 'maslope_value_combo'):
            self.maslope_value_combo.grid_remove()

        self.operator_combo.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)

        if detail == "Slope":
            self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)
            self.operator_combo.set('>')
        elif detail in ["Direction", "Change"]:
            if not hasattr(self, 'maslope_value_combo'):
                self.maslope_value_combo = ttk.Combobox(self.add_condition_frame, state="readonly", width=15)
            
            if detail == "Direction":
                self.maslope_value_combo['values'] = ["Rising", "Falling"]
                self.maslope_value_combo.set("Rising")
            else: # Change
                self.maslope_value_combo['values'] = ["Turned Up", "Turned Down"]
                self.maslope_value_combo.set("Turned Up")
            
            self.operator_combo.set("==")
            self.maslope_value_combo.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

    def add_param_entry(self, label_text, default_value):
        label = ttk.Label(self.param_frame, text=label_text)
        entry = ttk.Entry(self.param_frame, width=10)
        entry.insert(0, default_value)
        
        col = len(self.param_widgets) * 2
        label.grid(row=0, column=col, padx=5, pady=2)
        entry.grid(row=0, column=col + 1, padx=5, pady=2)
        
        self.param_widgets[label_text.replace(":", "")] = entry

    def _get_condition_data_from_widgets(self):
        group = self.group_entry.get().strip()
        try:
            shift = int(self.shift_entry.get().strip())
        except ValueError:
            self.log("'N봉 전' 값은 숫자(정수)여야 합니다.")
            return None
        timeframe = self.timeframe_combo.get()
        coin = self.coin_combo.get()
        indicator = self.indicator_combo.get()
        detail = self.indicator_detail_combo.get()
        operator = self.operator_combo.get()
        
        value = ""
        if indicator == "MASlope" and detail in ["Direction", "Change"]:
            value = self.maslope_value_combo.get()
        elif indicator in ["Envelope", "BollingerBands"]:
            value = self.price_value_combo.get()
        else:
            value = self.value_entry.get().strip()

        if not value:
             self.log("기준값을 입력해주세요.")
             return None

        params = {}
        for name, widget in self.param_widgets.items():
            params[name.lower()] = widget.get()
        params_str = ", ".join([f"{k}={v}" for k, v in params.items()])

        if not all([timeframe, coin, indicator, detail, operator]):
            self.log("시간봉, 코인, 지표, 세부 항목, 조건은 필수입니다.")
            return None
        
        # 숫자값이어야 하는 조건들에 대해 유효성 검사
        if indicator == "RSI" or (indicator == "MASlope" and detail == "Slope") or indicator == "MA_Compare":
            try:
                float(value)
            except ValueError:
                self.log(f"'{detail}'에 대한 기준값은 숫자여야 합니다.")
                return None
        elif indicator in ["Candle_Trend", "MA_Trend"]:
            try:
                int(value)
            except ValueError:
                self.log(f"'{indicator}'에 대한 기준값은 숫자(정수)여야 합니다.")
                return None

        return (group, shift, timeframe, coin, indicator, params_str, detail, operator, value)

    def add_condition(self):
        condition_data = self._get_condition_data_from_widgets()
        if condition_data:
            self.condition_tree.insert("", tk.END, values=condition_data)
            self.log(f"새 조건 추가: {condition_data}")
            self.clear_condition_selection()

    def modify_condition(self):
        selected_items = self.condition_tree.selection()
        if not selected_items:
            self.log("수정할 조건을 목록에서 선택해주세요.")
            return
        
        condition_data = self._get_condition_data_from_widgets()
        if condition_data:
            self.condition_tree.item(selected_items[0], values=condition_data)
            self.log(f"조건 수정: {condition_data}")
            self.clear_condition_selection()

    def on_condition_select(self, event):
        selected_items = self.condition_tree.selection()
        if selected_items:
            self.load_condition_to_widgets(selected_items[0])
            self.modify_button.config(state=tk.NORMAL)

    def load_condition_to_widgets(self, item_id):
        values = self.condition_tree.item(item_id, 'values')
        group, shift, timeframe, coin, indicator, params_str, detail, operator, value = values

        self.group_entry.delete(0, tk.END)
        self.group_entry.insert(0, group)
        self.shift_entry.delete(0, tk.END)
        self.shift_entry.insert(0, shift)

        # Set the main combos first
        self.timeframe_combo.set(timeframe)
        self.coin_combo.set(coin)
        self.indicator_combo.set(indicator)
        
        # Manually update the details list and available widgets
        self.update_indicator_details()

        # NOW, set the detail for the selected indicator
        self.indicator_detail_combo.set(detail)
        
        # If the indicator is MASlope, the sub-widgets (for value) must be updated again
        # based on the now-correct detail value.
        if indicator == 'MASlope':
            self.update_maslope_options()

        # Set the remaining widgets
        self.operator_combo.set(operator)

        if params_str:
            params = dict(p.split('=') for p in params_str.split(', '))
            for name, widget in self.param_widgets.items():
                if name.lower() in params:
                    widget.delete(0, tk.END)
                    widget.insert(0, params[name.lower()])

        # Set the correct value widget based on the indicator and detail
        if indicator == 'MASlope' and detail in ["Direction", "Change"]:
            self.maslope_value_combo.set(value)
        elif indicator in ["Envelope", "BollingerBands"]:
            self.price_value_combo.set(value)
        else:
            self.value_entry.delete(0, tk.END)
            self.value_entry.insert(0, value)

    def clear_condition_selection(self):
        # Clear selection in the treeview
        if self.condition_tree.selection():
            self.condition_tree.selection_remove(self.condition_tree.selection())
        
        # Reset input widgets to default
        self.timeframe_combo.set('5m')
        self.coin_combo.set('All Coins')
        self.indicator_combo.set('RSI')
        self.update_indicator_details() # This will reset sub-widgets
        self.value_entry.delete(0, tk.END)
        self.group_entry.delete(0, tk.END)
        self.shift_entry.delete(0, tk.END)
        self.shift_entry.insert(0, "0")
        
        # Disable modify button
        self.modify_button.config(state=tk.DISABLED)

    def remove_condition(self):
        selected_items = self.condition_tree.selection()
        if not selected_items:
            self.log("삭제할 조건을 목록에서 선택해주세요.")
            return
        
        for item in selected_items:
            self.condition_tree.delete(item)
            self.log("선택한 조건을 삭제했습니다.")
        self.clear_condition_selection() # 선택 해제 및 폼 초기화

    def log(self, message):
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{now}] {message}\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def start_monitoring(self):
        if not self.get_conditions():
            self.log("알림 조건이 없습니다. 최소 하나 이상의 조건을 추가해주세요.")
            return
        self.engine.start()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

    def stop_monitoring(self):
        self.stop_button.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._threaded_stop, daemon=True)
        thread.start()

    def _threaded_stop(self):
        self.engine.stop()
        self.after(0, self._finalize_stop)

    def _finalize_stop(self):
        self.start_button.config(state=tk.NORMAL)

    def get_conditions(self):
        conditions = []
        for item in self.condition_tree.get_children():
            conditions.append(self.condition_tree.item(item)['values'])
        return conditions

    def on_closing(self):
        self.log("애플리케이션을 종료합니다...")
        self.price_updater_stop_event.set() # 시세 업데이트 스레드 중지
        if self.engine.is_running:
            self.stop_monitoring()
            # Give the stop thread a moment to start and run
            self.after(100, self.destroy)
        else:
            self.destroy()

    def start_price_updater(self):
        """시세 업데이트를 위한 백그라운드 스레드를 시작합니다."""
        self.price_updater_stop_event.clear()
        self.price_updater_thread = threading.Thread(target=self._price_update_loop, daemon=True)
        self.price_updater_thread.start()
        self.log("실시간 시세 업데이트를 시작합니다.")

    def _price_update_loop(self):
        """백그라운드에서 실행되며 주기적으로 시세 데이터를 가져오는 루프."""
        while not self.price_updater_stop_event.is_set():
            try:
                tickers = get_futures_ticker_data()
                if tickers:
                    # GUI 업데이트는 메인 스레드에서 실행하도록 예약
                    self.after(0, self.update_coin_list_table, tickers)
            except Exception as e:
                self.after(0, self.log, f"시세 업데이트 스레드 오류: {e}")
            
            # 3초 대기 (중지 이벤트를 확인하며)
            self.price_updater_stop_event.wait(3)

    def populate_coin_list_table(self):
        """코인 목록을 최초로 한번만 로딩하고, 각 코인의 Treeview item을 맵에 저장합니다."""
        self.log("코인 목록을 최초로 로딩합니다...")
        try:
            # get_usdt_futures_symbol_info()는 심볼 리스트와 정밀도 맵을 모두 반환
            trading_symbols, self.price_precisions = get_usdt_futures_symbol_info()
            trading_symbols = set(trading_symbols)

            tickers = get_futures_ticker_data()
            if not tickers:
                self.log("시세 정보를 가져오지 못했습니다.")
                return

            filtered_tickers = [t for t in tickers if t['symbol'] in trading_symbols]

            for item in self.coin_list_tree.get_children():
                self.coin_list_tree.delete(item)
            self.symbol_item_map.clear()

            self.coin_list_tree.tag_configure("red", foreground="#d1403d")
            self.coin_list_tree.tag_configure("blue", foreground="#0a59f7")

            for i, ticker in enumerate(sorted(filtered_tickers, key=lambda x: float(x.get('quoteVolume', 0)), reverse=True), 1):
                try:
                    symbol = ticker['symbol']
                    price = float(ticker['lastPrice'])
                    change_percent = float(ticker['priceChangePercent'])
                    volume_usd = float(ticker['quoteVolume'])

                    if volume_usd >= 1_000_000_000:
                        volume_str = f"{volume_usd / 1_000_000_000:.2f}B"
                    elif volume_usd >= 1_000_000:
                        volume_str = f"{volume_usd / 1_000_000:.2f}M"
                    else:
                        volume_str = f"{volume_usd / 1_000:.2f}K"

                    color_tag = "normal"
                    if change_percent > 0:
                        color_tag = "red"
                    elif change_percent < 0:
                        color_tag = "blue"
                    
                    precision = self.price_precisions.get(symbol, 4) # 없으면 기본 4자리
                    price_str = f"{price:.{precision}f}"

                    item_id = self.coin_list_tree.insert(
                        "", tk.END,
                        values=(i, symbol, price_str, f"{change_percent:+.2f}%", volume_str),
                        tags=(color_tag,)
                    )
                    self.symbol_item_map[symbol] = item_id
                except (ValueError, KeyError):
                    pass

            self.log(f"거래 가능한 {len(self.symbol_item_map)}개 코인 목록 로딩 완료.")
        except Exception as e:
            self.log(f"초기 코인 목록 로딩 중 오류 발생: {e}")

    def update_coin_list_table(self, tickers):
        """테이블을 다시 만들지 않고 기존 코인 목록의 값만 업데이트합니다."""
        tickers_map = {t['symbol']: t for t in tickers}

        for symbol, item_id in self.symbol_item_map.items():
            ticker = tickers_map.get(symbol)
            if not ticker or not self.coin_list_tree.exists(item_id):
                continue

            try:
                price = float(ticker['lastPrice'])
                change_percent = float(ticker['priceChangePercent'])
                volume_usd = float(ticker['quoteVolume'])

                if volume_usd >= 1_000_000_000:
                    volume_str = f"{volume_usd / 1_000_000_000:.2f}B"
                elif volume_usd >= 1_000_000:
                    volume_str = f"{volume_usd / 1_000_000:.2f}M"
                else:
                    volume_str = f"{volume_usd / 1_000:.2f}K"

                color_tag = "normal"
                if change_percent > 0:
                    color_tag = "red"
                elif change_percent < 0:
                    color_tag = "blue"
                
                current_values = self.coin_list_tree.item(item_id, 'values')
                precision = self.price_precisions.get(symbol, 4)
                price_str = f"{price:.{precision}f}"

                self.coin_list_tree.item(item_id, 
                    values=(current_values[0], current_values[1], price_str, f"{change_percent:+.2f}%", volume_str),
                    tags=(color_tag,)
                )
            except (ValueError, KeyError):
                continue

    def sort_treeview_column(self, col, reverse):
        """Treeview 칼럼을 클릭하여 정렬하는 함수"""
        try:
            data = [(self.coin_list_tree.set(item, col), item) for item in self.coin_list_tree.get_children('')]
        except tk.TclError:
            return

        def sort_key(item):
            value = item[0]
            if col == "No":
                try: return int(value)
                except ValueError: return 0
            if col == "Price" or col == "Change":
                value = value.replace('%', '').replace('+', '')
                try: return float(value)
                except ValueError: return 0.0
            elif col == "Volume":
                value_lower = value.lower()
                num_part = value_lower.replace('k', '').replace('m', '').replace('b', '')
                try:
                    num = float(num_part)
                    if 'b' in value_lower: return num * 1_000_000_000
                    if 'm' in value_lower: return num * 1_000_000
                    if 'k' in value_lower: return num * 1_000
                    return num
                except ValueError: return 0
            return value

        if col == self.sort_column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = reverse

        data.sort(key=sort_key, reverse=self.sort_reverse)

        for index, (val, item) in enumerate(data):
            self.coin_list_tree.move(item, '', index)

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
