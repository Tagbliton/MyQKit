import json
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import ttk
import pandas as pd
import requests

# API配置
ALLTICK_TOKEN = "YOUR TOKEN"

# K线类型映射表 (Alltick API kline_type 映射)
KLINE_TYPES = {
    "1分钟": 1,
    "5分钟": 2,
    "15分钟": 3,
    "30分钟": 4,
    "1小时": 5,
    "1日": 6,
}


class AlltickApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Alltick 数据抓取")
        self.geometry("280x210")
        self.resizable(False, False)

        self.is_running = False
        self.polling_thread = None

        self._init_ui()

    def _init_ui(self):
        # 紧凑型参数设置区域
        frame_input = ttk.LabelFrame(self, text="参数设置", padding=(8, 4))
        frame_input.pack(fill="x", padx=8, pady=4)

        # 1. 股票代码
        ttk.Label(frame_input, text="代码:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.entry_symbol = ttk.Entry(frame_input, width=14)
        self.entry_symbol.insert(0, "000001.SH")
        self.entry_symbol.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        # 2. K线周期
        ttk.Label(frame_input, text="周期:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.combo_kline = ttk.Combobox(
            frame_input,
            values=list(KLINE_TYPES.keys()),
            state="readonly",
            width=12,
        )
        self.combo_kline.set("15分钟")
        self.combo_kline.grid(row=1, column=1, sticky="w", pady=2, padx=5)

        # 3. 轮询延迟(秒)
        ttk.Label(frame_input, text="间隔(秒):").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.entry_interval = ttk.Entry(frame_input, width=14)
        self.entry_interval.insert(0, "10")
        self.entry_interval.grid(row=2, column=1, sticky="w", pady=2, padx=5)

        # 控制按钮区域
        frame_btn = ttk.Frame(self)
        frame_btn.pack(fill="x", padx=8, pady=4)

        self.btn_toggle = ttk.Button(
            frame_btn, text="开始获取", command=self.toggle_fetching
        )
        self.btn_toggle.pack(fill="x")

        # 底部微型运行状态栏
        self.lbl_status = ttk.Label(
            self,
            text="状态: 待机",
            font=("Microsoft YaHei", 8),
            foreground="#666666",
        )
        self.lbl_status.pack(side="bottom", anchor="w", padx=6, pady=2)

    def update_status(self, text, is_error=False):
        """更新 UI 最底部的状态提示"""
        color = "#d9534f" if is_error else "#666666"
        self.lbl_status.config(text=f"状态: {text}", foreground=color)

    def toggle_fetching(self):
        if not self.is_running:
            # 启动轮询
            self.is_running = True
            self.btn_toggle.config(text="停止获取")

            # 禁用输入组件
            self.entry_symbol.config(state="disabled")
            self.combo_kline.config(state="disabled")
            self.entry_interval.config(state="disabled")

            # 启动后台线程
            self.polling_thread = threading.Thread(
                target=self.polling_loop, daemon=True
            )
            self.polling_thread.start()
        else:
            # 停止轮询
            self.is_running = False
            self.btn_toggle.config(text="开始获取")

            # 恢复输入组件
            self.entry_symbol.config(state="normal")
            self.combo_kline.config(state="readonly")
            self.entry_interval.config(state="normal")
            self.update_status("已停止")

    def fetch_and_save(self, symbol, kline_type, interval):
        url = "https://quote.alltick.co/quote-stock-b-api/kline"
        query_payload = json.dumps(
            {
                "trace": "py_kline_ui",
                "data": {
                    "code": symbol,
                    "kline_type": kline_type,
                    "kline_timestamp_end": 0,
                    "query_kline_num": 500,
                    "adjust_type": 0,
                },
            },
            separators=(",", ":"),
        )

        try:
            res = requests.get(
                url,
                params={"token": ALLTICK_TOKEN, "query": query_payload},
                timeout=10,
            ).json()
            kline_list = res.get("data", {}).get("kline_list", [])

            if not kline_list:
                self.update_status("无有效数据", is_error=True)
                return

            df = pd.DataFrame(kline_list)
            time_col = "timestamp" if "timestamp" in df.columns else "time"
            open_col = "open_price" if "open_price" in df.columns else "open"
            high_col = "high_price" if "high_price" in df.columns else "high"
            low_col = "low_price" if "low_price" in df.columns else "low"
            close_col = "close_price" if "close_price" in df.columns else "close"

            TIMEZONE_OFFSET = 8 * 3600

            # 计算调整后的时间戳
            ts_series = df[time_col].astype(int) + TIMEZONE_OFFSET
            dt_series = pd.to_datetime(ts_series, unit="s")

            # 拆分为符合格式的 Date 与 Time 列
            df["Date"] = dt_series.dt.strftime("%Y.%m.%d")
            df["Time"] = dt_series.dt.strftime("%H:%M:%S")

            df["Open"] = df[open_col].astype(float)
            df["High"] = df[high_col].astype(float)
            df["Low"] = df[low_col].astype(float)
            df["Close"] = df[close_col].astype(float)
            df["Volume"] = df["volume"].astype(int)

            # 按原始时间排序
            df["raw_time"] = ts_series
            df = df.sort_values(by="raw_time").reset_index(drop=True)

            # 按指定列名导出数据
            csv_df = df[["Date", "Time", "Open", "High", "Low", "Close", "Volume"]]

            # 定位 MQL5/Files 目录
            appdata_path = os.getenv("APPDATA")
            terminal_path = (
                Path(appdata_path) / "MetaQuotes" / "Terminal"
                if appdata_path
                else None
            )
            mt5_files_dir = None

            if terminal_path and terminal_path.exists():
                for folder in terminal_path.iterdir():
                    files_dir = folder / "MQL5" / "Files"
                    if files_dir.exists():
                        mt5_files_dir = files_dir
                        break

            # 动态生成文件名：例如 000001.SH_6.csv
            target_filename = f"{symbol}_{kline_type}.csv"
            target_path = (
                mt5_files_dir / target_filename
                if mt5_files_dir
                else Path(target_filename)
            )

            # 导出 CSV 并保留表头
            csv_df.to_csv(target_path, index=False, header=True, sep=",")

            current_time = time.strftime("%H:%M:%S")
            last_date = csv_df["Date"].iloc[-1]
            last_time = csv_df["Time"].iloc[-1]
            self.update_status(f"[{current_time}] 成功 | 最晚K线: {last_date} {last_time}")

        except Exception as e:
            self.update_status(f"出错: {str(e)}", is_error=True)

    def polling_loop(self):
        """后台轮询循环"""
        while self.is_running:
            symbol = self.entry_symbol.get().strip()
            kline_label = self.combo_kline.get()
            kline_type = KLINE_TYPES.get(kline_label, 1)

            try:
                interval = max(1, int(self.entry_interval.get().strip()))
            except ValueError:
                interval = 10

            self.fetch_and_save(symbol, kline_type, interval)

            for _ in range(interval):
                if not self.is_running:
                    break
                time.sleep(1)


if __name__ == "__main__":
    app = AlltickApp()
    app.mainloop()