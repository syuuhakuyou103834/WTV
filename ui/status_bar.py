from PyQt5.QtWidgets import QStatusBar, QLabel
from PyQt5.QtGui import QColor, QPalette

class StatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_label = QLabel("状态：就绪")
        self.addWidget(self.status_label)
        self.normal_color = QColor("#446688")
        self.warning_color = QColor("#CC6600")
        self.error_color = QColor("#CC0000")
        
    def set_message(self, text, alert_level="normal"):
        self.status_label.setText(text)
        palette = self.palette()
        
        if alert_level == "warning":
            palette.setColor(QPalette.WindowText, self.warning_color)
        elif alert_level == "error":
            palette.setColor(QPalette.WindowText, self.error_color)
        else:
            palette.setColor(QPalette.WindowText, self.normal_color)
        
        self.status_label.setPalette(palette)
