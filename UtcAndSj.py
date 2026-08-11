import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta

class SimpleTimestampConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("时间戳转换")
        self.root.geometry("420x120")
        self.root.resizable(False, False)

        # ---------- 第0行：UTC偏移 ----------
        ttk.Label(root, text="UTC偏移:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        # 用一个Frame容纳输入框和按钮，让它们紧凑排列
        offset_frame = ttk.Frame(root)
        offset_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.offset_var = tk.StringVar(value="0")
        self.offset_entry = ttk.Entry(offset_frame, textvariable=self.offset_var, width=6)
        self.offset_entry.pack(side=tk.LEFT, padx=2)
        # 左减按钮
        ttk.Button(offset_frame, text="◀", width=3, command=self.decrease_offset).pack(side=tk.LEFT, padx=2)
        # 右加按钮
        ttk.Button(offset_frame, text="▶", width=3, command=self.increase_offset).pack(side=tk.LEFT, padx=2)
        # 第2列留空占位（保持与其他行对齐）
        ttk.Label(root, text="").grid(row=0, column=2, padx=5, pady=5)

        # ---------- 第1行：时间戳 -> 日期 ----------
        ttk.Label(root, text="时间戳:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.ts_var = tk.StringVar()
        self.ts_entry = ttk.Entry(root, textvariable=self.ts_var, width=20)
        self.ts_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.ts_var.trace("w", lambda *args: self.ts_to_str())

        self.ts_result_var = tk.StringVar()
        self.ts_result_entry = ttk.Entry(root, textvariable=self.ts_result_var, width=22, state="readonly")
        self.ts_result_entry.grid(row=1, column=2, padx=5, pady=5)

        # ---------- 第2行：日期 -> 时间戳 ----------
        ttk.Label(root, text="日 期:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.str_var = tk.StringVar()
        self.str_entry = ttk.Entry(root, textvariable=self.str_var, width=20)
        self.str_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.str_var.trace("w", lambda *args: self.str_to_ts())

        self.str_result_var = tk.StringVar()
        self.str_result_entry = ttk.Entry(root, textvariable=self.str_result_var, width=22, state="readonly")
        self.str_result_entry.grid(row=2, column=2, padx=5, pady=5)

        # 偏移变化时刷新所有转换
        self.offset_var.trace("w", lambda *args: self.update_all())

        # 初始清空输入框
        self.ts_var.set("")
        self.str_var.set("")

    # ---------- 偏移增减 ----------
    def decrease_offset(self):
        try:
            current = float(self.offset_var.get())
            self.offset_var.set(str(current - 1))
        except ValueError:
            self.offset_var.set("0")

    def increase_offset(self):
        try:
            current = float(self.offset_var.get())
            self.offset_var.set(str(current + 1))
        except ValueError:
            self.offset_var.set("0")

    # ---------- 辅助方法 ----------
    def get_offset(self):
        try:
            return float(self.offset_var.get())
        except ValueError:
            return None

    def update_all(self):
        self.ts_to_str()
        self.str_to_ts()

    # ---------- 转换逻辑 ----------
    def ts_to_str(self):
        offset = self.get_offset()
        if offset is None:
            self.ts_result_var.set("偏移无效")
            return
        ts_str = self.ts_var.get().strip()
        if not ts_str:
            self.ts_result_var.set("")
            return
        try:
            ts = float(ts_str)
        except ValueError:
            self.ts_result_var.set("无效数字")
            return
        try:
            tz = timezone(timedelta(hours=offset))
            dt = datetime.fromtimestamp(ts, tz=tz)
            self.ts_result_var.set(dt.strftime("%Y%m%d%H%M%S"))
        except Exception:
            self.ts_result_var.set("错误")

    def str_to_ts(self):
        offset = self.get_offset()
        if offset is None:
            self.str_result_var.set("偏移无效")
            return
        dt_str = self.str_var.get().strip()
        if not dt_str:
            self.str_result_var.set("")
            return
        if len(dt_str) != 14 or not dt_str.isdigit():
            self.str_result_var.set("需14位数字")
            return
        try:
            naive = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
            tz = timezone(timedelta(hours=offset))
            dt_with_tz = naive.replace(tzinfo=tz)
            ts = dt_with_tz.timestamp()
            if ts.is_integer():
                self.str_result_var.set(str(int(ts)))
            else:
                self.str_result_var.set(f"{ts:.6f}")
        except ValueError:
            self.str_result_var.set("日期无效")
        except Exception:
            self.str_result_var.set("错误")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleTimestampConverter(root)
    root.mainloop()