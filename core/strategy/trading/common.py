import datetime
import pandas as pd
import backtrader as bt
from common.logger import create_log
import settings

logger = create_log("trade_strategy_common")


class TradeRecordManager:
    def __init__(self):
        self.trade_records = []

    def add_trade_record(self, trade_id, date, action, price, size, total_amount, commission, order_type, status):
        self.trade_records.append(
            TradeRecord(trade_id, date, action, price, size, total_amount, commission, order_type, status))

    def transform_to_dataframe(self):
        return pd.DataFrame([record.__dict__ for record in self.trade_records])


class TradeRecord:
    """
    :param trade_id: 交易唯一标识
    :param date: 交易日期
    :param action: 交易动作
    :param price: 交易价格
    :param size: 交易数量
    :param total_amount: 交易总金额
    :param commission: 佣金费用
    :param order_type: 订单类型
    :param status: 订单状态
    """

    def __init__(self, trade_id, date, action, price, size, total_amount, commission, order_type, status):
        if type(date) is datetime.date:
            # 将datetime.date转换为pandas Timestamp
            self.date = pd.Timestamp(date)
            # self.date = date.strftime('%Y-%m-%d')
        elif type(date) is str:
            # 将字符串转换为pandas Timestamp
            self.date = pd.Timestamp(date)
            # self.date = date
        else:
            logger.info(type(date))
            raise ValueError('date must be datetime.date or str')
        self.trade_id = trade_id
        self.action = action
        self.price = price
        self.size = size
        self.total_amount = total_amount
        self.commission = commission
        self.order_type = order_type
        self.status = status


class AssetRecordManager:
    def __init__(self):
        self.asset_records = []

    def add_asset_record(self, date, total_assets):
        self.asset_records.append(AssetRecord(date, total_assets))

    def transform_to_dataframe(self):
        return pd.DataFrame([record.__dict__ for record in self.asset_records])


class AssetRecord:
    def __init__(self, date, total_assets):
        if type(date) is datetime.date:
            # 将datetime.date转换为pandas Timestamp
            self.date = pd.Timestamp(date)
        elif type(date) is str:
            # 将字符串转换为pandas Timestamp
            self.date = pd.Timestamp(date)
        else:
            raise ValueError('date must be datetime.date or str')
        self.total_assets = total_assets


class StrategyBase(bt.Strategy):
    """
    交易策略基类，子类可覆盖trading_strategy_buy和trading_strategy_sell方法实现自定义交易策略，params参数为交易策略参数，
    子类可扩展更多交易策略参数
    """
    params = (
        # 交易股票最小单位（股）
        ('min_order_size', settings.MIN_ORDER_SIZE if hasattr(settings, 'MIN_ORDER_SIZE') else 100),
        # 最大持仓比例 = 总持仓股票数量 * 持仓股票价格 / 总资产
        ('max_portfolio_percent',
         settings.MAX_PORTFOLIO_PERCENT if hasattr(settings, 'MAX_PORTFOLIO_PERCENT') else 0.8),
        # 单笔交易百分比（买） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产
        ('max_single_buy_percent',
         settings.MAX_SINGLE_BUY_PERCENT if hasattr(settings, 'MAX_SINGLE_BUY_PERCENT') else 0.2),
        # 单笔交易百分比（卖） = 单笔交易费用（ 单笔交易股票价格 * 单笔交易量） / 总资产
        ('max_single_sell_percent',
         settings.MAX_SINGLE_SELL_PERCENT if hasattr(settings, 'MAX_SINGLE_SELL_PERCENT') else 0.3),

    )

    def __init__(self):
        self.asset_record_manager = AssetRecordManager()
        self.trade_record_manager = TradeRecordManager()
        # 初始化指标
        self.min_order_size = self.p.min_order_size
        self.max_portfolio_percent = self.p.max_portfolio_percent
        self.max_single_buy_percent = self.p.max_single_buy_percent
        self.max_single_sell_percent = self.p.max_single_sell_percent
        self.indicator = None
        self.order = None

        # 添加信号计数器
        self.buy_signals_count = 0
        self.sell_signals_count = 0
        self.executed_buys_count = 0
        self.executed_sells_count = 0

    def set_indicator(self, indicator):
        """设置交易策略使用的信号指标，卖点/买点指标等"""
        self.indicator = indicator

    def next(self):
        super().next()

    def trading_strategy_buy(self):
        pass

    def trading_strategy_sell(self):
        pass

    def notify_order(self, order):
        """订单状态通知，每笔订单状态改变都会触发"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            # 计算并记录实际佣金
            actual_commission = self.calculate_commission(order.executed.size, order.executed.price)
            order_date = self.data.datetime.date(0)
            if order.isbuy():
                logger.info(
                    f'【买入挂单成交】: 实际执行价格={order.executed.price:.2f}（含滑点）, 数量={order.executed.size}')
                self.executed_buys_count += 1
                self.trade_record_manager.add_trade_record(
                    trade_id=order.ref,
                    date=order_date,
                    action='B',
                    price=order.executed.price,
                    size=abs(order.executed.size),
                    total_amount=order.executed.price * order.executed.size,
                    commission=actual_commission['total_commission'],  # 实际佣金在notify_trade中计算
                    order_type='buy',
                    status=order.status
                )
            elif order.issell():
                logger.info(
                    f'【卖出挂单成交】: 实际执行价格={order.executed.price:.2f}（含滑点）, 数量={order.executed.size}')
                self.executed_sells_count += 1
                self.trade_record_manager.add_trade_record(
                    trade_id=order.ref,
                    date=order_date,
                    action='S',
                    price=order.executed.price,
                    size=abs(order.executed.size),
                    total_amount=order.executed.price * order.executed.size,
                    commission=actual_commission['total_commission'],  # 实际佣金在notify_trade中计算
                    order_type='sell',
                    status=order.status
                )

            self.asset_record_manager.add_asset_record(date=order_date, total_assets=self.broker.getvalue())
            logger.info(f"【实际交易手续费】: {actual_commission['total_commission']:.2f}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.info('订单 取消/保证金不足/拒绝')

        self.order = None

    def notify_trade(self, trade):
        """交易状态通知，平仓完成才会触发，部分平仓不会触发"""
        if not trade.isclosed:
            return

        logger.info(f'【已清仓，交易利润】: 毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f}')

    def calculate_commission(self, size, price):
        """使用原生方法计算总手续费"""
        # 获取当前使用的佣金模型
        comminfo = self.broker.getcommissioninfo(self.data)
        # 直接调用原生方法获取总手续费
        total_commission = comminfo._getcommission(size, price, pseudoexec=False)

        return {
            'total_commission': total_commission
        }

