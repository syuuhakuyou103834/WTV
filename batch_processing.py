import os
import re

def get_all_csv_files(folder):
    """获取文件夹中所有CSV文件路径（包括子文件夹），优先选择最新处理版本的文件"""
    csv_files = []

    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith('.csv'):
                full_path = os.path.join(root, file)
                csv_files.append(full_path)

    # 实现文件优先级选择逻辑
    selected_files = prioritize_files(csv_files)

    # 按文件名排序
    selected_files.sort(key=lambda x: os.path.basename(x))

    return selected_files

def prioritize_files(csv_files):
    """
    实现文件优先级选择逻辑：
    如果同时存在多个处理版本的文件（包括原始文件和不同轮次的处理后文件），
    优先选择剔除轮数最多的最新版本文件。
    """
    # 文件版本映射：{基础名: {轮数: 文件路径}}
    file_versions = {}

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        base_name, ext = os.path.splitext(filename)

        # 解析文件版本信息
        version_info = parse_file_version(filename)
        if version_info is None:
            continue

        original_base, round_num = version_info

        # 初始化基础名条目
        if original_base not in file_versions:
            file_versions[original_base] = {}

        # 添加版本信息
        file_versions[original_base][round_num] = file_path

    # 选择每个基础名的最高轮次文件
    selected_files = []
    for original_base, versions in file_versions.items():
        if versions:
            # 找到最高轮次
            max_round = max(versions.keys())
            selected_files.append(versions[max_round])

    return selected_files

def parse_file_version(filename):
    """
    解析文件名，提取基础名和轮数信息

    返回: (基础名, 轮数)

    示例:
    1201.csv -> (1201, 0)
    1201_error_deleted.csv -> (1201, 1)
    1201_error_deleted_round2.csv -> (1201, 2)
    1201_error_deleted_round3.csv -> (1201, 3)
    """
    # 匹配模式：基础名_error_deleted_round数字.csv
    pattern_round = r'^(.*)_error_deleted_round(\d+)\.csv$'
    match_round = re.match(pattern_round, filename, re.IGNORECASE)
    if match_round:
        base_name = match_round.group(1)
        round_num = int(match_round.group(2))
        return base_name, round_num

    # 匹配模式：基础名_error_deleted.csv
    pattern_first = r'^(.*)_error_deleted\.csv$'
    match_first = re.match(pattern_first, filename, re.IGNORECASE)
    if match_first:
        base_name = match_first.group(1)
        return base_name, 1

    # 匹配模式：普通基础名.csv
    if filename.lower().endswith('.csv'):
        base_name = filename[:-4]  # 去掉.csv
        return base_name, 0

    # 无法识别的格式
    return None

def get_file_priority_info(folder):
    """
    获取文件夹中文件的优先级信息，用于调试和用户通知
    返回: {
        'selected_files': 选择的文件列表,
        'skipped_files': 被跳过的文件列表,
        'version_details': 版本详情列表 [(基础名, 跳过的文件列表, 选择的文件)]
    }
    """
    csv_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith('.csv'):
                full_path = os.path.join(root, file)
                csv_files.append(full_path)

    # 分析文件版本
    file_versions = {}

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        version_info = parse_file_version(filename)
        if version_info is None:
            continue

        original_base, round_num = version_info

        # 初始化基础名条目
        if original_base not in file_versions:
            file_versions[original_base] = {}

        # 添加版本信息
        file_versions[original_base][round_num] = {
            'path': file_path,
            'filename': filename
        }

    # 生成结果
    selected_files = []
    skipped_files = []
    version_details = []

    for original_base, versions in file_versions.items():
        if versions:
            # 找到最高轮次
            max_round = max(versions.keys())
            selected_file_info = versions[max_round]
            selected_files.append(selected_file_info['path'])

            # 收集被跳过的文件
            skipped_in_group = []
            for round_num, file_info in versions.items():
                if round_num != max_round:
                    skipped_files.append(file_info['path'])
                    skipped_in_group.append(file_info['filename'])

            # 创建版本详情
            if skipped_in_group:
                version_details.append((
                    original_base,
                    skipped_in_group,
                    selected_file_info['filename']
                ))
            else:
                # 只有原始文件的情况
                version_details.append((
                    original_base,
                    [],
                    selected_file_info['filename']
                ))

    return {
        'selected_files': selected_files,
        'skipped_files': skipped_files,
        'version_details': version_details
    }
