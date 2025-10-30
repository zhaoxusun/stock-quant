import datetime

import backtrader as bt
import numpy as np
import pandas as pd

from common.logger import create_log
from core.strategy.indicator.indicator_strategy_common import EnhancedVolumeIndicator
import settings

logger = create_log("trade_strategy_common")


class TradeRecordManager:
    def __init__(self):
        self.trade_records = []

    def add_signal_record(self, date, action, signal_type, shares):
        self.trade_records.append(TradeRecord(date, action, signal_type, shares))

    def transform_to_dataframe(self):
        return pd.DataFrame([record.__dict__ for record in self.trade_records])


class TradeRecord:
    def __init__(self, date, action, signal_type, shares):
        if type(date) is datetime.date:
            # 将datetime.date转换为pandas Timestamp
            self.date = pd.Timestamp(date)
            # self.date = date.strftime('%Y-%m-%d')
        elif type(date) is str:
            # 将字符串转换为pandas Timestamp
            self.date = pd.Timestamp(date)
            # self.date = date
        else:
            raise ValueError('date must be datetime.date or str')
        self.action = action
        self.signal_type = signal_type
        self.shares = shares


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


class EnhancedVolumeStrategy(bt.Strategy):
    """
    使用增强成交量指标的交易策略
    """
    params = (
        # 是否打印日志
        ('print_log', settings.PRINT_LOG if hasattr(settings, 'PRINT_LOG') else True),
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
        self.indicator = EnhancedVolumeIndicator()
        self.order = None

        # 添加信号计数器
        self.buy_signals_count = 0
        self.sell_signals_count = 0
        self.executed_buys_count = 0
        self.executed_sells_count = 0

    def next(self):
        # 检查是否有未完成的订单
        if self.order:
            return

        # 执行交易信号
        if not np.isnan(self.indicator.lines.enhanced_buy_signal[0]):
            logger.info(f'*** 增强买入信号 ***: {self.data.close[0]}')
            self.trading_strategy_buy()
            self.buy_signals_count += 1
        elif not np.isnan(self.indicator.lines.enhanced_sell_signal[0]):
            logger.info(f'*** 增强卖出信号 ***: {self.data.close[0]}')
            self.trading_strategy_sell()
            self.sell_signals_count += 1
        # TODO 暂不执行普通的买入信号和普通卖出信号
        # elif not np.isnan(self.indicator.lines.main_buy_signal[0]):
        #     logger.info(f'主买入信号: {self.data.close[0]}')
        #     self.trading_strategy_buy()
        #     self.buy_signals_count += 1
        # elif not np.isnan(self.indicator.lines.main_sell_signal[0]):
        #     logger.info(f'主卖出信号: {self.data.close[0]}')
        #     self.trading_strategy_sell()
        #     self.sell_signals_count += 1
        self.asset_record_manager.add_asset_record(date=self.data.datetime.date(0), total_assets=self.broker.getvalue())

    def trading_strategy_buy(self):
        # 计算可用于购买的资金
        # 总资产价值（包含当前持仓股票价值）
        total_asset_value = self.broker.getvalue()
        # 可用资金（不包含当前持仓股票价值）
        available_cash = self.broker.getcash()
        # 计算单次购买最大可用资金
        max_single_trade_cash = total_asset_value * self.max_single_buy_percent
        # 计算最大可购买金额（考虑最大持仓限制）
        max_portfolio_value = total_asset_value * self.max_portfolio_percent
        # 取较小值作为实际可用购买金额
        usable_cash = min(available_cash, max_single_trade_cash, max_portfolio_value)

        # 计算可购买的股数，确保至少购买最小交易单位
        # 当前股票价格（最新收盘价）
        price = self.data.close[0]
        if price > 0 and usable_cash >= price * self.min_order_size:
            # 计算基于可用资金的股数
            shares_based_on_cash = usable_cash // price
            # 确保股数为整数且至少为最小交易单位
            buy_size = max(shares_based_on_cash, self.min_order_size)
            if buy_size >= self.min_order_size:
                # 确保购买股数为最小交易单位的整数倍
                buy_size = buy_size // self.min_order_size * self.min_order_size
                logger.info(
                    f"【买入挂单】: 可用资金={available_cash:.2f}, 总资产={total_asset_value:.2f}, 买入股数={buy_size}，理论买入价格={price:.2f}，买入后持仓={self.position.size + buy_size}")
                # 计算并打印手续费
                trade_commission = self.calculate_commission(buy_size, price)
                if trade_commission:
                    logger.info(f"【理论交易手续费】: {trade_commission['total_commission']:.8f}")
                self.order = self.buy(size=buy_size, price=price)
                self.trade_record_manager.add_signal_record(self.data.datetime.date(0), 'B', 'strong_buy', buy_size)
            else:
                logger.info(f"资金有限，预购买股数={buy_size}，小于最小交易单位={self.min_order_size}，无法购买")
        else:
            logger.info(f"资金有限，可用资金={usable_cash:.2f}，成交最小金额={price * self.min_order_size:.2f}，无法购买")

    def trading_strategy_sell(self):
        # 有持仓时
        if self.position:
            # 当前持仓股数（绝对值）
            current_position_size = self.position.size
            # 当前可卖出股数，确保购买股数为最小交易单位的整数倍
            remaining_sell_size = current_position_size // self.min_order_size * self.min_order_size
            # 当前资产价值（包含当前持仓股票价值）
            total_asset_value = self.broker.getvalue()
            # 可用资金（不包含当前持仓股票价值）
            available_cash = self.broker.getcash()
            # 单次最大可卖出股数，确保卖出股数为最小交易单位的整数倍
            price = self.data.close[0]
            max_single_sell_size = total_asset_value * self.max_single_sell_percent / price // self.min_order_size * self.min_order_size
            # 确保卖出数量至少为最小交易单位
            sell_size = min(remaining_sell_size, max_single_sell_size)
            if sell_size >= self.min_order_size:
                logger.info(
                    f"【卖出挂单】: 可用资金={available_cash:.2f}, 总资产={total_asset_value:.2f}, 当前持仓={self.position.size}, 卖出股数={sell_size}，理论卖出价格={price:.2f}，卖出后持仓={current_position_size - sell_size}")
                # 计算并打印手续费
                trade_commission = self.calculate_commission(sell_size, price)
                if trade_commission:
                    logger.info(f"【理论交易手续费】: {trade_commission['total_commission']:.8f}")
                self.order = self.sell(size=sell_size, price=price)
                self.trade_record_manager.add_signal_record(self.data.datetime.date(0), 'S', 'strong_sell', sell_size)
            else:
                logger.info(
                    f"持仓有限，持仓股数={current_position_size}，预卖出股数={sell_size}，小于最小交易单位={self.min_order_size}，无法卖出")
        else:
            logger.info("当前无持仓，不执行卖出操作")

    def notify_order(self, order):
        """订单状态通知，每笔订单状态改变都会触发"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                logger.info(
                    f'【买入挂单成交】: 实际执行价格={order.executed.price:.2f}（含滑点）, 数量={order.executed.size}')
                self.executed_buys_count += 1
            elif order.issell():
                logger.info(
                    f'【卖出挂单成交】: 实际执行价格={order.executed.price:.2f}（含滑点）, 数量={order.executed.size}')
                self.executed_sells_count += 1
            # 计算并记录实际佣金
            actual_commission = self.calculate_commission(order.executed.size, order.executed.price)
            logger.info(f"【实际交易手续费】: {actual_commission['total_commission']:.8f}")

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.info('订单 取消/保证金不足/拒绝')

        self.order = None

    def notify_trade(self, trade):
        """交易状态通知，平仓完成才会触发，部分平仓不会触发"""
        if not trade.isclosed:
            return

        logger.info(f'交易利润: 毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f}')

    def calculate_commission(self, size, price):
        """使用原生方法计算总手续费"""
        # 获取当前使用的佣金模型
        comminfo = self.broker.getcommissioninfo(self.data)
        # 直接调用原生方法获取总手续费
        total_commission = comminfo._getcommission(size, price, pseudoexec=False)

        return {
            'total_commission': total_commission
        }
