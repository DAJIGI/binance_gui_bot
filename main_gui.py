# main_gui.py
import tkinter as tk
from tkinter import ttk, scrolledtext
from binance_client import get_usdt_futures_symbols

from monitoring_engine import MonitoringEngine

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("바이낸스 선물 자동 알리미")
        self.geometry("800x680") # 세로 길이 약간 늘림

        # 엔진 초기화
        self.engine = MonitoringEngine(self)


        # 메인 프레임
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- 1. 상태 로그 프레임 (가장 먼저 생성) ---
        log_frame = ttk.LabelFrame(main_frame, text="상태 로그", padding="10")
        log_frame.pack(fill=tk.X, expand=False, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.X, expand=True)

        # --- 2. 조건 목록 프레임 ---
        list_frame = ttk.LabelFrame(main_frame, text="알림 조건 목록", padding="10")
        list_frame.pack(fill=tk.X, expand=False, pady=5)

        self.condition_tree = ttk.Treeview(
            list_frame, 
            columns=("Timeframe", "Coin", "Indicator", "Parameters", "Detail", "Operator", "Value"), 
            show="headings",
            height=5
        )
        self.condition_tree.pack(fill=tk.X, expand=True)

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
        add_condition_frame = ttk.LabelFrame(main_frame, text="조건 추가", padding="10")
        add_condition_frame.pack(fill=tk.X, pady=5)
        
        # --- 위젯 데이터 ---
        self.timeframe_options = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d']
        coin_list = get_usdt_futures_symbols()
        self.coin_options = ["All Coins"] + coin_list
        self.indicator_options = ["RSI", "Envelope", "BollingerBands"]
        self.operator_options = [">", ">=", "<", "<=", "=="]

        # --- 위젯 생성 및 배치 ---
        add_condition_frame.columnconfigure(1, weight=1)
        add_condition_frame.columnconfigure(3, weight=1)

        # 기본 조건 설정
        ttk.Label(add_condition_frame, text="시간봉:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.timeframe_combo = ttk.Combobox(add_condition_frame, values=self.timeframe_options, state="readonly")
        self.timeframe_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        self.timeframe_combo.set('5m')

        ttk.Label(add_condition_frame, text="코인:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.coin_combo = ttk.Combobox(add_condition_frame, values=self.coin_options, state="readonly")
        self.coin_combo.grid(row=0, column=3, padx=5, pady=5, sticky=tk.EW)
        self.coin_combo.set('All Coins')

        ttk.Label(add_condition_frame, text="지표:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.indicator_combo = ttk.Combobox(add_condition_frame, values=self.indicator_options, state="readonly")
        self.indicator_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        self.indicator_combo.set("RSI")
        
        ttk.Label(add_condition_frame, text="세부 항목:").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        self.indicator_detail_combo = ttk.Combobox(add_condition_frame, state="readonly")
        self.indicator_detail_combo.grid(row=1, column=3, padx=5, pady=5, sticky=tk.EW)

        # 지표 파라미터 프레임
        self.param_frame = ttk.Frame(add_condition_frame)
        self.param_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky=tk.EW)
        self.param_widgets = {}

        # 비교 조건 설정
        ttk.Label(add_condition_frame, text="조건:").grid(row=3, column=0, padx=5, pady=5, sticky=tk.W)
        self.operator_combo = ttk.Combobox(add_condition_frame, values=self.operator_options, state="readonly")
        self.operator_combo.grid(row=3, column=1, padx=5, pady=5, sticky=tk.EW)
        self.operator_combo.set('>')

        ttk.Label(add_condition_frame, text="기준값:").grid(row=3, column=2, padx=5, pady=5, sticky=tk.W)
        self.value_entry = ttk.Entry(add_condition_frame)
        self.value_entry.grid(row=3, column=3, padx=5, pady=5, sticky=tk.EW)

        # 버튼
        self.add_button = ttk.Button(add_condition_frame, text="추가하기", command=self.add_condition)
        self.add_button.grid(row=3, column=4, padx=5, pady=5, sticky=tk.E)
        
        self.remove_button = ttk.Button(add_condition_frame, text="선택 삭제", command=self.remove_condition)
        self.remove_button.grid(row=3, column=5, padx=5, pady=5, sticky=tk.E)

        self.indicator_combo.bind("<<ComboboxSelected>>", self.update_indicator_details)
        
        # --- 4. 제어 프레임 ---
        control_frame = ttk.Frame(main_frame)
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

        indicator = self.indicator_combo.get()
        details = []
        
        if indicator == "RSI":
            details = ["RSI Value"]
            self.add_param_entry("Length:", "14")
        elif indicator == "Envelope":
            details = ["Upper Band", "Lower Band", "Price"]
            self.add_param_entry("Length:", "20")
            self.add_param_entry("Percent:", "5")
        elif indicator == "BollingerBands":
            details = ["Upper Band", "Middle Band", "Lower Band", "Price"]
            self.add_param_entry("Length:", "20")
            self.add_param_entry("StdDev:", "2")
        
        self.indicator_detail_combo['values'] = details
        if details:
            self.indicator_detail_combo.set(details[0])
        else:
            self.indicator_detail_combo.set("")

    def add_param_entry(self, label_text, default_value):
        label = ttk.Label(self.param_frame, text=label_text)
        entry = ttk.Entry(self.param_frame, width=10)
        entry.insert(0, default_value)
        
        col = len(self.param_widgets) * 2
        label.grid(row=0, column=col, padx=5, pady=2)
        entry.grid(row=0, column=col + 1, padx=5, pady=2)
        
        self.param_widgets[label_text.replace(":", "")] = entry

    def add_condition(self):
        timeframe = self.timeframe_combo.get()
        coin = self.coin_combo.get()
        indicator = self.indicator_combo.get()
        detail = self.indicator_detail_combo.get()
        operator = self.operator_combo.get()
        value = self.value_entry.get().strip()

        # 기준값이 비어 있으면 'price'로 간주
        if not value:
            value = 'price'

        params = {}
        for name, widget in self.param_widgets.items():
            params[name.lower()] = widget.get()
        
        params_str = ", ".join([f"{k}={v}" for k, v in params.items()])

        if not all([timeframe, coin, indicator, detail, operator]):
            self.log("시간봉, 코인, 지표, 세부 항목, 조건은 필수입니다.")
            return
        
        # 값 유효성 검사 (숫자 또는 'price')
        if value.lower() != 'price':
            try:
                float(value)
            except ValueError:
                self.log("기준값은 숫자이거나 비워두어야 합니다(현재가 비교).")
                return

        condition_data = (timeframe, coin, indicator, params_str, detail, operator, value)
        self.condition_tree.insert("", tk.END, values=condition_data)
        self.log(f"새 조건 추가: {condition_data}")
        # 추가 후 입력 필드 초기화
        self.value_entry.delete(0, tk.END)

    def remove_condition(self):
        selected_items = self.condition_tree.selection()
        if not selected_items:
            self.log("삭제할 조건을 목록에서 선택해주세요.")
            return
        
        for item in selected_items:
            self.condition_tree.delete(item)
            self.log("선택한 조건을 삭제했습니다.")

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
        self.engine.stop()
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def get_conditions(self):
        conditions = []
        for item in self.condition_tree.get_children():
            conditions.append(self.condition_tree.item(item)['values'])
        return conditions

    def on_closing(self):
        self.log("애플리케이션을 종료합니다...")
        self.stop_monitoring()
        self.destroy()

if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception as e:
        print(f"App 객체 생성 또는 mainloop 실행 중 오류 발생: {e}")