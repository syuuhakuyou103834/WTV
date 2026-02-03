import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from ui.wafer_thickness_visualizer_ui import main
from core.data_processing import add_data_point, delete_points
import matplotlib as mpl
import matplotlib.font_manager as fm
import platform
import numpy as np
from ui.main_window import MainWindow
from utils.license_validator import LicenseValidator  # 导入许可证验证器

def set_chinese_font():
    """配置Matplotlib中文字体支持"""
    # 根据操作系统选择字体
    try:
        if platform.system() == 'Windows':
            # 添加中文字体避免刻蚀模拟图表乱码
            font_path = "simhei.ttf"  # 如果系统中不存在，可以使用资源文件
            if os.path.exists(font_path):
                font_prop = fm.FontProperties(fname=font_path)
                mpl.rcParams['font.sans-serif'] = font_prop.get_name()
            else:
                mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
            mpl.rcParams['axes.unicode_minus'] = False
            print("Windows中文支持已配置")
            
        elif platform.system() == 'Darwin':
            mpl.rcParams['font.sans-serif'] = ['STHeiti', 'Arial Unicode MS']
            mpl.rcParams['axes.unicode_minus'] = False
            print("macOS中文支持已配置")
        else:
            mpl.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC']
            mpl.rcParams['axes.unicode_minus'] = False
            print("Linux中文支持已配置")
        
        return "\n中文字体支持已配置\n"
    except:
        return "\n警告：中文字体配置可能存在问题\n"
    
def main():
    app = QApplication(sys.argv)
    
    # 配置中文字体
    font_status = set_chinese_font()
    print(font_status)

    #  首先验证许可证
    validator = LicenseValidator()
    if not validator.validate():
        sys.exit(1)  # 验证失败退出
    
    # 设置应用程序图标
    icon_paths = [
        "WTV_icon.ico",
        os.path.join(os.getcwd(), "WTV_icon.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "WTV_icon.ico"),
    ]
    
    # 尝试设置应用图标（影响任务栏）
    for path in icon_paths:
        if os.path.exists(path):
            try:
                print(f"[Application] 尝试设置应用图标: {path}")
                app.setWindowIcon(QIcon(path))
                break
            except Exception as e:
                print(f"[Application] 图标设置失败: {e}")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    app.exec_()

if __name__ == "__main__":
    # 创建应用实例
    app = QApplication(sys.argv)
    
    # 配置中文字体
    font_status = set_chinese_font()
    print(font_status)
    
    # 运行主应用
    main()
