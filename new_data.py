import sys
import os
import shutil
import datetime
from datetime import timedelta
import pandas as pd
import akshare as ak
import pyqtgraph as pg

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QFileDialog, QStatusBar, QProgressBar, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal, QRectF, QPointF, QUrl
from PyQt5.QtGui import QColor, QPainter, QPicture, QDesktopServices

# 1. 强制清理代理环境变量，避免 ProxyError
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""


class CandlestickItem(pg.GraphicsObject):
    """自定义蜡烛图 (K线) 图表控件"""

    def __init__(self, data, is_dark=False):
        super().__init__()
        self.data = data  # List of tuples: (i, open, close, low, high)
        self.is_dark = is_dark
        self.picture = QPicture()
        self.generate_picture()

    def generate_picture(self):
        p = QPainter(self.picture)

        if self.is_dark:
            red_pen = pg.mkPen(color=QColor(255, 82, 82), width=1.2)
            red_brush = pg.mkBrush(QColor(255, 82, 82))
            green_pen = pg.mkPen(color=QColor(76, 175, 80), width=1.2)
            green_brush = pg.mkBrush(QColor(76, 175, 80))
        else:
            red_pen = pg.mkPen(color=QColor(230, 50, 50), width=1.2)
            red_brush = pg.mkBrush(QColor(230, 50, 50))
            green_pen = pg.mkPen(color=QColor(50, 180, 50), width=1.2)
            green_brush = pg.mkBrush(QColor(50, 180, 50))

        w = 0.35  # 蜡烛柱宽度

        for t in self.data:
            x, open_p, close_p, low_p, high_p = t
            if close_p >= open_p:
                p.setPen(red_pen)
                p.setBrush(red_brush)
            else:
                p.setPen(green_pen)
                p.setBrush(green_brush)

            p.drawLine(QPointF(x, low_p), QPointF(x, high_p))
            p.drawRect(QRectF(x - w, open_p, w * 2, close_p - open_p))

        p.end()

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QRectF(self.picture.boundingRect())


class DateAxisItem(pg.AxisItem):
    """自定义 X 轴：将索引映射为上海时间的日期/时间文本"""

    def __init__(self, timestamps, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamps = timestamps

    def tickStrings(self, values, scale, spacing):
        strings = []
        for v in values:
            idx = int(v)
            if 0 <= idx < len(self.timestamps):
                strings.append(str(self.timestamps[idx]))
            else:
                strings.append('')
        return strings


class SinaDataExportThread(QThread):
    """纯新浪数据源 (Sina) 导出与解析线程"""
    finished_signal = pyqtSignal(bool, str, object)

    def __init__(self, symbol, period, start_date, end_date, adjust, output_dir, save_to_file=True):
        super().__init__()
        self.symbol = symbol.strip()
        self.period = period
        self.start_date = start_date.strip()
        self.end_date = end_date.strip()
        self.adjust = adjust
        self.output_dir = output_dir
        self.save_to_file = save_to_file

    def get_real_start_date(self, code, market):
        """尝试获取股票的真实上市日期，失败则退回 19900101"""
        if self.start_date != "19900101":
            return self.start_date
        try:
            df_info = ak.stock_individual_info_em(symbol=code)
            item = df_info[df_info['item'] == '上市时间']
            if not item.empty:
                val = str(item['value'].values[0]).replace("-", "").strip()
                if len(val) == 8:
                    return val
        except Exception:
            pass
        return "19900101"

    def run(self):
        try:
            clean_symbol = self.symbol.replace(",", ".").upper().strip()

            if "." in clean_symbol:
                code, market = clean_symbol.split(".", 1)
                full_symbol = f"{market.lower()}{code}"
            else:
                code = clean_symbol
                prefix = "sz" if code.startswith(("00", "30", "20", "39")) else "sh"
                full_symbol = f"{prefix}{code}"
                market = prefix.upper()

            is_index = full_symbol.startswith(("sh000", "sz399", "sh000300"))
            actual_start_date = self.get_real_start_date(code, market)

            if self.period == "1天":
                if is_index:
                    df = ak.stock_zh_index_daily(symbol=full_symbol)
                    if df is not None and not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        start_dt = pd.to_datetime(actual_start_date)
                        end_dt = pd.to_datetime(self.end_date)
                        df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()
                else:
                    df = ak.stock_zh_a_daily(
                        symbol=full_symbol,
                        start_date=actual_start_date,
                        end_date=self.end_date,
                        adjust=self.adjust
                    )

                if df is None or df.empty:
                    self.finished_signal.emit(False, "未获取到数据，请检查代码或日期范围", None)
                    return

                dt_series = pd.to_datetime(df['date']).dt.tz_localize('Asia/Shanghai')
                turnover_series = df['turnover'] if 'turnover' in df.columns else 0.0

                mt5_df = pd.DataFrame({
                    'Date': dt_series.dt.strftime('%Y.%m.%d'),
                    'Time': "00:00:00",
                    'Open': df['open'],
                    'High': df['high'],
                    'Low': df['low'],
                    'Close': df['close'],
                    'Volume': df['volume'],
                    'Turnover': turnover_series,
                    'DateTime_Label': dt_series.dt.strftime('%Y-%m-%d')
                })

            else:
                min_period_map = {
                    "5分钟": "5",
                    "15分钟": "15",
                    "30分钟": "30",
                    "1小时": "60"
                }
                k_period = min_period_map.get(self.period, "5")
                df = ak.stock_zh_a_minute(symbol=full_symbol, period=k_period, adjust=self.adjust)

                if df is None or df.empty:
                    self.finished_signal.emit(False, "未获取到分钟数据，请检查网络或代码", None)
                    return

                df['day'] = pd.to_datetime(df['day'])
                start_dt = pd.to_datetime(actual_start_date)
                end_dt = pd.to_datetime(self.end_date) + pd.Timedelta(days=1)

                df = df[(df['day'] >= start_dt) & (df['day'] < end_dt)].copy()

                if df.empty:
                    self.finished_signal.emit(False, "所选时间范围内无分钟数据", None)
                    return

                dt_series = df['day'].dt.tz_localize('Asia/Shanghai')
                turnover_series = df['turnover'] if 'turnover' in df.columns else 0.0

                mt5_df = pd.DataFrame({
                    'Date': dt_series.dt.strftime('%Y.%m.%d'),
                    'Time': dt_series.dt.strftime('%H:%M:%S'),
                    'Open': df['open'],
                    'High': df['high'],
                    'Low': df['low'],
                    'Close': df['close'],
                    'Volume': df['volume'],
                    'Turnover': turnover_series,
                    'DateTime_Label': dt_series.dt.strftime('%Y-%m-%d %H:%M')
                })

            if self.save_to_file:
                clean_period = self.period.replace("分钟", "m").replace("小时", "h").replace("天", "d")
                filename = f"{clean_symbol}_{clean_period}_sina_{actual_start_date}_{self.end_date}.csv"
                output_path = os.path.join(self.output_dir, filename)

                export_cols = ['Date', 'Time', 'Open', 'High', 'Low', 'Close', 'Volume']
                mt5_df[export_cols].to_csv(output_path, index=False)
                msg = f"导出成功！文件已保存至：{output_path}"
            else:
                msg = "查询成功！"

            self.finished_signal.emit(True, msg, mt5_df)

        except Exception as e:
            self.finished_signal.emit(False, f"接口异常：{str(e)}", None)


class StockExporterUI(QWidget):
    DEFAULT_INFO_TEXT = (
        "时间: -----  |  "
        "开盘: --  |  "
        "最高: --  |  "
        "最低: --  |  "
        "收盘: --  |  "
        "涨跌幅: --%  |  "
        "换手率: --%"
    )

    def __init__(self):
        super().__init__()
        self.current_df = None
        self.is_dark_theme = False
        self.init_ui()
        self.apply_theme()

    def init_ui(self):
        self.setWindowTitle("A股历史数据")
        self.resize(1020, 750)

        layout = QVBoxLayout()

        # 1. 股票代码 + 主题切换
        h_layout1 = QHBoxLayout()
        h_layout1.addWidget(QLabel("股票代码:"))
        self.symbol_input = QLineEdit("000001.SH")
        h_layout1.addWidget(self.symbol_input)

        self.btn_theme = QPushButton("🌙")
        self.btn_theme.setFixedWidth(140)
        self.btn_theme.clicked.connect(self.toggle_theme)
        h_layout1.addWidget(self.btn_theme)

        layout.addLayout(h_layout1)

        # 2. K线周期与复权选择
        h_layout2 = QHBoxLayout()
        h_layout2.addWidget(QLabel("数据周期:"))
        self.period_combo = QComboBox()
        self.period_combo.addItems(["5分钟", "15分钟", "30分钟", "1小时", "1天"])
        self.period_combo.setCurrentText("1天")
        h_layout2.addWidget(self.period_combo)

        h_layout2.addWidget(QLabel("复权类型:"))
        self.adjust_combo = QComboBox()
        self.adjust_combo.addItems(["前复权 (qfq)", "后复权 (hfq)", "不复权 (不填)"])
        self.adjust_combo.setCurrentIndex(0)
        h_layout2.addWidget(self.adjust_combo)
        layout.addLayout(h_layout2)

        # 3. 起止日期 (快捷选择)
        h_layout3 = QHBoxLayout()
        today = datetime.date.today()
        today_str = today.strftime("%Y%m%d")

        h_layout3.addWidget(QLabel("开始日期:"))

        self.quick_date_combo = QComboBox()
        self.quick_date_combo.addItems(["自定义", "近1个月", "近3个月", "近1年", "近3年", "上市至今"])
        h_layout3.addWidget(self.quick_date_combo)

        self.start_date_input = QLineEdit((today - timedelta(days=365)).strftime("%Y%m%d"))
        h_layout3.addWidget(self.start_date_input)

        h_layout3.addWidget(QLabel("结束日期:"))
        self.end_date_input = QLineEdit(today_str)
        h_layout3.addWidget(self.end_date_input)

        self.quick_date_combo.currentIndexChanged.connect(self.on_quick_date_changed)
        self.start_date_input.textEdited.connect(lambda: self.quick_date_combo.setCurrentText("自定义"))

        layout.addLayout(h_layout3)

        # 4. 保存目录 & 操作按钮组 (新增打开文件夹)
        h_layout4 = QHBoxLayout()
        h_layout4.addWidget(QLabel("输出文件夹:"))
        self.dir_input = QLineEdit(os.path.abspath("./export_data"))
        h_layout4.addWidget(self.dir_input)

        self.btn_select_dir = QPushButton("选择文件夹")
        self.btn_select_dir.clicked.connect(self.select_directory)
        h_layout4.addWidget(self.btn_select_dir)

        # 新增：打开文件夹按钮
        self.btn_open_dir = QPushButton("打开文件夹")
        self.btn_open_dir.clicked.connect(self.open_directory)
        h_layout4.addWidget(self.btn_open_dir)

        self.btn_export_data = QPushButton("导出数据")
        self.btn_export_data.clicked.connect(self.start_export)
        h_layout4.addWidget(self.btn_export_data)

        self.btn_clean_dir = QPushButton("清理目录")
        self.btn_clean_dir.clicked.connect(self.clean_directory)
        h_layout4.addWidget(self.btn_clean_dir)

        layout.addLayout(h_layout4)

        # 5. 查询数据按钮
        self.btn_export = QPushButton("查询数据")
        self.btn_export.setStyleSheet("font-size: 14px; font-weight: bold; min-height: 32px;")
        self.btn_export.clicked.connect(lambda: self.start_fetch_data(save_to_file=False))
        layout.addWidget(self.btn_export)

        # 6. 交互式数据信息面板栏
        self.info_label = QLabel(self.DEFAULT_INFO_TEXT)
        layout.addWidget(self.info_label)

        # 7. 图表容器初始化
        self.graphics_layout = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_layout)

        # 8. 底部状态栏
        self.status_bar = QStatusBar()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(120)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()

        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        self.status_bar.addPermanentWidget(self.progress_bar)

        layout.addWidget(self.status_bar)

        self.setLayout(layout)

    def on_quick_date_changed(self, index):
        selection = self.quick_date_combo.currentText()
        if selection == "自定义":
            return

        today = datetime.date.today()

        if selection == "近1个月":
            start_dt = today - timedelta(days=30)
        elif selection == "近3个月":
            start_dt = today - timedelta(days=90)
        elif selection == "近1年":
            start_dt = today - timedelta(days=365)
        elif selection == "近3年":
            start_dt = today - timedelta(days=365 * 3)
        elif selection == "上市至今":
            self.start_date_input.setText("19900101")
            return

        self.start_date_input.setText(start_dt.strftime("%Y%m%d"))

    def toggle_theme(self):
        self.is_dark_theme = not self.is_dark_theme
        self.btn_theme.setText("☀️" if self.is_dark_theme else "🌙")
        self.apply_theme()

        if self.current_df is not None and not self.current_df.empty:
            self.plot_data(self.current_df)

    def apply_theme(self):
        bg_color = "#121212" if self.is_dark_theme else "#ffffff"

        if hasattr(self, 'graphics_layout'):
            self.graphics_layout.setBackground(bg_color)

        if self.is_dark_theme:
            card_bg = "#1e1e1e"
            text_color = "#e0e0e0"
            border_color = "#333333"

            self.setStyleSheet(f"""
                QWidget {{ background-color: {bg_color}; color: {text_color}; font-family: Microsoft YaHei, Segoe UI, sans-serif; }}
                QLineEdit, QComboBox {{ background-color: {card_bg}; border: 1px solid {border_color}; border-radius: 4px; padding: 4px; color: {text_color}; }}
                QPushButton {{ background-color: #263238; color: #ffffff; border: 1px solid #37474f; border-radius: 4px; padding: 5px 12px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #37474f; }}
                QStatusBar {{ background-color: {card_bg}; color: {text_color}; border-top: 1px solid {border_color}; }}
            """)

            self.default_info_style = (
                "font-size: 13px; font-weight: bold; color: #81d4fa; "
                "padding: 6px; background-color: #1a2634; border-radius: 4px; border: 1px solid #264b5d;"
            )
        else:
            card_bg = "#f5f5f5"
            text_color = "#212121"
            border_color = "#cccccc"

            self.setStyleSheet(f"""
                QWidget {{ background-color: {bg_color}; color: {text_color}; font-family: Microsoft YaHei, Segoe UI, sans-serif; }}
                QLineEdit, QComboBox {{ background-color: #ffffff; border: 1px solid {border_color}; border-radius: 4px; padding: 4px; color: {text_color}; }}
                QPushButton {{ background-color: #e0e0e0; color: #212121; border: 1px solid #bdbdbd; border-radius: 4px; padding: 5px 12px; font-weight: bold; }}
                QPushButton:hover {{ background-color: #d6d6d6; }}
                QStatusBar {{ background-color: {card_bg}; color: {text_color}; border-top: 1px solid {border_color}; }}
            """)

            self.default_info_style = (
                "font-size: 13px; font-weight: bold; color: #1a237e; "
                "padding: 6px; background-color: #e8eaf6; border-radius: 4px; border: 1px solid #c5cae9;"
            )

        self.info_label.setText(self.DEFAULT_INFO_TEXT)
        self.info_label.setStyleSheet(self.default_info_style)

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择保存文件夹", self.dir_input.text())
        if directory:
            self.dir_input.setText(directory)

    def open_directory(self):
        """快速打开当前的输出文件夹"""
        target_dir = self.dir_input.text().strip()
        if not target_dir:
            return

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        QDesktopServices.openUrl(QUrl.fromLocalFile(target_dir))

    def clean_directory(self):
        target_dir = self.dir_input.text().strip()
        if not os.path.exists(target_dir):
            QMessageBox.information(self, "提示", "指定文件夹不存在，无需清理。")
            return

        reply = QMessageBox.question(
            self,
            "确认清理",
            f"确定要清空以下目录中的所有文件吗？\n{target_dir}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                count = 0
                for filename in os.listdir(target_dir):
                    file_path = os.path.join(target_dir, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        count += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        count += 1
                self.status_label.setText(f"✓ 已完成目录清理，共删除 {count} 个项目。")
                self.status_label.setStyleSheet("color: #66bb6a; font-weight: bold;" if self.is_dark_theme else "color: #2e7d32; font-weight: bold;")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清理文件夹失败: {str(e)}")

    def start_export(self):
        self.start_fetch_data(save_to_file=True)

    def start_fetch_data(self, save_to_file=False):
        symbol = self.symbol_input.text().strip()
        period = self.period_combo.currentText()
        start_date = self.start_date_input.text().strip()
        end_date = self.end_date_input.text().strip()

        adjust_map = {"前复权 (qfq)": "qfq", "后复权 (hfq)": "hfq", "不复权 (不填)": ""}
        adjust = adjust_map.get(self.adjust_combo.currentText(), "qfq")

        output_dir = self.dir_input.text().strip()
        if save_to_file and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        self.btn_export.setEnabled(False)
        self.btn_export_data.setEnabled(False)
        self.status_label.setText("正在拉取并解析数据..." if not save_to_file else "正在导出数据...")
        self.status_label.setStyleSheet("color: #29b6f6;" if self.is_dark_theme else "color: #0055ff;")
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()

        self.thread = SinaDataExportThread(symbol, period, start_date, end_date, adjust, output_dir, save_to_file=save_to_file)
        self.thread.finished_signal.connect(self.on_export_finished)
        self.thread.start()

    def on_export_finished(self, success, message, df):
        self.btn_export.setEnabled(True)
        self.btn_export_data.setEnabled(True)
        self.progress_bar.hide()

        if not success:
            self.status_label.setText(f"❌ {message}")
            self.status_label.setStyleSheet("color: #ff5252; font-weight: bold;" if self.is_dark_theme else "color: #d32f2f; font-weight: bold;")
            return

        self.info_label.setText(self.DEFAULT_INFO_TEXT)
        self.info_label.setStyleSheet(self.default_info_style)

        self.current_df = df
        self.plot_data(df)
        self.status_label.setText(f"✓ {message}")
        self.status_label.setStyleSheet("color: #66bb6a; font-weight: bold;" if self.is_dark_theme else "color: #2e7d32; font-weight: bold;")

    def plot_data(self, df):
        self.graphics_layout.clear()

        bg_color = '#121212' if self.is_dark_theme else '#ffffff'
        fg_color = '#e0e0e0' if self.is_dark_theme else '#000000'
        grid_alpha = 0.2 if self.is_dark_theme else 0.3

        self.graphics_layout.setBackground(bg_color)

        time_labels = df['DateTime_Label'].values

        x_axis_price = DateAxisItem(time_labels, orientation='bottom')
        x_axis_vol = DateAxisItem(time_labels, orientation='bottom')

        x_axis_price.setPen(fg_color)
        x_axis_price.setTextPen(fg_color)
        x_axis_vol.setPen(fg_color)
        x_axis_vol.setTextPen(fg_color)

        self.price_plot = self.graphics_layout.addPlot(
            row=0, col=0,
            axisItems={'bottom': x_axis_price},
            title="K线走势图|Candlestick"
        )
        self.volume_plot = self.graphics_layout.addPlot(
            row=1, col=0,
            axisItems={'bottom': x_axis_vol},
            title="成交量柱状图|Volume"
        )

        title_style = {'color': fg_color, 'size': '11pt'}
        self.price_plot.setTitle("K线走势图|Candlestick", **title_style)
        self.volume_plot.setTitle("成交量柱状图|Volume", **title_style)

        self.price_plot.getAxis('left').setPen(fg_color)
        self.price_plot.getAxis('left').setTextPen(fg_color)
        self.volume_plot.getAxis('left').setPen(fg_color)
        self.volume_plot.getAxis('left').setTextPen(fg_color)

        self.volume_plot.setXLink(self.price_plot)
        self.graphics_layout.ci.layout.setRowStretchFactor(0, 3)
        self.graphics_layout.ci.layout.setRowStretchFactor(1, 1)

        x = list(range(len(df)))
        opens = df['Open'].values
        closes = df['Close'].values
        lows = df['Low'].values
        highs = df['High'].values
        volumes = df['Volume'].values

        candle_data = [
            (i, opens[i], closes[i], lows[i], highs[i])
            for i in range(len(df))
        ]
        candle_item = CandlestickItem(candle_data, is_dark=self.is_dark_theme)
        self.price_plot.addItem(candle_item)
        self.price_plot.showGrid(x=True, y=True, alpha=grid_alpha)

        colors = []
        for i in range(len(df)):
            if closes[i] >= opens[i]:
                color = QColor(255, 82, 82, 200) if self.is_dark_theme else QColor(230, 50, 50, 180)
            else:
                color = QColor(76, 175, 80, 200) if self.is_dark_theme else QColor(50, 180, 50, 180)
            colors.append(color)

        bars = pg.BarGraphItem(x=x, height=volumes, width=0.6, brushes=colors)
        self.volume_plot.addItem(bars)
        self.volume_plot.showGrid(x=True, y=True, alpha=grid_alpha)

        total_count = len(df)
        x_min = -0.5
        x_max = total_count - 0.5

        global_min_low = float(min(lows))
        global_max_high = float(max(highs))
        price_range = global_max_high - global_min_low
        if price_range == 0:
            price_range = global_max_high * 0.05 or 1.0

        y_min = global_min_low - price_range * 0.10
        y_max = global_max_high + price_range * 0.10

        self.price_plot.setXRange(x_min, x_max, padding=0)
        self.price_plot.setYRange(y_min, y_max, padding=0)

        self.price_plot.setLimits(
            xMin=x_min, xMax=x_max,
            yMin=y_min, yMax=y_max
        )
        self.volume_plot.setLimits(
            xMin=x_min, xMax=x_max,
            yMin=0, yMax=max(volumes) * 1.15
        )

        self.price_plot.scene().sigMouseClicked.connect(self.on_chart_clicked)

    def on_chart_clicked(self, event):
        if self.current_df is None or self.current_df.empty:
            return

        if event.button() != 1:
            return

        pos = event.scenePos()
        if not self.price_plot.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.price_plot.vb.mapSceneToView(pos)
        x_idx = int(round(mouse_point.x()))

        if 0 <= x_idx < len(self.current_df):
            row = self.current_df.iloc[x_idx]

            open_p, close_p = row['Open'], row['Close']
            high_p, low_p = row['High'], row['Low']
            turnover = row.get('Turnover', 0.0)
            dt_str = row['DateTime_Label']

            turnover_pct = turnover * 100 if 0 < turnover < 1 else turnover

            change = close_p - open_p
            pct_change = (change / open_p) * 100 if open_p != 0 else 0

            info_text = (
                f"时间: {dt_str}  |  "
                f"开盘: {open_p:.2f}  |  "
                f"最高: {high_p:.2f}  |  "
                f"最低: {low_p:.2f}  |  "
                f"收盘: {close_p:.2f}  |  "
                f"涨跌幅: {pct_change:+.2f}%  |  "
                f"换手率: {turnover_pct:.2f}%"
            )

            if self.is_dark_theme:
                if close_p >= open_p:
                    style = (
                        "font-size: 13px; font-weight: bold; color: #ff8a80; "
                        "padding: 6px; background-color: #3b1e1e; border-radius: 4px; border: 1px solid #d32f2f;"
                    )
                else:
                    style = (
                        "font-size: 13px; font-weight: bold; color: #b9f6ca; "
                        "padding: 6px; background-color: #1b3820; border-radius: 4px; border: 1px solid #388e3c;"
                    )
            else:
                if close_p >= open_p:
                    style = (
                        "font-size: 13px; font-weight: bold; color: #b71c1c; "
                        "padding: 6px; background-color: #ffebee; border-radius: 4px; border: 1px solid #ffcdd2;"
                    )
                else:
                    style = (
                        "font-size: 13px; font-weight: bold; color: #1b5e20; "
                        "padding: 6px; background-color: #e8f5e9; border-radius: 4px; border: 1px solid #c8e6c9;"
                    )

            self.info_label.setText(info_text)
            self.info_label.setStyleSheet(style)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = StockExporterUI()
    window.show()
    sys.exit(app.exec_())
