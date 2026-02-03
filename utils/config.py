from PyQt5.QtCore import QSettings, QStandardPaths
import os

class AppConfig:
    """应用程序配置管理类"""
    
    def __init__(self):
        # 创建并加载配置对象
        config_path = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        os.makedirs(config_path, exist_ok=True)
        self.settings = QSettings(os.path.join(config_path, "app_config.ini"), QSettings.IniFormat)
        
        # 设置默认值
        self.defaults = {
            "recent_files": [],
            "wafer_size": 200,
            "theme": "light",
            "language": "zh_CN",
            "last_export_path": QStandardPaths.writableLocation(QStandardPaths.DesktopLocation),
            "last_import_path": QStandardPaths.writableLocation(QStandardPaths.HomeLocation),
            "show_scatter": True,
            "extend_edge": False,
            "show_stats": False
        }
    
    def get(self, key):
        """获取配置值，如果没有则使用默认值"""
        return self.settings.value(key, self.defaults[key])
    
    def set(self, key, value):
        """设置配置值"""
        self.settings.setValue(key, value)
    
    def add_recent_file(self, file_path):
        """添加最近打开的文件"""
        recent_files = self.get("recent_files")
        if file_path in recent_files:
            recent_files.remove(file_path)
        recent_files.insert(0, file_path)
        recent_files = recent_files[:10]  # 最多保存10个
        self.set("recent_files", recent_files)
    
    def get_recent_files(self):
        """获取最近打开的文件列表"""
        return self.get("recent_files")
    
    def get_wafer_size(self):
        """获取当前的晶圆尺寸"""
        return self.get("wafer_size")
    
    def set_wafer_size(self, size):
        """设置当前的晶圆尺寸"""
        self.set("wafer_size", size)

config = AppConfig()
