#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件管理模块
用于管理应用程序的配置信息，如载台中心坐标等
"""

import os
import json
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        # 配置文件路径
        self.config_dir = os.path.join("Data", "Config")
        self.config_file = os.path.join(self.config_dir, "app_config.json")

        # 默认配置
        self.default_config = {
            "stage_center_x": 0.0,
            "stage_center_y": 0.0,
            "transition_width": 50.0,
            "recipe_range": 160,
            "uniformity_threshold": 0.5,
            "speed_threshold": 140.0
        }

        # 确保配置目录存在
        self._ensure_config_dir()

        # 当前配置
        self._config = {}

        # 加载配置
        self.load_config()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        os.makedirs(self.config_dir, exist_ok=True)

    def load_config(self) -> Dict[str, Any]:
        """加载配置文件

        Returns:
            Dict: 配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # 与默认配置合并，确保所有必要的键都存在
                self._config = {**self.default_config, **loaded_config}
                print(f"配置文件加载成功: {self.config_file}")
            else:
                # 如果配置文件不存在，使用默认配置
                self._config = self.default_config.copy()
                self.save_config()  # 创建默认配置文件
                print(f"创建默认配置文件: {self.config_file}")

        except (json.JSONDecodeError, IOError) as e:
            print(f"加载配置文件失败，使用默认配置: {str(e)}")
            self._config = self.default_config.copy()

        return self._config

    def save_config(self) -> bool:
        """保存配置到文件

        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保目录存在
            self._ensure_config_dir()

            # 创建备份
            if os.path.exists(self.config_file):
                backup_file = self.config_file + ".backup"
                try:
                    import shutil
                    shutil.copy2(self.config_file, backup_file)
                except Exception as e:
                    print(f"创建配置文件备份失败: {str(e)}")

            # 保存配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)

            print(f"配置文件保存成功: {self.config_file}")
            return True

        except IOError as e:
            print(f"保存配置文件失败: {str(e)}")
            return False

    def get_stage_center_x(self) -> float:
        """获取载台中心X坐标

        Returns:
            float: 载台中心X坐标
        """
        return float(self._config.get("stage_center_x", 0.0))

    def get_stage_center_y(self) -> float:
        """获取载台中心Y坐标

        Returns:
            float: 载台中心Y坐标
        """
        return float(self._config.get("stage_center_y", 0.0))

    def set_stage_center_x(self, x: float) -> bool:
        """设置载台中心X坐标

        Args:
            x: X坐标值

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["stage_center_x"] = float(x)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置载台中心X坐标失败: {str(e)}")
            return False

    def set_stage_center_y(self, y: float) -> bool:
        """设置载台中心Y坐标

        Args:
            y: Y坐标值

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["stage_center_y"] = float(y)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置载台中心Y坐标失败: {str(e)}")
            return False

    def set_stage_center(self, x: float, y: float) -> bool:
        """同时设置载台中心X和Y坐标

        Args:
            x: X坐标值
            y: Y坐标值

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["stage_center_x"] = float(x)
            self._config["stage_center_y"] = float(y)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置载台中心坐标失败: {str(e)}")
            return False

    def get_transition_width(self) -> float:
        """获取过渡区宽度

        Returns:
            float: 过渡区宽度
        """
        return float(self._config.get("transition_width", 50.0))

    def set_transition_width(self, width: float) -> bool:
        """设置过渡区宽度

        Args:
            width: 过渡区宽度

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["transition_width"] = float(width)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置过渡区宽度失败: {str(e)}")
            return False

    def get_recipe_range(self) -> int:
        """获取Recipe截取范围

        Returns:
            int: Recipe截取范围
        """
        return int(self._config.get("recipe_range", 160))

    def set_recipe_range(self, range_val: int) -> bool:
        """设置Recipe截取范围

        Args:
            range_val: Recipe截取范围

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["recipe_range"] = int(range_val)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置Recipe截取范围失败: {str(e)}")
            return False

    def get_uniformity_threshold(self) -> float:
        """获取均一性判定阈值

        Returns:
            float: 均一性判定阈值
        """
        return float(self._config.get("uniformity_threshold", 0.5))

    def set_uniformity_threshold(self, threshold: float) -> bool:
        """设置均一性判定阈值

        Args:
            threshold: 均一性判定阈值

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["uniformity_threshold"] = float(threshold)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置均一性判定阈值失败: {str(e)}")
            return False

    def get_speed_threshold(self) -> float:
        """获取倍速扫描刻蚀量阈值

        Returns:
            float: 倍速扫描刻蚀量阈值
        """
        return float(self._config.get("speed_threshold", 140.0))

    def set_speed_threshold(self, threshold: float) -> bool:
        """设置倍速扫描刻蚀量阈值

        Args:
            threshold: 倍速扫描刻蚀量阈值

        Returns:
            bool: 设置是否成功
        """
        try:
            self._config["speed_threshold"] = float(threshold)
            return self.save_config()
        except (ValueError, TypeError) as e:
            print(f"设置倍速扫描刻蚀量阈值失败: {str(e)}")
            return False

    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置

        Returns:
            Dict: 完整的配置字典
        """
        return self._config.copy()

    def update_config(self, new_config: Dict[str, Any]) -> bool:
        """更新多个配置项

        Args:
            new_config: 新的配置字典

        Returns:
            bool: 更新是否成功
        """
        try:
            for key, value in new_config.items():
                self._config[key] = value
            return self.save_config()
        except Exception as e:
            print(f"更新配置失败: {str(e)}")
            return False

    def reset_to_default(self) -> bool:
        """重置为默认配置

        Returns:
            bool: 重置是否成功
        """
        self._config = self.default_config.copy()
        return self.save_config()

    def get_config_path(self) -> str:
        """获取配置文件路径

        Returns:
            str: 配置文件的完整路径
        """
        return self.config_file

    def is_config_exist(self) -> bool:
        """检查配置文件是否存在

        Returns:
            bool: 配置文件是否存在
        """
        return os.path.exists(self.config_file)


# 全局配置管理器实例
_config_manager = None


def get_config_manager() -> ConfigManager:
    """获取全局配置管理器实例

    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_stage_center() -> tuple:
    """便捷函数：获取载台中心坐标

    Returns:
        tuple: (x, y) 坐标元组
    """
    config = get_config_manager()
    return config.get_stage_center_x(), config.get_stage_center_y()


def set_stage_center(x: float, y: float) -> bool:
    """便捷函数：设置载台中心坐标

    Args:
        x: X坐标值
        y: Y坐标值

    Returns:
        bool: 设置是否成功
    """
    config = get_config_manager()
    return config.set_stage_center(x, y)


if __name__ == "__main__":
    # 测试代码
    print("测试配置管理器...")

    config = ConfigManager()

    # 测试读取
    print(f"载台中心X: {config.get_stage_center_x()}")
    print(f"载台中心Y: {config.get_stage_center_y()}")

    # 测试设置
    print("测试设置载台中心坐标...")
    if config.set_stage_center(10.5, -5.2):
        print("设置成功")
    else:
        print("设置失败")

    # 测试读取更新后的值
    print(f"更新后载台中心X: {config.get_stage_center_x()}")
    print(f"更新后载台中心Y: {config.get_stage_center_y()}")

    # 测试配置文件路径
    print(f"配置文件路径: {config.get_config_path()}")
    print(f"配置文件是否存在: {config.is_config_exist()}")