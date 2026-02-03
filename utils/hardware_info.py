import wmi
import winreg
import os

def get_hardware_ids():
    result = {}
    try:
        # 连接WMI服务
        conn = wmi.WMI()
        
        # 获取CPU ID
        for processor in conn.Win32_Processor():
            result["CPU ID"] = processor.ProcessorId.strip()
            break  # 只取第一颗CPU
        
        # 获取硬盘序列号（第一个物理硬盘）
        for disk in conn.Win32_DiskDrive():
            if "fixed" in disk.MediaType.lower():  # 过滤固定磁盘
                result["Disk Serial"] = disk.SerialNumber.strip().replace(' ', '')
                break
        
        # 获取主板UUID
        for board in conn.Win32_ComputerSystemProduct():
            result["smBIOS UUID"] = board.UUID
            break
        
    except Exception as e:
        print(f"WMI查询错误: {str(e)}")
        result["Error"] = "WMI访问失败"

    # 获取Windows产品ID (注册表)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        )
        product_id, _ = winreg.QueryValueEx(key, "ProductId")
        winreg.CloseKey(key)
        result["Windows Product ID"] = product_id
    except:
        result["Windows Product ID"] = "读取失败"

    # 获取MachineGuid (注册表)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography"
        )
        machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        result["Machine GUID"] = machine_guid
    except:
        result["Machine GUID"] = "读取失败"

    # 添加用户名
    result["UserName"] = os.getlogin()

    return result

# 保持独立运行时的功能
if __name__ == "__main__":
    print("正在收集硬件标识信息...")
    print("-" * 50)
    hardware_info = get_hardware_ids()
    
    # 输出格式化为许可证文件格式
    license_fields = {
        "CPU ID": "CID",
        "Disk Serial": "DID",
        "smBIOS UUID": "BID",
        "Windows Product ID": "WID",
        "Machine GUID": "MID",
        "UserName": "UID"
    }
    
    for hw_name, license_code in license_fields.items():
        print(f"{license_code}:{hardware_info.get(hw_name, 'N/A')}")
    
    print("-" * 50)
    print("信息收集完成")
    print("请复制上述内容保存为 Liscense.txt 文件")
