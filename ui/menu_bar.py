from PyQt5.QtWidgets import QMenuBar, QMenu
from PyQt5.QtGui import QKeySequence

def create_menu_bar(parent):
    menu_bar = QMenuBar()
    
    # 文件菜单
    file_menu = menu_bar.addMenu("文件(&F)")
    
    load_action = file_menu.addAction("加载数据(&L)")
    load_action.setShortcut(QKeySequence("Ctrl+O"))
    load_action.triggered.connect(parent.load_data)
    
    export_data_action = file_menu.addAction("导出数据(&S)")
    export_data_action.setShortcut(QKeySequence("Ctrl+S"))
    export_data_action.triggered.connect(parent.export_data)

    # +++ 新增菜单项: 导出到新坐标 +++
    export_new_coords_action = file_menu.addAction("导出数据至新坐标")
    export_new_coords_action.triggered.connect(parent.export_to_new_coords)
    
    file_menu.addSeparator()
    
    export_image_action = file_menu.addAction("导出图像(&E)")
    export_image_action.setShortcut(QKeySequence("Ctrl+E"))
    export_image_action.triggered.connect(parent.export_image)
    
    file_menu.addSeparator()
    exit_action = file_menu.addAction("退出(&X)")
    exit_action.triggered.connect(parent.close)
    
    # 数据菜单
    data_menu = menu_bar.addMenu("数据(&D)")
    
    extend_edge_action = data_menu.addAction("扩展至晶圆边缘")
    extend_edge_action.setCheckable(True)
    extend_edge_action.triggered.connect(parent.toggle_extend_boundary)
    
    show_scatter_action = data_menu.addAction("显示原始数据点")
    show_scatter_action.setCheckable(True)
    show_scatter_action.setChecked(True)
    show_scatter_action.triggered.connect(parent.toggle_scatter_visibility)
    
    data_menu.addSeparator()
    
    show_stats_action = data_menu.addAction("显示分布统计")
    show_stats_action.setCheckable(True)
    show_stats_action.triggered.connect(parent.toggle_distribution_stats)
    
    data_menu.addSeparator()

    # 新增菜单项：显示批量统计
    show_batch_stats_action = data_menu.addAction("显示批量统计")
    show_batch_stats_action.triggered.connect(parent.show_batch_statistics)

    data_menu.addSeparator()

    # 新增菜单项：异常值再次剔除
    outlier_removal_action = data_menu.addAction("异常值再次剔除")
    outlier_removal_action.triggered.connect(parent.trigger_batch_outlier_removal)

    range_select_action = data_menu.addAction("按厚度范围多选")
    range_select_action.setShortcut(QKeySequence("Ctrl+R"))
    range_select_action.triggered.connect(parent.select_by_thickness_range)
    
    # 操作菜单
    action_menu = menu_bar.addMenu("操作(&A)")
    add_point_action = action_menu.addAction("添加数据点")
    add_point_action.triggered.connect(parent.add_data_point)

    # 新增批量数据点处理菜单项 +++
    batch_edit_action = action_menu.addAction("批量数据点处理")
    batch_edit_action.triggered.connect(parent.batch_point_edit)
    
    return menu_bar
