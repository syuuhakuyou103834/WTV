import os
import sys
from collections import OrderedDict
from PyQt5.QtWidgets import QMessageBox, QApplication

class LicenseValidator:
    def __init__(self, license_path="License.txt"):
        self.license_path = license_path
        self.hw_fields = [
            "CID",  # CPU ID
            "DID",  # Disk Serial
            "BID",  # smBIOS UUID
            "WID",  # Windows Product ID
            "MID",  # Machine GUID
            "UID"   # UserName
        ]
        
    def get_license_data(self):
        """读取许可证文件并返回有序字典"""
        if not os.path.exists(self.license_path):
            return None
            
        license_data = OrderedDict()
        try:
            with open(self.license_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and ":" in line:
                        key, value = line.split(":", 1)
                        license_data[key.strip()] = value.strip()
        except Exception as e:
            print(f"读取许可证错误: {str(e)}")
            return None
            
        return license_data
        
    def get_current_hardware_info(self):
        """返回当前计算机的硬件信息（与许可证格式一致）"""
        from utils.hardware_info import get_hardware_ids
        
        hw_info = get_hardware_ids()
        
        return OrderedDict([
            ("CID", hw_info.get("CPU ID", "N/A")),
            ("DID", hw_info.get("Disk Serial", "N/A")),
            ("BID", hw_info.get("smBIOS UUID", "N/A")),
            ("WID", hw_info.get("Windows Product ID", "N/A")),
            ("MID", hw_info.get("Machine GUID", "N/A")),
            ("UID", os.getlogin())
        ])
        
    def validate(self):
        """验证许可证是否有效"""
        # 检查许可证文件是否存在
        if not os.path.exists(self.license_path):
            QMessageBox.critical(
                None, 
                "许可证错误", 
                f"未找到许可证文件: {self.license_path}\n程序无法启动！"
            )
            return False
            
        # 读取许可证数据
        license_hw = self.get_license_data()
        if not license_hw:
            QMessageBox.critical(
                None, 
                "许可证错误", 
                "许可证文件格式不正确或损坏！"
            )
            return False
            
        # 获取当前硬件信息
        current_hw = self.get_current_hardware_info()
        
        # 对比所有硬件信息
        invalid_fields = []
        
        for field in self.hw_fields:
            if field in current_hw and field in license_hw:
                if current_hw[field] != license_hw[field]:
                    invalid_fields.append(field)
        
        # 如果有不匹配的字段
        if invalid_fields:
            msg = "<b>注册信息不匹配！</b><br><br>"
            msg += "<table>"
            msg += "<tr><th>字段</th><th>许可证值？？</th><th>当前值？？</th></tr>"
            for field in invalid_fields:
                msg += f"<tr><td></td><td></td><td style='color:red'>您的计算机未授权</td></tr>"
                #msg += f"<tr><td>{field}</td><td>{license_hw[field]}</td><td style='color:red'>{current_hw[field]}</td></tr>"
            msg += "</table>"
            msg += "<br>请联系系统管理员获取有效许可证文件。"
            
            QMessageBox.critical(
                None, 
                "许可证验证失败", 
                msg
            )
            return False
            
        return True
