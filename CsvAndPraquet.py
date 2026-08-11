import os
import sys
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel


# 后台数据处理线程
class ConvertThread(QThread):
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        total = len(self.file_paths)
        for idx, file_path in enumerate(self.file_paths, 1):
            try:
                ext = os.path.splitext(file_path)[1].lower()
                filename = os.path.basename(file_path)

                if ext == '.csv':
                    self.status_signal.emit(f"正在转换 ({idx}/{total}): {filename}")
                    output_path = os.path.splitext(file_path)[0] + '.parquet'
                    self.csv_to_parquet(file_path, output_path)

                elif ext == '.parquet':
                    self.status_signal.emit(f"正在转换 ({idx}/{total}): {filename}")
                    output_path = os.path.splitext(file_path)[0] + '_converted.csv'
                    self.parquet_to_csv(file_path, output_path)
                else:
                    self.status_signal.emit(f"跳过不支持的文件: {filename}")
            except Exception as e:
                self.status_signal.emit(f"处理失败: {filename}")

        self.finished_signal.emit()

    def csv_to_parquet(self, input_csv_path, output_parquet_path):
        df = pd.read_csv(input_csv_path)
        datetime_str = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
        dt_series = pd.to_datetime(datetime_str, format='%Y.%m.%d %H:%M:%S')
        time_ks = dt_series.astype('int64') // 10 ** 9

        df_processed = pd.DataFrame({
            'time': time_ks,
            'open': df['Open'],
            'high': df['High'],
            'low': df['Low'],
            'close': df['Close'],
            'tick_volume': df['Volume']
        })
        df_processed.to_parquet(output_parquet_path, index=False)

    def parquet_to_csv(self, input_parquet_path, output_csv_path):
        df = pd.read_parquet(input_parquet_path)
        df.to_csv(output_csv_path, index=False, encoding='utf-8')


# 极简 UI 主窗口
class MinimalConverterUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('格式转换器')
        self.setFixedSize(360, 200)  # 固定精简尺寸
        self.setAcceptDrops(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 10)
        layout.setSpacing(8)

        # 核心拖拽区域
        self.drop_area = QLabel("拖入 CSV / Parquet 文件")
        self.drop_area.setAlignment(Qt.AlignCenter)
        self.drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                border-radius: 8px;
                background-color: #fafafa;
                font-size: 14px;
                color: #666666;
            }
            QLabel:hover {
                border-color: #007bff;
                background-color: #f0f7ff;
                color: #007bff;
            }
        """)
        layout.addWidget(self.drop_area, stretch=1)

        # 最下方极简状态显示栏
        self.status_label = QLabel("就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    # 拖拽进入事件
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    # 拖拽放下事件
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls if url.isLocalFile()]

        if file_paths:
            self.setAcceptDrops(False)
            self.drop_area.setText("转换中...")

            self.thread = ConvertThread(file_paths)
            self.thread.status_signal.connect(self.status_label.setText)
            self.thread.finished_signal.connect(self.on_finished)
            self.thread.start()

    def on_finished(self):
        self.drop_area.setText("拖入 CSV / Parquet 文件")
        self.status_label.setText("转换完成")
        self.setAcceptDrops(True)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MinimalConverterUI()
    window.show()
    sys.exit(app.exec_())