from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QFileDialog, QGroupBox, 
    QScrollArea, QSplitter, QComboBox, 
    QDoubleSpinBox, QCheckBox, QMessageBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import os
import time
from core.convolution_engine import ConvolutionEngine

class ConvolutionThread(QThread):
    finished = pyqtSignal(str, str)  # signal for (image_path, status)
    error = pyqtSignal(str)  # signal for error message

    def __init__(self, engine, dwell_file, ion_file):
        super().__init__()
        self.engine = engine
        self.dwell_file = dwell_file
        self.ion_file = ion_file

    def run(self):
        try:
            start_time = time.time()
            heatmap_path, csv_path = self.engine.process_etch_depth(
                self.dwell_file, 
                self.ion_file
            )
            elapsed = time.time() - start_time
            status = f"计算完成 (耗时: {elapsed:.2f}秒)"
            self.finished.emit(heatmap_path, status)
        except Exception as e:
            self.error.emit(str(e))

class ConvolutionIntegralUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.engine = ConvolutionEngine()
        self.etch_depth_image = None
        self.current_dwell_file = None
        self.current_ion_file = None
        self.init_ui()
        self.worker_thread = None
    
    def init_ui(self):
        # 主布局 - 左右分栏
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # === 左侧控制面板 ===
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        # 文件选择区域
        file_grp = QGroupBox("选择输入文件")
        file_layout = QGridLayout(file_grp)
        
        # 停留时间分布文件选择
        self.dwell_label = QLabel("未选择")
        file_layout.addWidget(QLabel("停留时间分布文件(1mm网格):"), 0, 0)
        file_layout.addWidget(self.dwell_label, 0, 1, 1, 2)
        
        self.select_dwell_btn = QPushButton("浏览...")
        self.select_dwell_btn.clicked.connect(lambda: self.select_input_file('dwell'))
        file_layout.addWidget(self.select_dwell_btn, 0, 3)
        
        # 离子束能量分布文件选择
        self.ion_label = QLabel("未选择")
        file_layout.addWidget(QLabel("离子束能量分布文件:"), 1, 0)
        file_layout.addWidget(self.ion_label, 1, 1, 1, 2)
        
        self.select_ion_btn = QPushButton("浏览...")
        self.select_ion_btn.clicked.connect(lambda: self.select_input_file('ion'))
        file_layout.addWidget(self.select_ion_btn, 1, 3)
        
        left_layout.addWidget(file_grp)
        
        # === 镜像设置 ===
        mirror_grp = QGroupBox("镜像设置")
        mirror_layout = QHBoxLayout(mirror_grp)
        
        self.mirror_label = QLabel("当前状态: 未翻转")
        mirror_layout.addWidget(self.mirror_label)
        
        # X轴镜像翻转
        self.mirror_btn = QPushButton("沿X轴镜像翻转")
        self.mirror_btn.setFixedWidth(150)
        self.mirror_btn.setToolTip("翻转上下方向 - 顶部变底部，底部变顶部")
        self.mirror_btn.clicked.connect(self.toggle_mirror)
        mirror_layout.addWidget(self.mirror_btn)
        
        left_layout.addWidget(mirror_grp)
        
        # === 圆形区域配置 ===
        circle_grp = QGroupBox("圆形区域设置")
        circle_layout = QGridLayout(circle_grp)
        
        self.circle_mode_cb = QCheckBox("仅显示圆形区域")
        self.circle_mode_cb.setChecked(False)
        self.circle_mode_cb.stateChanged.connect(self.toggle_circle_mode)
        circle_layout.addWidget(self.circle_mode_cb, 0, 0, 1, 4)
        
        circle_layout.addWidget(QLabel("直径(mm):"), 1, 0)
        self.diameter_cb = QComboBox()
        self.diameter_cb.addItems(["100", "150", "200", "300"])
        self.diameter_cb.setCurrentIndex(1)  # 默认选择150mm
        circle_layout.addWidget(self.diameter_cb, 1, 1)
        
        circle_layout.addWidget(QLabel("圆心X(mm):"), 2, 0)
        self.center_x_input = QDoubleSpinBox()
        self.center_x_input.setDecimals(3)
        self.center_x_input.setRange(-500, 500)
        self.center_x_input.setValue(0)
        circle_layout.addWidget(self.center_x_input, 2, 1)
        
        circle_layout.addWidget(QLabel("圆心Y(mm):"), 2, 2)
        self.center_y_input = QDoubleSpinBox()
        self.center_y_input.setDecimals(3)
        self.center_y_input.setRange(-500, 500)
        self.center_y_input.setValue(0)
        circle_layout.addWidget(self.center_y_input, 2, 3)
        
        circle_layout.addWidget(QLabel("显示样式:"), 1, 2)
        self.style_cb = QComboBox()
        self.style_cb.addItems(["jet", "plasma", "inferno", "viridis", "coolwarm"])
        self.style_cb.setCurrentText("jet")
        circle_layout.addWidget(self.style_cb, 1, 3)
        
        left_layout.addWidget(circle_grp)
        
        # === 添加计算按钮 ===
        self.calc_btn = QPushButton("计算刻蚀深度分布")
        self.calc_btn.setMinimumHeight(40)
        self.calc_btn.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.calc_btn.clicked.connect(self.calculate_convolution)
        left_layout.addWidget(self.calc_btn)
        
        # 进度和信息标签
        self.progress_label = QLabel("等待计算...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.progress_label)
        
        # === 右侧结果面板 ===
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)
        
        # === 结果展示区域 ===
        result_grp = QGroupBox("刻蚀深度分布图")
        result_layout = QVBoxLayout(result_grp)
        
        self.etch_label = QLabel()
        self.etch_label.setAlignment(Qt.AlignCenter)
        self.etch_label.setStyleSheet("background-color: white; min-height: 500px;")
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.etch_label)
        result_layout.addWidget(scroll_area, 1)  # 设置伸缩因子为1
        
        # 添加结果状态标签
        self.result_label = QLabel("结果将显示在这里")
        self.result_label.setAlignment(Qt.AlignCenter)
        result_layout.addWidget(self.result_label)
        
        right_layout.addWidget(result_grp)
        
        # 添加分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 600])
        
        main_layout.addWidget(splitter, 1)  # 设置伸缩因子为1
    
    def toggle_circle_mode(self, state):
        self.engine.circle_mode = (state == Qt.Checked)
        circle_status = "圆形区域" if self.engine.circle_mode else "矩形区域"
        self.progress_label.setText(f"当前模式: {circle_status}")
    
    def toggle_mirror(self):
        """应用X轴镜像翻转"""
        # 切换镜像状态
        self.engine.mirror_x = not self.engine.mirror_x
        
        # 更新标签状态
        status = "已翻转" if self.engine.mirror_x else "未翻转"
        self.mirror_label.setText(f"当前状态: {status}")
        
        # 更新按钮状态
        self.mirror_btn.setText("恢复原始方向" if self.engine.mirror_x else "沿X轴镜像翻转")
    
    def select_input_file(self, file_type):
        """选择停留时间或离子束文件"""
        if file_type == 'dwell':
            dialog_label = "停留时间文件"
        else:
            dialog_label = "离子束能量分布文件"
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            f"选择{dialog_label}",
            "", 
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
            
        file_name = os.path.basename(file_path)
        display_name = file_name if len(file_name) <= 30 else file_name[:27] + "..."
        
        if file_type == 'dwell':
            self.current_dwell_file = file_path
            self.dwell_label.setText(display_name)
        else:
            self.current_ion_file = file_path
            self.ion_label.setText(display_name)
    
    def calculate_convolution(self):
        if not self.current_dwell_file or not self.current_ion_file:
            error_msg = "请选择停留时间文件和离子束文件"
            self.result_label.setText(error_msg)
            QMessageBox.warning(self, "输入不完整", error_msg)
            return
            
        try:
            # 更新圆形设置
            diameter = float(self.diameter_cb.currentText())
            center_x = self.center_x_input.value()
            center_y = self.center_y_input.value()
            circle_style = self.style_cb.currentText()
            
            self.engine.set_circle_params(diameter, center_x, center_y)
            self.engine.circle_style = circle_style
            
            # 禁用按钮防止重复点击
            self.calc_btn.setEnabled(False)
            self.calc_btn.setText("计算中...")
            
            # 显示加载中图像
            self.result_label.setText("计算中，请稍候...")
            self.progress_label.setText("正在计算蚀刻深度...")
            
            # 临时显示加载动画
            loading_img = QPixmap()
            loading_img.loadFromData(self._create_loading_image())
            self.etch_label.setPixmap(loading_img)
            
            # 使用工作线程避免阻塞UI
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.terminate()
                
            self.worker_thread = ConvolutionThread(
                self.engine, 
                self.current_dwell_file, 
                self.current_ion_file
            )
            
            self.worker_thread.finished.connect(self.on_calculation_finished)
            self.worker_thread.error.connect(self.on_calculation_error)
            self.worker_thread.start()
            
        except Exception as e:
            self.on_calculation_error(str(e))
    
    def _create_loading_image(self):
        """创建加载中图片的字节数据"""
        import matplotlib.pyplot as plt
        from io import BytesIO
        
        plt.figure(figsize=(6, 4))
        plt.text(0.5, 0.5, "计算中...", 
                ha='center', va='center', fontsize=24, color='blue')
        plt.axis('off')
        
        buffer = BytesIO()
        plt.savefig(buffer, dpi=150, format='png', bbox_inches='tight')
        plt.close()
        
        buffer.seek(0)
        return buffer.getvalue()
    
    def on_calculation_finished(self, heatmap_path, status):
        # 更新进度标签
        self.progress_label.setText(status)
        
        # 启用按钮
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("计算刻蚀深度分布")
        
        # 显示热力图
        try:
            pixmap = QPixmap(heatmap_path)
            self.etch_label.setPixmap(pixmap)
            
            # 更新状态
            area_mode = "圆形区域" if self.engine.circle_mode else "矩形区域"
            mirror_mode = "镜像模式" if self.engine.mirror_x else "正常模式"
            file_name = os.path.basename(heatmap_path)
            
            self.result_label.setText(
                f"刻蚀深度分布 | {area_mode} | {mirror_mode}\n"
                f"{file_name}"
            )
            
        except Exception as e:
            self.result_label.setText(f"显示图像错误: {str(e)}")
    
    def on_calculation_error(self, error_message):
        # 恢复按钮状态
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("计算刻蚀深度分布")
        self.progress_label.setText("计算错误")
        
        # 显示错误信息
        self.result_label.setText(f"错误: {error_message}")
        
        # 保存错误图像到缓存
        error_img = QPixmap()
        error_img.loadFromData(self._create_error_image(error_message))
        self.etch_label.setPixmap(error_img)
        
        QMessageBox.critical(self, "计算错误", f"卷积积分过程中出错:\n{error_message}")
    
    def _create_error_image(self, error_message):
        """创建错误信息的图片字节数据"""
        import matplotlib.pyplot as plt
        from io import BytesIO
        
        plt.figure(figsize=(6, 4))
        plt.text(0.5, 0.5, f"错误:\n{error_message}", 
                ha='center', va='center', fontsize=14, color='red')
        plt.axis('off')
        
        buffer = BytesIO()
        plt.savefig(buffer, dpi=150, format='png', bbox_inches='tight')
        plt.close()
        
        buffer.seek(0)
        return buffer.getvalue()
