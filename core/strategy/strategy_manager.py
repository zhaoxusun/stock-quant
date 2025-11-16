import backtrader as bt
import importlib
import pkgutil
import os
import sys
from core.strategy.trading.common import StrategyBase
from common.logger import create_log
import inspect

logger = create_log("strategy_manager")


class StrategyManager:

    def __init__(self):
        self.strategy_list = []
        self.strategy_map = {}
        self._auto_discover_strategies()

    def _auto_discover_strategies(self):
        """自动发现并注册所有继承自StrategyBase的策略类"""
        # 获取策略目录路径
        strategy_dir = os.path.join(os.path.dirname(__file__), 'trading')

        # 遍历trading目录下的所有子模块
        for _, module_name, _ in pkgutil.iter_modules([strategy_dir]):
            # 跳过common模块
            if module_name == 'common' or module_name.startswith('__'):
                continue

            try:
                # 构建完整模块路径
                full_module_path = f'core.strategy.trading.{module_name}'
                module = importlib.import_module(full_module_path)

                # 遍历模块中的所有属性，查找继承自StrategyBase的类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # 检查是否为类，是否继承自StrategyBase，且不是StrategyBase本身
                    if isinstance(attr, type) and issubclass(attr, StrategyBase) and attr != StrategyBase:
                        self.register_strategy(attr)
            except Exception as e:
                logger.error(f"Failed to load module {module_name}: {str(e)}")
                continue

        # 特殊处理volume子目录
        volume_dir = os.path.join(strategy_dir, 'volume')
        if os.path.exists(volume_dir):
            for _, module_name, _ in pkgutil.iter_modules([volume_dir]):
                if module_name.startswith('__'):
                    continue

                try:
                    full_module_path = f'core.strategy.trading.volume.{module_name}'
                    module = importlib.import_module(full_module_path)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and issubclass(attr, StrategyBase) and attr != StrategyBase:
                            self.register_strategy(attr)
                except Exception as e:
                    logger.error(f"Failed to load volume module {module_name}: {str(e)}")
                    continue

    def register_strategy(self, strategy_class):
        """注册一个策略类"""
        if strategy_class not in self.strategy_list:
            self.strategy_list.append(strategy_class)
            # 使用类名作为key，方便前端通过名称查找策略类
            self.strategy_map[strategy_class.__name__] = strategy_class
            logger.info(f"Registered strategy: {strategy_class.__name__}")

    def get_strategy(self, strategy_class_name):
        """根据类名获取策略类"""
        return self.strategy_map.get(strategy_class_name)

    def get_all_strategies(self):
        """获取所有注册的策略类"""
        return self.strategy_list

    def get_strategy_names(self):
        """获取所有注册的策略类名"""
        return list(self.strategy_map.keys())

    def get_strategy_source_code(self, strategy_class_name):
        """
        获取策略类的源代码

        参数:
            strategy_class_name: 策略类名称

        返回:
            包含源代码和文件路径的字典，如果找不到则返回None
        """
        strategy_class = self.get_strategy(strategy_class_name)
        if not strategy_class:
            return None

        try:
            # 获取类的源代码
            source_code = inspect.getsource(strategy_class)
            # 获取类所在的文件路径
            file_path = inspect.getfile(strategy_class)

            # 尝试获取完整的模块源代码
            module = inspect.getmodule(strategy_class)
            module_source = None
            if module:
                module_file_path = inspect.getfile(module)
                with open(module_file_path, 'r', encoding='utf-8') as f:
                    module_source = f.read()

            return {
                'class_name': strategy_class_name,
                'source_code': source_code,
                'file_path': file_path,
                'module_source': module_source,
                'module_file_path': module_file_path if module else file_path
            }
        except Exception as e:
            logger.error(f"Failed to get source code for {strategy_class_name}: {str(e)}")
            return None

# 创建全局的策略管理器实例
global_strategy_manager = StrategyManager()

if __name__ == '__main__':
    # 测试策略发现功能
    manager = StrategyManager()
    print("Available strategies:")
    for name in manager.get_strategy_names():
        print(f"- {name}")