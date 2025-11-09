import numpy as np
from common.logger import create_log
from core.strategy.indicator.volume.single_volume import SingleVolumeIndicator
from core.strategy.trading.common import StrategyBase

logger = create_log("trade_strategy_volume")


class SingleVolumeStrategy(StrategyBase):
    """增强量化指标"""
    def __init__(self):
        super().__init__()
        self.set_indicator(SingleVolumeIndicator())   # 设置交易策略使用的信号指标，卖点/买点指标等

    def next(self):
        # 检查是否有未完成的订单
        if self.order:
            return
        # 执行普通的买入信号和普通卖出信号
        elif not np.isnan(self.indicator.lines.main_buy_signal[0]):
            logger.info(f'主买入信号: {self.data.close[0]}')
            self.trading_strategy_buy()
            self.buy_signals_count += 1
        elif not np.isnan(self.indicator.lines.main_sell_signal[0]):
            logger.info(f'主卖出信号: {self.data.close[0]}')
            self.trading_strategy_sell()
            self.sell_signals_count += 1

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
                    logger.info(f"【理论交易手续费】: {trade_commission['total_commission']:.2f}")
                self.order = self.buy(size=buy_size, price=price)
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
                    logger.info(f"【理论交易手续费】: {trade_commission['total_commission']:.2f}")
                self.order = self.sell(size=sell_size, price=price)
            else:
                logger.info(
                    f"持仓有限，持仓股数={current_position_size}，预卖出股数={sell_size}，小于最小交易单位={self.min_order_size}，无法卖出")
        else:
            logger.info("【卖出挂单失败，当前无持仓，不执行卖出操作】")

