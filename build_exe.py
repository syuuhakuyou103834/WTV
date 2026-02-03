import os
import sys
import PyInstaller.__main__
import shutil

def package_application():
    try:
        # 检查是否安装了 PyInstaller
        import PyInstaller
    except ImportError:
        print("PyInstaller 未安装，请使用 pip 安装: pip install pyinstaller")
        sys.exit(1)
    
    # 1. 检查图标文件是否存在
    icon_path = os.path.abspath("WTV_icon.ico")
    if not os.path.exists(icon_path):
        input(f"错误: 未找到图标文件 WTV_icon.ico，请放置在项目根目录\n按 Enter 退出...")
        sys.exit(1)
    
    print("=" * 50)
    print("晶圆膜厚可视化工具 4.2 - 打包程序")
    print("=" * 50)
    
    # 2. 清理旧打包文件
    print("[1/6] 清理旧打包文件...")
    dist_path = os.path.abspath("dist")
    build_path = os.path.abspath("build")
    
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    
    # 3. 配置 PyInstaller 参数 - 添加新模块支持
    script_path = os.path.abspath("main.py")
    app_name = "晶圆膜厚可视化工具 4.2.1"
    
    # 特别注意新增的模块路径
    pyinstaller_args = [
        script_path,                # 主脚本文件
        '--onefile',                # 打包成单个可执行文件
        '--windowed',               # 窗口应用 (不显示控制台)
        f'--icon={icon_path}',      # 图标文件
        f'--name={app_name}',       # 应用名称
        '--clean',                  # 清理临时文件
        # 添加核心模块
        '--add-data=core;core',
        # 添加UI模块 - 包含新添加的卷积积分和Recipe分析UI
        '--add-data=ui;ui',
        # 添加工具模块
        '--add-data=utils;utils',
        # 添加数据目录 - 包含Recipe分析和卷积结果
        '--add-data=Data;Data',
        # 添加图标文件
        '--add-data=WTV_icon.ico;.',
        # 指定输出目录
        '--distpath=dist',
        '--noconfirm',              # 覆盖文件时不提示
        # 隐藏导入警告
        '--hidden-import=scipy.spatial.transform._rotation_groups',
        '--hidden-import=sklearn.utils._weight_vector',
        '--hidden-import=sklearn.neighbors.typedefs',
    ]
    
    # 4. 执行打包
    print("[2/6] 开始打包应用程序...")
    PyInstaller.__main__.run(pyinstaller_args)
    
    # 5. 处理平台特定需求
    print("[3/6] 处理平台特定依赖...")
    if sys.platform == "win32":
        # Windows平台需要确保包含Visual C++运行时
        python_dir = os.path.dirname(sys.executable)
        runtime_dlls = [
            "vcruntime140.dll", 
            "vcruntime140_1.dll",
            "msvcp140.dll",
            "concrt140.dll"
        ]
        for dll in runtime_dlls:
            src = os.path.join(python_dir, dll)
            if os.path.exists(src):
                print(f"包含运行时DLL: {dll}")
    
    # 6. 创建完整的发布目录
    print("[4/6] 整理发布文件...")
    release_dir = os.path.join(dist_path, "WTV_4.2_release")
    os.makedirs(release_dir, exist_ok=True)
    
    # 移动可执行文件
    src_exe = os.path.join(dist_path, f"{app_name}.exe")
    dest_exe = os.path.join(release_dir, f"{app_name}.exe")
    shutil.move(src_exe, dest_exe)
    
    # 复制数据目录 (尤其确保recipe_analysis、convolution_results和Config可用)
    data_src = os.path.abspath("Data")
    data_dest = os.path.join(release_dir, "Data")
    if os.path.exists(data_src):
        if not os.path.exists(data_dest):
            shutil.copytree(data_src, data_dest)

        # 确保Config文件夹存在
        config_dest = os.path.join(data_dest, "Config")
        os.makedirs(config_dest, exist_ok=True)

        # 如果Config文件夹中没有配置文件，创建默认配置
        default_config_file = os.path.join(config_dest, "app_config.json")
        if not os.path.exists(default_config_file):
            import json
            default_config = {
                "stage_center_x": 0.0,
                "stage_center_y": 0.0
            }
            with open(default_config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            print(f"创建默认配置文件: {default_config_file}")
    else:
        # 如果源数据目录不存在，创建必要的子目录
        os.makedirs(os.path.join(data_dest, "recipe_analysis"), exist_ok=True)
        os.makedirs(os.path.join(data_dest, "convolution_results"), exist_ok=True)
        os.makedirs(os.path.join(data_dest, "Config"), exist_ok=True)

        # 创建默认配置文件
        default_config_file = os.path.join(data_dest, "Config", "app_config.json")
        import json
        default_config = {
            "stage_center_x": 0.0,
            "stage_center_y": 0.0
        }
        with open(default_config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        print(f"创建默认配置文件: {default_config_file}")
    
    # 添加额外的示例文件 (可选)
    example_files = ["README.md", "LICENSE"]
    for file in example_files:
        if os.path.exists(file):
            shutil.copy(file, release_dir)
    
    # 7. 复制必要的依赖文件
    print("[5/6] 复制依赖文件...")
    # 包含Matplotlib的mpl-data目录
    mpl_data_dir = ""
    try:
        import matplotlib
        mpl_data_dir = matplotlib.get_data_path()
    except ImportError:
        pass
    
    if mpl_data_dir and os.path.exists(mpl_data_dir):
        mpl_dest = os.path.join(release_dir, "mpl-data")
        shutil.copytree(mpl_data_dir, mpl_dest, dirs_exist_ok=True)
        # 添加环境变量以确保matplotlib能找到数据
        with open(os.path.join(release_dir, "set_env.bat"), "w") as f:
            f.write(f"@echo off\n")
            f.write(f'set MATPLOTLIBDATA="{mpl_dest}"\n')
            f.write(f'start "" "{dest_exe}"\n')
    
    # 创建直接运行的可执行文件包装器
    create_launcher(release_dir, dest_exe)
    
    # 8. 清除临时文件
    print("[6/6] 清理临时文件...")
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    
    print("\n" + "=" * 50)
    print(f"打包完成！请在此目录找到应用程序:")
    print(os.path.abspath(release_dir))
    print("\n应用程序文件结构:")
    print(f"  {app_name}.exe      - 主程序")
    print(f"  WTV_launcher.exe - 环境配置启动器")
    print(f"  Data/            - 数据目录 (包含recipe分析、卷积结果和Config配置)")
    print(f"  mpl-data/        - Matplotlib数据")
    print("=" * 50)
    
    # 9. 打开输出目录
    if sys.platform == "win32":
        os.startfile(release_dir)
    elif sys.platform == "darwin":
        import subprocess
        subprocess.call(["open", release_dir])
    else:
        import subprocess
        subprocess.call(["xdg-open", release_dir])

def create_launcher(release_dir, main_exe_path):
    """创建环境配置启动器"""
    # 创建启动器脚本 - 使用 ASCII 编码避免问题
    launcher_script = os.path.join(release_dir, "launcher.py")
    with open(launcher_script, "w", encoding="utf-8") as f:  # 指定 UTF-8 编码
        # 仅使用基本 ASCII 字符写脚本
        f.write("import os\n")
        f.write("import sys\n")
        f.write("import subprocess\n")
        f.write("import os.path as osp\n\n")  # 避免使用点分隔符
        f.write("def main():\n")
        f.write("    # 设置Matplotlib环境变量\n")
        f.write('    base_dir = osp.dirname(osp.abspath(__file__))\n')
        f.write('    mpl_data_path = osp.join(base_dir, "mpl-data")\n')
        f.write('    os.environ["MATPLOTLIBDATA"] = mpl_data_path\n\n')
        f.write("    # 启动主程序\n")
        f.write('    exe_name = "{}"\n'.format(os.path.basename(main_exe_path)))
        f.write('    exe_path = osp.join(base_dir, exe_name)\n')
        f.write('    if osp.isfile(exe_path):\n')
        f.write('        subprocess.Popen([exe_path])\n')
        f.write('    else:\n')
        f.write('        print(f"File not found: {exe_path}")\n')
        f.write('\n')
        f.write('if __name__ == "__main__":\n')
        f.write('    main()\n')
    
    # 打包启动器 - 避免重复清理目录
    PyInstaller.__main__.run([
        launcher_script,
        '--onefile',
        '--windowed',
        '--distpath', release_dir,
        '--name', 'WTV_launcher',
        '--clean',
        '--noconfirm',
        '--workpath', os.path.join(release_dir, "_build_temp")  # 单独的工作目录
    ])
    
    # 清理临时文件 - 添加安全检查
    try:
        if os.path.exists(launcher_script):
            os.remove(launcher_script)
        
        temp_dir = os.path.join(release_dir, "_build_temp")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    except Exception as e:
        print(f"清理临时文件时出错: {e}")

if __name__ == "__main__":
    package_application()
