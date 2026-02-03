from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

def apply_theme(app, theme_name="light"):
    """应用主题样式到应用程序"""
    app.setStyle("Fusion")
    
    palette = QPalette()
    
    if theme_name == "dark":
        # 深色主题
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
    else:
        # 浅色主题
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, Qt.black)
        palette.setColor(QPalette.Base, Qt.white)
        palette.setColor(QPalette.AlternateBase, QColor(233, 233, 235))
        palette.setColor(QPalette.ToolTipBase, Qt.black)
        palette.setColor(QPalette.ToolTipText, Qt.black)
        palette.setColor(QPalette.Text, Qt.black)
        palette.setColor(QPalette.Button, QColor(220, 220, 220))
        palette.setColor(QPalette.ButtonText, Qt.black)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(0, 120, 215))
        palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
        palette.setColor(QPalette.HighlightedText, Qt.white)
    
    app.setPalette(palette)
    
    # 应用样式表
    apply_stylesheet(app, theme_name)

def apply_stylesheet(app, theme_name="light"):
    """应用自定义样式表"""
    stylesheet = ""
    
    if theme_name == "dark":
        stylesheet = """
            QMainWindow {
                background-color: #404040;
            }
            QGroupBox {
                border: 1px solid #555;
                border-radius: 4px;
                margin-top: 0.5em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: transparent;
                color: #aaa;
            }
            QLabel {
                color: #ccc;
            }
            QPushButton {
                background-color: #5A6269;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #6C757D;
            }
            QPushButton:pressed {
                background-color: #4A5259;
            }
            QStatusBar {
                background-color: #353535;
                color: #aaa;
                font-size: 9pt;
            }
        """
    else:
        stylesheet = """
            QMainWindow {
                background-color: #F0F0F0;
            }
            QGroupBox {
                border: 1px solid #CCC;
                border-radius: 4px;
                margin-top: 0.5em;
                padding-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                background-color: transparent;
                color: #555;
            }
            QLabel {
                color: #333;
            }
            QPushButton {
                background-color: #E0E0E0;
                color: #333;
                border: 1px solid #CCC;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F0F0F0;
                border-color: #999;
            }
            QPushButton:pressed {
                background-color: #D0D0D0;
            }
            QStatusBar {
                background-color: #E8E8E8;
                color: #666;
                font-size: 9pt;
            }
        """
    
    app.setStyleSheet(stylesheet)

def get_highlight_color():
    """获取高亮使用的颜色"""
    return QColor(255, 0, 0)  # 红色

def get_default_edge_color():
    """获取默认的边缘颜色"""
    return QColor(180, 180, 180)  # 灰色

def apply_app_style(app):
    """应用应用程序样式"""
    # 设置全局调色板
    palette = app.palette()
    palette.setColor(palette.Window, QColor(240, 240, 240))
    palette.setColor(palette.WindowText, QColor(0, 0, 0))
    palette.setColor(palette.Base, QColor(255, 255, 255))
    palette.setColor(palette.AlternateBase, QColor(233, 233, 235))
    palette.setColor(palette.ToolTipBase, QColor(255, 255, 220))
    palette.setColor(palette.ToolTipText, QColor(0, 0, 0))
    palette.setColor(palette.Text, QColor(0, 0, 0))
    palette.setColor(palette.Button, QColor(240, 240, 240))
    palette.setColor(palette.ButtonText, QColor(0, 0, 0))
    palette.setColor(palette.BrightText, QColor(255, 0, 0))
    palette.setColor(palette.Link, QColor(42, 130, 218))
    palette.setColor(palette.Highlight, QColor(187, 212, 238))
    palette.setColor(palette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    # 设置字体
    app.setFont(QFont("Microsoft YaHei", 9))


