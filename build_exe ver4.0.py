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
    print("晶圆膜厚可视化工具 - 打包程序")
    print("=" * 50)
    
    # 2. 清理旧打包文件
    print("[1/6] 清理旧打包文件...")
    dist_path = os.path.abspath("dist")
    build_path = os.path.abspath("build")
    
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    if os.path.exists(build_path):
        shutil.rmtree(build_path)
    
    # 3. 配置 PyInstaller 参数
    script_path = os.path.abspath("main.py")
    app_name = "晶圆膜厚可视化工具"
    
    pyinstaller_args = [
        script_path,            # 主脚本文件
        '--onefile',            # 打包成单个可执行文件
        '--windowed',           # 窗口应用 (不显示控制台)
        f'--icon={icon_path}',  # 图标文件
        f'--name={app_name}',   # 应用名称
        '--clean',              # 清理临时文件
        '--add-data=core;core',          # 添加 core 文件夹
        '--add-data=ui;ui',              # 添加 ui 文件夹
        '--add-data=utils;utils',        # 添加 utils 文件夹
        '--add-data=Data;Data',          # 添加示例数据文件夹
        '--add-data=WTV_icon.ico;.',    # 添加图标文件
        '--distpath=dist',              # 输出目录
        '--noconfirm',                  # 覆盖文件时不提示
        # 确保图标文件正确包含
        '--add-data=WTV_icon.ico;.', 
        '--icon=WTV_icon.ico',
    ]
    
    # 4. 执行打包
    print("[2/6] 开始打包应用程序...")
    PyInstaller.__main__.run(pyinstaller_args)
    
    # 5. 处理平台特定需求
    print("[3/6] 处理平台特定依赖...")
    # 这里可以添加平台特定的处理逻辑
    
    # 6. 创建完整的发布目录
    print("[4/6] 整理发布文件...")
    release_dir = os.path.join(dist_path, "WTV_ver4.0_release")
    os.makedirs(release_dir, exist_ok=True)
    
    # 移动可执行文件
    src_exe = os.path.join(dist_path, f"{app_name}.exe")
    dest_exe = os.path.join(release_dir, f"{app_name}.exe")
    shutil.move(src_exe, dest_exe)
    
    # 复制数据目录
    data_src = os.path.abspath("Data")
    data_dest = os.path.join(release_dir, "Data")
    if os.path.exists(data_src):
        shutil.copytree(data_src, data_dest)
    
    # 复制文档等额外文件 (可选)
    shutil.copy("README.md", release_dir)
    shutil.copy("LICENSE", release_dir)
    
    # 7. 复制依赖的 dll 文件
    print("[5/6] 复制依赖文件...")
    # 检查 Python 安装目录下是否有必要的 DLL 文件
    python_dir = os.path.dirname(sys.executable)
    possible_dlls = [
        "vcruntime140.dll",     # Visual C++ 运行时
        "msvcp140.dll",         # Visual C++ 运行时
        "vcruntime140_1.dll",   # Visual Studio 2019+ 运行时
        "concrt140.dll",        # ConcRT 运行时
        "mfc140u.dll",          # MFC 库 (如果使用)
        "mfc140.dll",           # MFC 库 (如果使用)
    ]
    
    for dll in possible_dlls:
        src_dll = os.path.join(python_dir, dll)
        if os.path.exists(src_dll):
            print(f"复制: {dll}")
            shutil.copy(src_dll, release_dir)
    
    # 8. 清除临时文件
    print("[6/6] 清理临时文件...")
    shutil.rmtree(build_path)  # 清理 build 目录
    
    print("\n" + "=" * 50)
    print(f"打包完成！请在此目录找到应用程序:")
    print(os.path.abspath(release_dir))
    print("\n应用程序文件结构:")
    print(f"  {app_name}.exe  - 主程序")
    if os.path.exists(data_dest):
        print(f"  Data/  - 示例数据目录")
        print(f"  README.md  - 说明文档")
        print(f"  LICENSE  - 许可证")
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

if __name__ == "__main__":
    package_application()
