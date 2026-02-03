from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from .main_window import MainWindow
import os

def main():
    app = QApplication([])
     # 尝试设置应用程序图标
    icon_paths = [
        "WTV_icon.ico",  # 开发环境中
        os.path.join(os.getcwd(), "WTV_icon.ico"),  # 打包后同级目录
        os.path.join(os.path.dirname(__file__), "WTV_icon.ico") # 打包后的路径
    ]
    
    for path in icon_paths:
        if os.path.exists(path):
            app_icon = QIcon(path)
            app.setWindowIcon(app_icon)
            break

    window = MainWindow()
    window.show()
    app.exec_()
