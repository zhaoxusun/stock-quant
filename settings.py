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
result_root = project_root / 'result'


# 交易策略相关参数
MIN_ORDER_SIZE = 100    # 交易股票最小单位（股）
MAX_PORTFOLIO_PERCENT = 0.8 # 最大持仓比例 = 总持仓股票数量 * 持仓股票价格 / 总资产
MAX_SINGLE_BUY_PERCENT = 0.2    # 单笔交易百分比（买） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产
MAX_SINGLE_SELL_PERCENT = 0.3   # 单笔交易百分比（卖） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产


# 交易佣金相关参数
HK_COMMISSION = 0.0003  # 佣金率0.03%
HK_MIN_COMMISSION = 3  # 最低佣金
HK_CURRENCY = 'HKD'
HK_STAMP_DUTY = 0.001  # 印花税0.1%
HK_TRANSACTION_LEVY = 0.000042  # 交易征费0.0042%
HK_TRANSACTION_FEE = 0.0000565  # 交易费0.005565%
HK_TRADING_SYSTEM_FEE = 15  # 交易系统使用费15港币/笔
HK_SETTLEMENT_FEE = 0.00002  # 股份交收费0.002%
HK_MIN_SETTLEMENT_FEE = 2  # 最低交收费2港币
HK_MAX_SETTLEMENT_FEE = 100  # 最高交收费100港币
HK_SLIPPAGE = 0.3  # 滑点0.3港币

CN_COMMISSION = 0.0003  # 佣金率0.03%
CN_MIN_COMMISSION = 3  # 最低佣金
CN_CURRENCY = 'CNY'
CN_STAMP_DUTY = 0.00025 # 印花税0.05%，仅卖出收，所以买入+卖出相当于分别025%
CN_TRANSACTION_LEVY = 0.0000341  # 经手费0.00341%
CN_TRANSACTION_FEE = 0.00002  # 政管费0.002%
CN_TRADING_SYSTEM_FEE = 15  # 交易系统使用费15元/笔
CN_SETTLEMENT_FEE = 0.00002  # 过户费0.002%
CN_SLIPPAGE = 0.3  # 滑点0.3元


US_COMMISSION_PER_SHARE = 0.0049  # 佣金率0.0049%/股
US_MIN_COMMISSION = 0.99  # 最低佣金0.99美元
US_MAX_COMMISSION_RATE = 0.005  # 最高佣金率0.5%
US_CURRENCY = 'USD'
US_MIN_TRADING_SYSTEM_PER_SHARE = 0.005  # 交易系统使用费0.005美元/股
US_MAX_TRADING_SYSTEM_RATE = 0.005  # 交易系统使用费最高0.5%
US_MIN_TRADING_SYSTEM_FEE = 1  # 交易系统使用费最低1美元/笔
US_SETTLEMENT_FEE = 0.00003  # 股份交收费0.003%
US_SETTLEMENT_ACTIVITY_FEE_PER_SHARE = 0.000166  # 交易活动费0.000166美元/股
US_MIN_SETTLEMENT_ACTIVITY_FEE = 0.005  # 交易活动费0.01美元/笔，仅卖出收，相当于买卖各收0.005美元/笔
US_MAX_SETTLEMENT_ACTIVITY_FEE = 8.30  # 交易活动费8.30美元/笔
US_COMPREHENSIVE_AUDIT_SUPERVISION_FEE = 0.0000265  # 综合审计跟踪监管费0.0000265美元/笔
US_SLIPPAGE = 0.3  # 滑点0.3美元


# 交易本金
INIT_CASH = 5000000  # 初始资金5000000港币

