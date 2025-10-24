import backtrader as bt
import pandas as pd

from common.logger import create_log
from core.strategy.trading.trading_strategy_common import EnhancedVolumeStrategy
from core.visualization.visual_tools_plotly import plotly_draw
from settings import stock_data_root
from pathlib import Path

logger = create_log('quant_manage')

class HKCommission(bt.CommInfoBase):
    """香港市场佣金模型"""
    params = (
        ('commission', 0.0003),  # 佣金率0.03%
        ('mincommission', 3),  # 最低佣金
        ('currency', 'HKD'),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('stamp_duty', 0.0013),  # 印花税0.13%
        ('transaction_levy', 0.000027),  # 交易征费0.0027%
        ('transaction_fee', 0.00005),  # 交易费0.005%
        ('trading_system_fee', 0.5),  # 交易系统使用费0.5港币/笔
        ('settlement_fee', 0.00002),  # 股份交收费0.002%
        ('min_settlement_fee', 2),  # 最低交收费2港币
        ('max_settlement_fee', 100),  # 最高交收费100港币
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        # 佣金计算
        commission = max(value * self.p.commission, self.p.mincommission)
        stamp_duty = value * self.p.stamp_duty
        transaction_levy = value * self.p.transaction_levy
        transaction_fee = value * self.p.transaction_fee
        # 交收费（有上下限）
        settlement_fee = value * self.p.settlement_fee
        settlement_fee = max(min(settlement_fee, self.p.max_settlement_fee), self.p.min_settlement_fee)

        return commission + stamp_duty + transaction_levy + transaction_fee + self.p.trading_system_fee + settlement_fee


def run_backtest_enhanced_volume_strategy_multi(folder_path, init_cash):
    """
    批量运行增强成交量策略回测
    :param folder_path: 包含CSV文件的文件夹路径
    :param init_cash: 初始资金
    """
    folder = Path(folder_path)
    for file in folder.glob("*.csv"):
        run_backtest_enhanced_volume_strategy(file, init_cash)

def run_backtest_enhanced_volume_strategy(csv_path, init_cash):
    logger.info("=" * 60)
    logger.info("【程序启动】VolumeIndicatorStrategy回测程序")
    logger.info(f"【目标文件】{csv_path}")
    logger.info("=" * 60)

    cerebro = bt.Cerebro()
    logger.info("=" * 60)
    logger.info("【回测配置】开始初始化回测参数")

    # 配置交易参数
    cerebro.broker.set_cash(init_cash)
    cerebro.broker.addcommissioninfo(HKCommission())
    cerebro.broker.set_slippage_fixed(0.3)
    cerebro.broker.set_coc(True)

    logger.info(f"【资金配置】初始资金：{init_cash:,.2f} 港元 | 佣金率：0.03% | 滑点：0.3 港元")
    logger.info("=" * 60)

    # 加载数据
    try:
        data = get_data_form_csv(csv_path)
    except Exception as e:
        logger.warning(f"【回测终止】数据加载失败：{str(e)}")
        return
    cerebro.adddata(data)

    # 检查数据量
    data_length = len(data.p.dataname)
    logger.info(f"【数据检查】有效数据量：{data_length} 天")
    if data_length < 50:
        logger.info(f"【风险提示】数据量较少，可能影响策略信号有效性！")

    # 添加策略和分析器
    cerebro.addstrategy(EnhancedVolumeStrategy)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="total_return", timeframe=bt.TimeFrame.NoTimeFrame)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")

    # 启动回测
    logger.info("=" * 60)
    logger.info(f"【回测启动】初始资金：{cerebro.broker.getcash():,.2f} 港元")
    try:
        start_date = data.p.dataname.index[0].date()
        end_date = data.p.dataname.index[-1].date()
        logger.info(f"回测周期：{start_date} ~ {end_date}")
    except Exception:
        pass
    logger.info("=" * 60)

    # 执行回测
    logger.info("【回测执行】正在运行回测...")
    try:
        results = cerebro.run()
    except Exception as e:
        logger.warning(f"【回测失败】执行出错：{str(e)}")
        return
    strategy = results[0]

    # 打印回测结果
    logger.info("=" * 60)
    logger.info("【回测结果汇总】")
    logger.info("=" * 60)

    # 收益情况
    try:
        total_return = list(strategy.analyzers.total_return.get_analysis().values())[0] * 100
        final_cash = cerebro.broker.getvalue()
        logger.info(f"1. 收益情况：总收益率={total_return:.2f}% | 最终资金={final_cash:,.2f} 港元")
    except Exception as e:
        logger.warning(f"1. 收益情况：无法计算 ({str(e)})")

    # 风险指标
    try:
        max_dd = strategy.analyzers.drawdown.get_analysis()["max"]["drawdown"]
        logger.info(f"2. 风险指标：最大回撤={max_dd:.2f}%")
    except Exception as e:
        logger.warning(f"2. 风险指标：无法计算 ({str(e)})")

    # 交易统计
    try:
        trade_stats = strategy.analyzers.trade_analyzer.get_analysis()
        total_trades = trade_stats["total"]["total"]
        won_trades = trade_stats.get("won", {}).get("total", 0)
        win_rate = (won_trades / total_trades) * 100 if total_trades > 0 else 0
        logger.info(
            f"3. 交易统计：总交易={total_trades} | 盈利={won_trades} | 亏损={total_trades - won_trades} | 胜率={win_rate:.2f}%")
    except Exception as e:
        logger.warning(f"3. 交易统计：无法计算 ({str(e)})")

    # 信号统计
    try:
        logger.info(
            f"4. 信号统计：买入信号={strategy.buy_signals_count} | 卖出信号={strategy.sell_signals_count} | 实际买入={strategy.executed_buys_count} | 实际卖出={strategy.executed_sells_count}")
    except Exception as e:
        logger.warning(f"4. 信号统计：无法计算 ({str(e)})")


    # 可视化，暂时不用，用plotly代替可视化，plotly可视化更加强大，支持交互操作
    # try:
    #     logger.info("【图表生成】正在绘制回测图表...")
    #     cerebro.plot(style="candle", volume=True, iplot=False, figsize=(16, 12), barup="red", bardown="green")
    #     logger.info("【图表生成】图表已弹出，请查看")
    # except Exception as e:
    #     logger.warning(f"【图表提示】图表生成失败：{str(e)}")

    # plotly数据
    asset_record_manager = strategy.asset_record_manager
    asset_records_df = asset_record_manager.transform_to_dataframe()
    signal_record_manager = strategy.indicator.signal_record_manager
    signals_df = signal_record_manager.transform_to_dataframe()
    trade_record_manager = strategy.trade_record_manager
    trades_df = trade_record_manager.transform_to_dataframe()
    html_path = plotly_draw(kline_csv_path=csv_path, signal_records=signals_df, trade_records=trades_df, asset_records=asset_records_df, initial_capital=init_cash)
    logger.info(f"5. 回测可视化图表将保存至：{html_path}，对应股票数据：{csv_path}")
    logger.info("=" * 60)
    logger.info("【回测结束】\n")




def get_file_names_pathlib(folder_path):
    """
    使用pathlib遍历指定文件夹下的所有文件，返回文件名列表
    """
    folder = Path(folder_path)
    # 获取所有文件（不包括目录）
    files = [f.name for f in folder.rglob('*') if f.is_file()]
    # 如果需要完整路径，使用以下代码
    # files = [str(f) for f in folder.rglob('*') if f.is_file()]

    return files


def get_data_form_csv(csv_path):
    df = pd.read_csv(
        csv_path,
        parse_dates=['date'],  # 解析date列为datetime类型
        index_col='date'  # 将date列设为索引，方便按日期查询
    )

    class CustomPandasData(bt.feeds.PandasData):
        params = (
            ('datetime', None),
            ('open', 'open'), ('high', 'high'), ('low', 'low'), ('close', 'close'), ('volume', 'volume'),
            ('openinterest', -1)
        )

    data_feed = CustomPandasData(dataname=df)
    data_feed.timeframe = bt.TimeFrame.Days
    data_feed.compression = 1

    return data_feed

# if __name__ == "__main__":
#     # 设置CSV路径
#     kline_csv_path = stock_data_root / "futu/HK.00700_腾讯控股_20210104_20250127.csv"
#     init_cash = 5000000
#     # 启动回测-单个股票
#     run_backtest_enhanced_volume_strategy(kline_csv_path,init_cash)
#     # 启动回测-批量股票
#     run_backtest_enhanced_volume_strategy_multi(folder_path=stock_data_root / "futu", init_cash=5000000)
#
