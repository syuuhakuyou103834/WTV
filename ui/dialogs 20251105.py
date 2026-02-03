from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QDialogButtonBox, 
                             QDoubleSpinBox, QGroupBox, QGridLayout,QPushButton,QMessageBox,QDialog, QFormLayout, QLabel, QLineEdit, QDialogButtonBox
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
