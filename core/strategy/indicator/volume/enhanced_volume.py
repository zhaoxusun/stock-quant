import numpy as np
import backtrader as bt

from core.strategy.indicator.common import SignalRecordManager


class EnhancedVolumeIndicator(bt.Indicator):
    """
    基于成交量和多个技术指标的增强交易信号指示器
    包含成交量分析、RSI、布林带和KDJ指标的综合分析
    """
    lines = ('main_buy_signal', 'main_sell_signal', 'enhanced_buy_signal', 'enhanced_sell_signal')
    params = (
        ('n1', 1),  # 短期均线周期
        ('n2', 5),  # 中期均线周期
        ('n3', 20),  # 长期均线周期
        ('rsi_period', 14),  # RSI计算周期
        ('boll_period', 20),  # 布林带周期
        ('boll_width', 2),  # 布林带宽度倍数
        ('kdj_period', 9)  # KDJ周期
    )

    # 设置绘图参数，让信号在主图上显示
    plotinfo = dict(subplot=False)

    # 为每个信号线设置绘图样式
    plotlines = dict(
        main_buy_signal=dict(marker='', _plotskip=True),  # 不直接显示线
        main_sell_signal=dict(marker='', _plotskip=True),  # 不直接显示线
        enhanced_buy_signal=dict(marker='', _plotskip=True),  # 不直接显示线
        enhanced_sell_signal=dict(marker='', _plotskip=True)  # 不直接显示线
    )

    def __init__(self):
        self.signal_record_manager = SignalRecordManager()
        # 使用backtrader内置指标计算基础数据
        self.ma_vol_today = bt.indicators.MovingAverageSimple(self.data.volume, period=self.p.n1)
        self.ma_close_today = bt.indicators.MovingAverageSimple(self.data.close, period=self.p.n1)

        self.ma_vol_5 = bt.indicators.MovingAverageSimple(self.data.volume, period=self.p.n2)
        self.ma_close_5 = bt.indicators.MovingAverageSimple(self.data.close, period=self.p.n2)

        self.ma_vol_20 = bt.indicators.MovingAverageSimple(self.data.volume, period=self.p.n3)
        self.ma_close_20 = bt.indicators.MovingAverageSimple(self.data.close, period=self.p.n3)

        # 计算成交量标准差
        self.vol_std_5 = bt.indicators.StandardDeviation(self.data.volume, period=self.p.n2)
        self.vol_std_20 = bt.indicators.StandardDeviation(self.data.volume, period=self.p.n3)

        # RSI指标
        # 1. 前一日收盘价 (REF(CLOSE, 1))
        self.lc = self.data.close(-1)
        self.rsi_delta = self.data.close - self.lc
        self.rsi_up = bt.Max(self.rsi_delta, 0)
        self.rsi_down = abs(bt.Min(self.rsi_delta, 0))
        self.rsi_avg_up = bt.indicators.MovingAverageSimple(self.rsi_up, period=self.p.rsi_period)
        self.rsi_avg_down = bt.indicators.MovingAverageSimple(self.rsi_down, period=self.p.rsi_period)
        rsi_denominator = self.rsi_avg_up + self.rsi_avg_down + 1e-10
        self.lines.rsi = self.rsi_avg_up / rsi_denominator * 100
        # RSI处理初始数据不足的情况
        self.addminperiod(self.p.rsi_period + 1)

        # 布林带指标 - 使用内置指标
        self.boll = bt.indicators.BollingerBands(self.data.close, period=self.p.boll_period,
                                                 devfactor=self.p.boll_width)

        # KDJ指标 - 使用正确的周期参数（HHV使用3天而不是9天）
        self.lowest = bt.indicators.Lowest(self.data.low, period=self.p.kdj_period)  # LLV(LOW,9)
        self.highest_3 = bt.indicators.Highest(self.data.high, period=3)  # HHV(HIGH,3) - 这里是关键差异！
        self.lowest_3 = bt.indicators.Lowest(self.data.low, period=3)  # LLV(LOW,3) - 这里是关键差异！

        # 正确计算RSV - 这是导致信号差异的主要原因
        self.rsv = (self.data.close - self.lowest) / (self.highest_3 - self.lowest_3 + 1e-10) * 100

        # 使用SMA计算K、D、J线
        self.k = bt.indicators.MovingAverageSimple(self.rsv, period=3, plotname='K')
        self.d = bt.indicators.MovingAverageSimple(self.k, period=3, plotname='D')
        self.j = 3 * self.k - 2 * self.d

    def next(self):
        # 初始化信号值
        self.lines.main_buy_signal[0] = np.nan
        self.lines.main_sell_signal[0] = np.nan
        self.lines.enhanced_buy_signal[0] = np.nan
        self.lines.enhanced_sell_signal[0] = np.nan

        # 计算成交量相关指标
        vol_multiplier_5 = 0.9 + min(self.vol_std_5[0] / (self.ma_vol_5[0] + 1e-10), 0.6)
        vol_multiplier_20 = 0.8 + min(self.vol_std_20[0] / (self.ma_vol_20[0] + 1e-10), 0.5)

        # 计算买入/卖出计数
        vo_count_5 = self.ma_vol_today[0] - self.ma_vol_5[0] \
            if self.ma_vol_today[0] > self.ma_vol_5[0] * vol_multiplier_5 else 0
        vo_count_20 = self.ma_vol_today[0] - self.ma_vol_20[0] \
            if self.ma_vol_today[0] > self.ma_vol_20[0] * vol_multiplier_20 else 0

        # 判断连续3天阴线/阳线
        is_3_down = False
        is_3_up = False

        # 确保有足够的数据点
        if len(self) >= 3:
            # 检查前3天是否都是阴线 (收盘 < 开盘)
            is_3_down = all(self.data.close[-i] < self.data.open[-i] for i in range(0, 3))

            # 检查前3天是否都是阳线 (收盘 > 开盘)
            is_3_up = all(self.data.close[-i] > self.data.open[-i] for i in range(0, 3))


        # 计算均线相关买入/卖出计数
        ma_count_buy_5 = self.ma_close_5[0] - self.ma_close_today[0] \
            if is_3_down and self.ma_close_5[0] > self.ma_close_today[0] else 0
        ma_count_sell_5 = self.ma_close_today[0] - self.ma_close_5[0] \
            if is_3_up and self.ma_close_5[0] < self.ma_close_today[0] else 0

        ma_count_buy_20 = self.ma_close_20[0] - self.ma_close_today[0] \
            if is_3_down and self.ma_close_20[0] > self.ma_close_today[0] else 0
        ma_count_sell_20 = self.ma_close_today[0] - self.ma_close_20[0] \
            if is_3_up and self.ma_close_20[0] < self.ma_close_today[0] else 0

        # 计算买入/卖出信号
        buy_signal_5 = -vo_count_5 * ma_count_buy_5 if vo_count_5 > 0 and ma_count_buy_5 > 0 else 0
        sell_signal_5 = vo_count_5 * ma_count_sell_5 if vo_count_5 > 0 and ma_count_sell_5 > 0 else 0

        buy_signal_20 = -vo_count_20 * ma_count_buy_20 if vo_count_20 > 0 and ma_count_buy_20 > 0 else 0
        sell_signal_20 = vo_count_20 * ma_count_sell_20 if vo_count_20 > 0 and ma_count_sell_20 > 0 else 0

        # 计算信号计数
        buy_signal_count = (1 if buy_signal_5 != 0 else 0) + (1 if buy_signal_20 != 0 else 0)
        sell_signal_count = (1 if sell_signal_5 != 0 else 0) + (1 if sell_signal_20 != 0 else 0)

        # 主信号 - 使用BARSCOUNT(1)>50对应富途的条件
        main_buy = buy_signal_count >= 2 and len(self) > 50
        main_sell = sell_signal_count >= 2 and len(self) > 50

        # RSI条件
        rsi_oversold = self.rsi[0] < 30
        rsi_overbought = self.rsi[0] > 70

        # RSI穿越条件
        rsi_buy_condition = False
        rsi_sell_condition = False
        if len(self) > self.p.rsi_period:
            rsi_buy_condition = self.rsi[0] > 30 and self.rsi[-1] < 30
            rsi_sell_condition = self.rsi[0] < 70 and self.rsi[-1] > 70

        # 布林带条件
        boll_buy_cond = self.data.low[0] < self.boll.lines.bot[0]
        boll_sell_cond = self.data.high[0] > self.boll.lines.top[0]
        boll_confirm_buy = self.data.close[0] > self.boll.lines.bot[0]
        boll_confirm_sell = self.data.close[0] < self.boll.lines.top[0]

        # KDJ条件
        kdj_buy_cond = (self.k[0] < 20 and self.d[0] < 20) or self.j[0] < 20
        kdj_sell_cond = (self.k[0] > 80 and self.d[0] > 80) or self.j[0] > 80

        # 设置主信号值 - 按照用户要求的位置
        if main_buy:
            self.lines.main_buy_signal[0] = self.data.low[0] * 0.96  # 在LOW * 0.96的位置显示多
            self.signal_record_manager.add_signal_record(self.data.datetime.date(), 'normal_buy', '多')

        if main_sell:
            self.lines.main_sell_signal[0] = self.data.high[0] * 1.05  # 在HIGH * 1.05的位置显示
            self.signal_record_manager.add_signal_record(self.data.datetime.date(), 'normal_sell', '空')
        # TODO DEBUG不包含RSI指标，暂时不使用RSI，信号更多
        # enhanced_buy = main_buy and ((boll_buy_cond or boll_confirm_buy)) and kdj_buy_cond
        # enhanced_sell = main_sell and ((boll_sell_cond or boll_confirm_sell)) and kdj_sell_cond
        # 包含RSI指标，RSI过滤掉了很多信号指标
        enhanced_buy = main_buy and ((rsi_oversold or rsi_buy_condition) and (boll_buy_cond or boll_confirm_buy)) and kdj_buy_cond
        enhanced_sell = main_sell and ((rsi_overbought or rsi_sell_condition) and (boll_sell_cond or boll_confirm_sell)) and kdj_sell_cond
        # 设置增强信号值 - 按照用户要求的位置
        if enhanced_buy:
            self.lines.enhanced_buy_signal[0] = self.data.low[0] * 0.90  # 在LOW * 0.90的位置显示
            self.signal_record_manager.add_signal_record(self.data.datetime.date(), 'strong_buy', '强多')

        if enhanced_sell:
            self.lines.enhanced_sell_signal[0] = self.data.high[0] * 1.08  # 在HIGH * 1.08的位置显示
            self.signal_record_manager.add_signal_record(self.data.datetime.date(), 'strong_sell', '强空')


# if __name__ == '__main__':
#     signal_record_manager = SignalRecordManager()
#     signal_record_manager.add_signal_record(datetime.date(2024, 1, 15), 'normal_buy', '多')
#     signal_record_manager.add_signal_record(datetime.date(2024, 1, 16), 'normal_sell', '空')
#     signal_record_manager.add_signal_record(datetime.date(2024, 1, 17), 'strong_buy', '强多')
#     signal_record_manager.add_signal_record(datetime.date(2024, 1, 18), 'strong_sell', '强空')
#     signal_record_manager.add_signal_record('2024-01-15', 'normal_buy', '多')
#     record = signal_record_manager.transform_to_dataframe()
#     print(record)
