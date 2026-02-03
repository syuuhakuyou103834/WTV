# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 主要配置段
a = Analysis(
    ['Wafer_Thickness_Visualizer-3.1.py'],   # 主程序路径
    pathex=[],                # 其他导入路径
    binaries=[],
    datas=[],                 # 需要包含的额外文件
    hiddenimports=[           # 需手动添加的隐藏导入
        'matplotlib.backends.backend_tkagg',
        'scipy.spatial.transform._rotation_groups',
        'scipy.spatial.ckdtree',
        'pandas._libs.tslibs.base',
        'openpyxl',
        'pytz',
        'sklearn.utils._weight_vector',
        'sklearn.neighbors.quad_tree',
        'sqlite3'
        
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Wafer_Thickness_Visualizer-3.1 ',          # 生成的EXE名称
    debug=False,                      # 禁用调试模式
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                         # 使用UPX压缩
    upx_exclude=['vcruntime140.dll'],
    runtime_tmpdir=None,
    console=False,                    # 不显示控制台窗口
    disable_windowed_traceback=False, 
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None, 
    icon='Wafer_Thickness_Visualizer.ico'                   # 自定义图标文件（可选）
)