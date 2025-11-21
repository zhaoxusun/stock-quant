"""
此脚本可以直接运行，用于定时任务的执行，不必依赖前端系统的运行。
与task_timer.py的区别在于，此脚本可以直接运行（修复了futu与python3.13之间的兼容问题），而task_timer.py需要依赖前端系统的运行。
直接运行此脚本时，会加载所有启用的任务，并按照配置的时间间隔执行。
"""


import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 向上三级目录
core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 向上两级目录
sys.path.insert(0, project_root)  # 优先使用项目根目录
sys.path.insert(1, core_dir)  # 添加core目录
import importlib

# 在导入任何模块之前，先修复signal模块的兼容性问题
try:
    # 导入Python标准库的signal模块
    import signal as std_signal

    # 检查是否有signal属性，如果没有则添加一个简单的实现
    if not hasattr(std_signal, 'signal'):
        def mock_signal(signum, handler):
            print(f"Mock signal handler registered for signal {signum}")
            return None


        # 补丁：添加signal属性到signal模块
        std_signal.signal = mock_signal
        print("已为Python 3.13环境修补signal模块")
    # 检查并添加SIGINT常量
    if not hasattr(std_signal, 'SIGINT'):
        std_signal.SIGINT = 2  # 大多数系统中SIGINT的标准值
        print("已为Python 3.13环境添加signal.SIGINT常量")

    print("已为Python 3.13环境修补signal模块")
except Exception as e:
    print(f"修复signal模块时出错: {str(e)}")

import importlib

# 现在尝试导入logger来初始化日志
try:
    from common.logger import create_log

    logger = create_log('task_timer')
    logger.info("信号模块兼容性补丁已应用")
except Exception as e:
    print(f"初始化日志时出错: {str(e)}")
    raise

# 尝试导入futu模块
manager_futu = None
futu_available = False
try:
    # 使用importlib动态导入以更好地控制导入过程
    manager_futu = importlib.import_module('core.stock.manager_futu')
    futu_available = True
    logger.info("成功导入futu模块")
except Exception as e:
    logger.error(f"导入futu模块失败: {str(e)}")
    # 即使futu导入失败，程序也会继续运行

import schedule
import time
import datetime
from common.logger import create_log
from common.util_html import signals_to_html, save_clean_html
from core.signal.signal_handler import signal_get, signals_analyze
from core.stock import manager_akshare, manager_baostock
from core.task.task_manager import TaskManager
from core.strategy.strategy_manager import global_strategy_manager
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy
import settings

logger = create_log('task_timer')

scheduled_jobs = []

def load_tasks():
    """
    从配置文件加载任务，过滤enabled为true的任务

    Returns:
        list: enabled为true的任务列表
    """
    try:
        task_manager = TaskManager()
        # 获取所有任务
        all_tasks = task_manager.read_all()
        # 过滤enabled为true的任务
        enabled_tasks = [task for task in all_tasks if task.get('enabled', False) is True]
        logger.info(f"加载了 {len(enabled_tasks)} 个启用的任务")
        return enabled_tasks
    except Exception as e:
        logger.error(f"加载任务失败: {str(e)}")
        return []


def get_kline_data(stock_config):
    """
    获取历史k线数据（第一步）

    Args:
        stock_config: 股票配置，包含market, data_source, stock_code, adjust_type

    Returns:
        tuple: (success, csv_path) 成功标志和CSV文件路径
    """
    try:
        market = stock_config.get('market')
        data_source = stock_config.get('data_source')
        stock_code = stock_config.get('stock_code')
        adjust_type = stock_config.get('adjust_type', 'qfq')
        logger.info(f"获取股票k线数据: market={market}, data_source={data_source}, stock_code={stock_code}, adjust_type={adjust_type}")
        # 处理股票代码，移除市场前缀（如果有）
        if not stock_code.startswith(f"{market.upper()}."):
            logger.error(f"股票代码格式错误: {stock_code}, market={market}")
            return False, None

        # 计算日期范围（默认4年）
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")

        # 根据数据源和市场调用对应的函数
        if data_source and market:
            if data_source == 'akshare' and market.upper() == 'HK':
                success, csv_name = manager_akshare.get_single_hk_stock_history(stock_code, start_date, end_date, adjust_type)
            elif data_source == 'akshare' and market.upper() == 'US':
                success, csv_name = manager_akshare.get_single_us_history(stock_code, start_date, end_date, adjust_type)
            elif data_source == 'baostock' and market.upper() == 'CN':
                success, csv_name = manager_baostock.get_stock_history(stock_code, start_date, end_date, adjust_type)
            elif data_source == 'futu' and futu_available and market.upper() == 'HK':
                success, csv_name = manager_futu.get_single_hk_stock_history(stock_code, start_date, end_date, adjust_type)
            elif data_source == 'futu' and futu_available and market.upper() == 'CN':
                success, csv_name = manager_futu.get_single_cn_stock_history(stock_code, start_date, end_date, adjust_type)
            else:
                logger.error(f"不支持的数据源或市场: data_source={data_source}, market={market}")
                return False, None
            if success and csv_name:
                csv_path = os.path.join(settings.stock_data_root, data_source, csv_name)
                stock_config['filename'] = csv_name
                logger.info(f"成功获取股票数据 {stock_config.get('stock_code')}: {csv_path}")
                return True, csv_path

        logger.error(f"不支持的数据源或市场: data_source={data_source}, market={market}")
        return False, None
    except Exception as e:
        logger.error(f"获取k线数据失败: {str(e)}")
        return False, None


def run_backtest(csv_path, backtest_config):
    """
    执行回测（第二步）

    Args:
        csv_path: CSV文件路径
        backtest_config: 回测配置，包含strategy, init_cash等

    Returns:
        bool: 是否成功
    """
    try:
        strategy_name = backtest_config.get('strategy', 'EnhancedVolumeStrategy')
        init_cash = backtest_config.get('init_cash', settings.INIT_CASH)

        # 获取策略类
        strategy_class = global_strategy_manager.get_strategy(strategy_name)
        if not strategy_class:
            logger.error(f"未找到策略类: {strategy_name}")
            return False

        # 执行回测
        run_backtest_enhanced_volume_strategy(csv_path, strategy_class, init_cash)
        logger.info(f"回测完成: {csv_path}, 策略: {strategy_name}")
        return True
    except Exception as e:
        logger.error(f"回测失败: {str(e)}")
        return False


def check_signals(target_stocks, task_id, days=365):
    """
    检查昨天买入信号
    """
    logger.info(f"开始检查{days}天前信号")

    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    start_day = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        signal_files = signal_get()
        signal_files.sort(key=lambda x: x['file_time'], reverse=True)
        logger.info(f"获取到 {len(signal_files)} 个信号文件")
        all_signal_files = []
        target_signal_file = []
        for signal_file in signal_files:
            all_signal_files.append(signal_file['file_path'])
        for signal_file in all_signal_files:
            for stock in target_stocks:
                data_source = stock["data_source"]
                stock_file = stock["filename"]
                if data_source in signal_file and stock_file.replace('.csv', '') in signal_file:
                    target_signal_file.append(signal_file)
        if len(target_signal_file) == 0:
            for stock in target_stocks:
                stock_file = stock["filename"]
                logger.error(f"没有信号文件包含股票 {stock_file.replace('.csv', '')}")
            return
        else:
            logger.info(f"找到 {len(target_signal_file)} 个信号文件包含目标股票")
        filters = {
                "start_date": start_day,
                "end_date": yesterday,
                "strategy_name": "",
                "stock_code": "",
                "signal_type": ""
            }

        combined_df = signals_analyze(target_signal_file, filters)
        summary = {
            'total_signals': len(combined_df),
            'buy_signals': len(combined_df[combined_df['signal_type'].str.contains('buy')]),
            'sell_signals': len(combined_df[combined_df['signal_type'].str.contains('sell')]),
            'unique_stocks': combined_df['stock_info'].nunique(),
            'unique_strategies': combined_df['strategy_name'].nunique()
        }
        signals = combined_df.to_dict('records')
        total_signals_count = len(combined_df)
        logger.info(f"昨天共有 {total_signals_count} 个信号")

        # 打印每个信号
        for signal in signals:
            logger.debug(f"信号: 股票={signal.get('stock_info')}, 日期={signal.get('date')}, "
                         f"信号类型={signal.get('signal_type')}, 策略={signal.get('strategy_name')}")
        html = signals_to_html(signals, filters, summary)
        save_clean_html(html, task_id)
        logger.info("成功检查昨天信号，并下载信号HTML完成")
        return True

    except Exception as e:
        logger.error(f"分析信号失败: {str(e)}")
        return False




def process_task(task):
    """
    处理单个任务，执行三步流程

    Args:
        task: 任务配置
    """
    task_id = task.get('id')
    task_name = task.get('name')
    logger.info(f"开始处理任务: {task_name} (ID: {task_id})")

    try:
        # 获取目标股票列表
        target_stocks = task.get('target_stocks', [])
        backtest_config = task.get('backtest_config', {})

        for stock_config in target_stocks:
            logger.info(f"处理股票: {stock_config.get('stock_code')}")

            # 第一步：查询历史k线数据
            success, csv_path = get_kline_data(stock_config)
            if not success or not csv_path:
                logger.error(f"跳过股票处理，因为获取k线数据失败")
                continue

            # 第二步：执行回测
            backtest_success = run_backtest(csv_path, backtest_config)
            if not backtest_success:
                logger.error(f"跳过股票处理，因为回测失败")
                continue

            # 第三步：生成信号详情 - 这一步在run_backtest_enhanced_volume_strategy中已经自动处理
            # 信号会保存到signals目录，图表会保存到html目录
            check_signals(target_stocks, task_id, days=365)
            logger.info(f"股票处理完成: {stock_config.get('stock_code')}")

        logger.info(f"任务处理完成: {task_name} (ID: {task_id})")
    except Exception as e:
        logger.error(f"处理任务时出错: {str(e)}")


def update_schedule():
    """
    更新调度任务
    """
    global current_tasks, scheduled_jobs

    # 获取新的任务列表
    new_tasks = load_tasks()

    # 清除现有的调度任务
    for job in scheduled_jobs:
        schedule.cancel_job(job)
    scheduled_jobs.clear()

    # 添加新的调度任务
    for task in new_tasks:
        schedule_time = task.get('schedule_time', '0 0 0 0 0')  # 默认每分钟执行
        task_id = task.get('id')

        # 解析cron表达式
        try:
            parts = schedule_time.split()
            if len(parts) == 5:
                minute, hour, day, month, weekday = parts

                # 根据cron表达式创建定时任务
                # 这里简化处理，实际应该更复杂地解析cron表达式
                job = schedule.every().day.at(f"{hour}:{minute}").do(process_task, task)
                scheduled_jobs.append(job)
                logger.info(f"添加定时任务: {task.get('name')}, 执行时间: {schedule_time}")
            else:
                # 默认每分钟执行
                job = schedule.every(1).minutes.do(process_task, task)
                scheduled_jobs.append(job)
                logger.info(f"添加定时任务: {task.get('name')}, 执行时间: 每分钟")
        except Exception as e:
            logger.error(f"解析调度时间失败: {schedule_time}, 错误: {str(e)}")

    current_tasks = new_tasks
    logger.info(f"调度任务更新完成，共 {len(scheduled_jobs)} 个任务")


def schedule_tasks():
    """
    启动任务调度
    """
    # 初始更新调度
    update_schedule()

    # 每小时重新加载配置
    schedule.every(1).hours.do(update_schedule)
    logger.info("启动定时任务调度器")
    # 每分钟更新一次调度任务配置
    last_update_time = time.time()
    update_interval = 60
    # 主循环
    while True:
        try:
            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                update_schedule()
                last_update_time = current_time
                logger.info("更新任务配置完成")
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"调度器错误: {str(e)}")
            time.sleep(60)  # 出错后等待一分钟再尝试


if __name__ == '__main__':
    try:
        logger.info("启动任务定时器")
        schedule_tasks()
    except KeyboardInterrupt:
        logger.info("用户中断，停止任务定时器")
    except Exception as e:
        logger.error(f"任务定时器异常: {str(e)}")