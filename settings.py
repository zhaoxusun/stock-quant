from pathlib import Path


def get_project_root():
    current_file = Path(__file__).resolve()  # 当前文件的绝对路径
    root_markers = ['README.md', 'requirements-7.txt','requirements-13.txt']  # 根目录标志

    for parent in current_file.parents:
        if any((parent / marker).exists() for marker in root_markers):
            return parent
    raise FileNotFoundError("未找到项目根目录")


project_root = get_project_root()
data_root = project_root / 'data'
stock_data_root = data_root / 'stock'
log_root = project_root / 'log'
html_root = project_root / 'html'


# 交易策略相关参数
PRINT_LOG = True    #是否打印日志
MIN_ORDER_SIZE = 100    # 交易股票最小单位（股）
MAX_PORTFOLIO_PERCENT = 0.8 # 最大持仓比例 = 总持仓股票数量 * 持仓股票价格 / 总资产
MAX_SINGLE_BUY_PERCENT = 0.2    # 单笔交易百分比（买） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产
MAX_SINGLE_SELL_PERCENT = 0.3   # 单笔交易百分比（卖） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产


# 交易佣金相关参数
COMMISSION = 0.0003  # 佣金率0.03%
MIN_COMMISSION = 3  # 最低佣金
CURRENCY = 'HKD'
STAMP_DUTY = 0.0013  # 印花税0.13%
TRANSACTION_LEVY = 0.000027  # 交易征费0.0027%
TRANSACTION_FEE = 0.00005  # 交易费0.005%
TRADING_SYSTEM_FEE = 15  # 交易系统使用费0.5港币/笔
SETTLEMENT_FEE = 0.00002  # 股份交收费0.002%
MIN_SETTLEMENT_FEE = 2  # 最低交收费2港币
MAX_SETTLEMENT_FEE = 100  # 最高交收费100港币

# 交易本金
INIT_CASH = 5000000  # 初始资金5000000港币

