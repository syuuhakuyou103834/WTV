import os
from PyQt5.QtWidgets import QFileDialog

def open_file_dialog(title="选择文件", parent=None, filter="数据文件 (*.csv *.txt);;所有文件 (*.*)"):
    """打开文件选择对话框"""
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getOpenFileName(
        parent, caption=title, filter=filter, options=options)
    return file_path, _

#def save_file_dialog(title="保存文件", parent=None, filter="所有文件 (*.*)"):
    """打开文件保存对话框"""
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getSaveFileName(
        parent, caption=title, filter=filter, options=options)
    return file_path

def save_file_dialog(title="保存文件", parent=None, filter="所有文件 (*.*)", default_path=""):
    """打开文件保存对话框"""
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getSaveFileName(
        parent, 
        caption=title, 
        directory=default_path,  # 添加默认路径支持
        filter=filter, 
        options=options
    )
    return file_path

def export_data(data, file_path):
    """将数据导出到CSV文件"""
    try:
        import pandas as pd
        import numpy as np
        
        if len(data) < 3:
            return False
        
        # 创建DataFrame
        df = pd.DataFrame(data, columns=['X', 'Y', 'Thickness'])
        
        # 保存文件
        if file_path.lower().endswith('.xlsx'):
            df.to_excel(file_path, index=False)
        else:
            if not file_path.lower().endswith('.csv'):
                file_path += '.csv'
            df.to_csv(file_path, index=False)
        
        return True
    except Exception as e:
        print(f"导出数据时出错: {e}")
        return False

def export_image(figure, file_path):
    """将图像导出到文件"""
    try:
        if not file_path:
            return False
        
        # 确保文件有扩展名
        if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf', '.svg')):
            file_path += '.png'
        
        # 保存图像
        figure.savefig(file_path, dpi=300, bbox_inches='tight')
        return True
    except Exception as e:
        print(f"导出图像时出错: {e}")
        return False
    

