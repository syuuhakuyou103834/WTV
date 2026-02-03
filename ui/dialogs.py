from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QDialogButtonBox,
                             QDoubleSpinBox, QGroupBox, QGridLayout, QPushButton, QMessageBox,
                             QFormLayout, QSpinBox
)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import Qt

class DataInputDialog(QDialog):
    def __init__(self, parent=None, default_wafer_size=200):
        super().__init__(parent)
        self.setWindowTitle("添加数据点")
        self.result = None
        self.default_wafer_size = default_wafer_size
        
        layout = QVBoxLayout(self)
        
        # 坐标输入字段
        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X坐标 (mm):"))
        self.x_input = QDoubleSpinBox()
        self.x_input.setRange(-500, 500)
        coord_layout.addWidget(self.x_input)
        
        coord_layout.addWidget(QLabel("Y坐标 (mm):"))
        self.y_input = QDoubleSpinBox()
        self.y_input.setRange(-500, 500)
        coord_layout.addWidget(self.y_input)
        
        layout.addLayout(coord_layout)
        
        # 膜厚输入
        thick_layout = QHBoxLayout()
        thick_layout.addWidget(QLabel("膜厚 (nm):"))
        self.thick_input = QDoubleSpinBox()
        self.thick_input.setRange(1, 10000)
        self.thick_input.setValue(500)
        thick_layout.addWidget(self.thick_input)
        
        layout.addLayout(thick_layout)
        
        # 最大范围提示
        max_val = default_wafer_size / 2
        layout.addWidget(QLabel(f"晶圆范围: -{max_val:.0f}mm 到 +{max_val:.0f}mm"))
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def accept(self):
        """接收输入"""
        self.result = (
            self.x_input.value(),
            self.y_input.value(),
            self.thick_input.value()
        )
        super().accept()

class RangeSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("按厚度范围选择")
        self.result = None
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("请输入厚度范围:"))
        
        range_layout = QHBoxLayout()
        range_layout.addWidget(QLabel("最小值:"))
        self.min_input = QDoubleSpinBox()
        self.min_input.setRange(0, 10000)
        range_layout.addWidget(self.min_input)
        
        range_layout.addWidget(QLabel("最大值:"))
        self.max_input = QDoubleSpinBox()
        self.max_input.setRange(0, 10000)
        self.max_input.setValue(1000)
        range_layout.addWidget(self.max_input)
        
        layout.addLayout(range_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_range)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def accept_range(self):
        """接收范围输入"""
        min_val = self.min_input.value()
        max_val = self.max_input.value()
        
        # 交换值以确保min<max
        if min_val > max_val:
            min_val, max_val = max_val, min_val
        
        self.result = (min_val, max_val)
        self.accept()
        
class PostSelectDialog(QDialog):
    def __init__(self, parent=None, count=0):
        super().__init__(parent)
        self.setWindowTitle("选择操作")
        self.choice = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"已选择 {count} 个点"))
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.modify_btn = QPushButton("修改厚度")
        self.modify_btn.clicked.connect(self.select_modify)
        btn_layout.addWidget(self.modify_btn)
        
        self.delete_btn = QPushButton("删除数据点")
        self.delete_btn.clicked.connect(self.select_delete)
        btn_layout.addWidget(self.delete_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def select_modify(self):
        self.choice = "modify"
        self.accept()
    
    def select_delete(self):
        self.choice = "delete"
        self.accept()


class NewGridSettingsDialog(QDialog):
    def __init__(self, wafer_size, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新网格设置")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        # 晶圆尺寸说明
        self.size_label = QLabel(f"晶圆直径: {wafer_size}mm")
        layout.addRow(QLabel("晶圆尺寸:"), self.size_label)
        
        # X步长
        self.x_step_input = QLineEdit("10.0")
        self.x_step_input.setValidator(QDoubleValidator(0.1, 1000, 3, self))
        layout.addRow(QLabel("X步长 (mm):"), self.x_step_input)
        
        # Y步长
        self.y_step_input = QLineEdit("10.0")
        self.y_step_input.setValidator(QDoubleValidator(0.1, 1000, 3, self))
        layout.addRow(QLabel("Y步长 (mm):"), self.y_step_input)
        
        # 起始点
        self.start_point_input = QLineEdit("0,0")
        layout.addRow(QLabel("起始点 (x,y):"), self.start_point_input)
        
        # 操作按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)
    
    def validate_and_accept(self):
        # 获取X步长
        x_step = self.x_step_input.text()
        try:
            x_step = float(x_step)
            if x_step <= 0:
                raise ValueError
        except:
            QMessageBox.warning(self, "步长错误", "X步长必须是大于0的数字")
            return
        
        # 获取Y步长
        y_step = self.y_step_input.text()
        try:
            y_step = float(y_step)
            if y_step <= 0:
                raise ValueError
        except:
            QMessageBox.warning(self, "步长错误", "Y步长必须是大于0的数字")
            return
        
        # 获取起始点
        start_point = self.start_point_input.text()
        try:
            x_start, y_start = [float(p.strip()) for p in start_point.split(",")]
        except:
            QMessageBox.warning(self, "坐标错误", "起始点格式错误，请输入两个数字以逗号分隔（例如：0,0）")
            return
        
        # 保存结果
        self.result = (x_step, y_step, (x_start, y_start))
        self.accept()


class AdvancedOptionsDialog(QDialog):
    """高级选项设置对话框"""
    def __init__(self, transition_width, recipe_range, uniformity_threshold=0.5, speed_threshold=140.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级选项设置")
        self.setModal(True)
        self.setFixedSize(450, 350)  # 增加高度以容纳新选项

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title = QLabel("高级参数设置")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(title)

        # 过渡区宽度设置
        transition_group = QGroupBox("过渡区设置")
        transition_layout = QHBoxLayout(transition_group)

        transition_layout.addWidget(QLabel("过渡区宽度 (mm):"))
        self.transition_input = QDoubleSpinBox()
        self.transition_input.setRange(1.0, 200.0)
        self.transition_input.setValue(transition_width)
        self.transition_input.setSingleStep(1.0)
        self.transition_input.setSuffix(" mm")
        transition_layout.addWidget(self.transition_input)

        layout.addWidget(transition_group)

        # Recipe截取范围设置
        recipe_group = QGroupBox("Recipe生成设置")
        recipe_layout = QHBoxLayout(recipe_group)

        recipe_layout.addWidget(QLabel("Recipe截取范围 (mm):"))
        self.recipe_input = QSpinBox()
        self.recipe_input.setRange(50, 500)
        self.recipe_input.setValue(recipe_range)
        self.recipe_input.setSingleStep(10)
        self.recipe_input.setSuffix(" mm")
        recipe_layout.addWidget(self.recipe_input)

        layout.addWidget(recipe_group)

        # 均一性判定标准设置
        uniformity_group = QGroupBox("质量判定标准")
        uniformity_layout = QHBoxLayout(uniformity_group)

        uniformity_layout.addWidget(QLabel("验算均一性阈值 (%):"))
        self.uniformity_input = QDoubleSpinBox()
        self.uniformity_input.setRange(0.1, 10.0)
        self.uniformity_input.setValue(uniformity_threshold)
        self.uniformity_input.setSingleStep(0.1)
        self.uniformity_input.setSuffix(" %")
        self.uniformity_input.setDecimals(2)
        uniformity_layout.addWidget(self.uniformity_input)

        layout.addWidget(uniformity_group)

        # 倍速多次扫描条件设置
        speed_group = QGroupBox("倍速多次扫描设置")
        speed_layout = QHBoxLayout(speed_group)

        speed_layout.addWidget(QLabel("刻蚀量阈值 (nm):"))
        self.speed_threshold_input = QDoubleSpinBox()
        self.speed_threshold_input.setRange(50.0, 500.0)
        self.speed_threshold_input.setValue(speed_threshold)
        self.speed_threshold_input.setSingleStep(10.0)
        self.speed_threshold_input.setSuffix(" nm")
        self.speed_threshold_input.setDecimals(1)
        speed_layout.addWidget(self.speed_threshold_input)

        layout.addWidget(speed_group)

        # 说明文字
        info_label = QLabel("提示: 过渡区宽度影响载台速度变化平滑度\nRecipe截取范围决定生成运动指令的有效区域\n刻蚀量阈值决定何时生成倍速扫描Recipe")
        info_label.setStyleSheet("color: #666; font-size: 15px; margin: 5px 0;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_btn = QPushButton("确定")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)

        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def get_transition_width(self):
        """获取过渡区宽度设置"""
        return self.transition_input.value()

    def get_recipe_range(self):
        """获取Recipe截取范围设置"""
        return self.recipe_input.value()

    def get_uniformity_threshold(self):
        """获取均一性判定阈值设置"""
        return self.uniformity_input.value()

    def get_speed_threshold(self):
        """获取刻蚀量阈值设置"""
        return self.speed_threshold_input.value()
