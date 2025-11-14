import backtrader as bt
import importlib
import pkgutil
import os
import sys
import inspect
from common.logger import create_log

logger = create_log("indicator_manager")


class IndicatorManager:
    """
    信号指标管理器，专门用于管理和发现所有的信号指标类
    与交易策略管理器完全独立
    """

    def __init__(self):
        self.indicator_list = []
        self.indicator_map = {}
        self._auto_discover_indicators()

    def _auto_discover_indicators(self):
        """自动发现并注册所有继承自bt.Indicator的信号指标类"""
        # 获取指标目录路径
        indicator_dir = os.path.join(os.path.dirname(__file__), 'indicator')

        # 遍历indicator目录下的所有子模块
        for _, module_name, _ in pkgutil.iter_modules([indicator_dir]):
            # 跳过common模块
            if module_name == 'common' or module_name.startswith('__'):
                continue

            try:
                # 构建完整模块路径
                full_module_path = f'core.strategy.indicator.{module_name}'
                module = importlib.import_module(full_module_path)

                # 遍历模块中的所有属性，查找继承自bt.Indicator的类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # 检查是否为类，是否继承自bt.Indicator，且不是bt.Indicator本身
                    if isinstance(attr, type) and issubclass(attr, bt.Indicator) and attr != bt.Indicator:
                        self.register_indicator(attr)
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {str(e)}")
                continue

        # 特殊处理volume子目录
        volume_dir = os.path.join(indicator_dir, 'volume')
        if os.path.exists(volume_dir):
            for _, module_name, _ in pkgutil.iter_modules([volume_dir]):
                if module_name.startswith('__'):
                    continue

                try:
                    full_module_path = f'core.strategy.indicator.volume.{module_name}'
                    module = importlib.import_module(full_module_path)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, bt.Indicator) and attr != bt.Indicator:
                            self.register_indicator(attr)
                except Exception as e:
                    logger.error(f"Failed to load volume indicator module {module_name}: {str(e)}")
                    continue

    def register_indicator(self, indicator_class):
        """注册一个信号指标类"""
        if indicator_class not in self.indicator_list:
            self.indicator_list.append(indicator_class)
            # 使用类名作为key，方便前端通过名称查找指标类
            self.indicator_map[indicator_class.__name__] = indicator_class
            logger.info(f"Registered indicator: {indicator_class.__name__}")

    def get_indicator(self, indicator_class_name):
        """根据类名获取信号指标类"""
        return self.indicator_map.get(indicator_class_name)

    def get_all_indicators(self):
        """获取所有注册的信号指标类"""
        return self.indicator_list

    def get_indicator_names(self):
        """获取所有注册的信号指标类名"""
        return list(self.indicator_map.keys())

    def get_indicator_source_code(self, indicator_class_name):
        """
        获取信号指标类的源代码

        参数:
            indicator_class_name: 指标类名称

        返回:
            包含源代码和文件路径的字典，如果找不到则返回None
        """
        indicator_class = self.get_indicator(indicator_class_name)
        if not indicator_class:
            return None

        try:
            # 获取类的源代码
            source_code = inspect.getsource(indicator_class)
            # 获取类所在的文件路径
            file_path = inspect.getfile(indicator_class)

            # 尝试获取完整的模块源代码
            module = inspect.getmodule(indicator_class)
            module_source = None
            if module:
                module_file_path = inspect.getfile(module)
                with open(module_file_path, 'r', encoding='utf-8') as f:
                    module_source = f.read()

            return {
                'class_name': indicator_class_name,
                'source_code': source_code,
                'file_path': file_path,
                'module_source': module_source,
                'module_file_path': module_file_path if module else file_path
            }
        except Exception as e:
            logger.error(f"Failed to get source code for {indicator_class_name}: {str(e)}")
            return None


# 创建全局的指标管理器实例
global_indicator_manager = IndicatorManager()
