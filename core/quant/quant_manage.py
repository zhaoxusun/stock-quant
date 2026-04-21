import os
from datetime import datetime

import backtrader as bt
import pandas as pd

from common.logger import create_log
from common.time_key import get_current_time
from core.strategy.trading.trading_commition import CommissionFactory
from core.visualization.visual_tools_plotly import plotly_draw
from pathlib import Path
import settings
from core.quant.backtest_record_manager import backtest_record_manager

logger = create_log('quant_manage')


def run_backtest_enhanced_volume_strategy_multi(kline_csv_folder_path, trading_strategy: bt.Strategy, init_cash=settings.INIT_CASH,
                                                backtest_mode=settings.BACKTEST_MODE):
    """
    批量运行增强成交量策略回测
    :param kline_csv_folder_path: 包含CSV文件的文件夹路径
    :param trading_strategy: 交易策略类
    :param init_cash: 初始资金
    :param backtest_mode: 回测模式，'BACKTEST'或'LIVE'，默认读取settings.BACKTEST_MODE
    """
    folder = Path(kline_csv_folder_path)
    for kline_csv_path in folder.glob("*.csv"):
        run_backtest_enhanced_volume_strategy(kline_csv_path, trading_strategy, init_cash, backtest_mode)

def run_backtest_enhanced_volume_strategy(csv_path, trading_strategy: bt.Strategy, init_cash=settings.INIT_CASH,
                                        backtest_mode=settings.BACKTEST_MODE):
    # 获取实际配置，优先使用传入参数，否则使用settings默认值
    actual_backtest_mode = backtest_mode if backtest_mode in settings.BACKTEST_MODE_LIST else settings.BACKTEST_MODE

    current_time = get_current_time()
    record_id = backtest_record_manager.create_record_id()
    relative_path = str(csv_path).replace(str(settings.stock_data_root) + '/', '')

    # 解析股票信息
    stock_code = ''
    stock_name = ''
    data_source = ''
    if '_' in relative_path:
        parts = relative_path.split('/')
        if len(parts) >= 2:
            file_name = parts[-1].replace('.csv', '')
            stock_code, stock_name = file_name.split('_', 1) if '_' in file_name else (file_name, '')
            data_source = parts[0] if len(parts) >= 2 else ''

    logger.info("=" * 60)
    logger.info("【程序启动】VolumeIndicatorStrategy回测程序")
    logger.info(f"【目标文件】{csv_path}")
    logger.info(f"【回测记录ID】{record_id}")
    logger.info("=" * 60)

    # 初始化记录数据
    record_data = {
        'record_id': record_id,
        'created_at': datetime.now().isoformat(),
        'init_data': {
            'csv_path': str(csv_path),
            'relative_path': relative_path,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'data_source': data_source,
            'strategy': trading_strategy.__name__,
            'backtest_mode': actual_backtest_mode,
            'init_cash': init_cash,
            'start_time': current_time
        }
    }

    logger.info("=" * 60)
    logger.info("【回测配置】开始初始化回测参数")
    # 加载数据
    try:
        data = get_data_form_csv(csv_path)
    except Exception as e:
        logger.warning(f"【回测终止】数据加载失败：{str(e)}")
        return
    # 检查数据量
    data_length = len(data.p.dataname)
    logger.info(f"【数据检查】有效数据量：{data_length} 天")
    if data_length < 50:
        logger.info(f"【风险提示】数据量较少，可能影响策略信号有效性！")

    market_series = data.p.dataname.get('market', pd.Series(['HK']))
    market = market_series.iloc[0] if not market_series.empty else None

    # 回测前数据
    start_date = data.p.dataname.index[0].strftime('%Y-%m-%d')
    end_date = data.p.dataname.index[-1].strftime('%Y-%m-%d')
    commission = CommissionFactory.get_commission(market)  # 获取对应市场的佣金配置
    record_data['before_data'] = {
        'start_date': start_date,
        'end_date': end_date,
        'data_days': data_length,
        'market': market,
        'initial_cash': init_cash,
        'commission_rate': commission.p.commission if 'commission' in dir() else 0,
        'slippage': commission.p.slippage if 'commission' in dir() else 0
    }

    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.broker.set_cash(init_cash)  # 设置初始资金
    commission = CommissionFactory.get_commission(market)   # 获取对应市场的佣金配置
    cerebro.broker.addcommissioninfo(commission)
    cerebro.broker.set_slippage_fixed(commission.p.slippage)  # 设置固定滑点
    cerebro.broker.set_coc(True)    # 当设置为True时，Backtrader会使用当前交易日的收盘价来执行订单，而不是默认的下一个交易日的开盘价
    logger.info(f"【资金配置】初始资金：{init_cash:,.2f} 港元 | 佣金率：{commission.p.commission:.2f}% | 滑点：{commission.p.slippage:.2f} 港元")
    logger.info("=" * 60)

    # 添加策略和分析器
    cerebro.addstrategy(trading_strategy)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="total_return", timeframe=bt.TimeFrame.NoTimeFrame)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade_analyzer")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe_ratio", timeframe=bt.TimeFrame.Days, riskfreerate=0.03)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name="annual_return")

    # 启动回测
    logger.info(f"【回测启动】初始资金：{cerebro.broker.getcash():,.2f} 港元")
    logger.info(f"【回测周期】：{start_date} ~ {end_date}")
    logger.info(f"【回测模式】：{actual_backtest_mode}")
    logger.info("=" * 60)

    # 执行回测
    logger.info("【回测执行】正在运行回测...")
    try:
        if actual_backtest_mode == 'BACKTEST':
            logger.info(f"【回测模式】{actual_backtest_mode}：历史回测，批量K线数据直接给Cerebro，一起计算")
            # 历史回测，批量K线数据直接给Cerebro，一起计算
            results = cerebro.run()
        elif actual_backtest_mode == 'LIVE':
            logger.info(f"【回测模式】{actual_backtest_mode}：实盘 / 模拟盘，每条K线喂给Cerebro，每条K线依次计算")
            # 实盘 / 模拟盘，每条K线喂给Cerebro，每条K线依次计算
            results = cerebro.run(runonce=False, preload=False)
        else:
            logger.warning(f"【回测失败】未知回测模式：{actual_backtest_mode}")
            return
    except Exception as e:
        logger.warning(f"【回测失败】执行出错：{str(e)}")
        return
    strategy = results[0]

    # 打印回测结果
    logger.info("【回测结果汇总】")
    logger.info("=" * 60)

    # 收益情况
    try:
        total_return = list(strategy.analyzers.total_return.get_analysis().values())[0] * 100
        final_cash = cerebro.broker.getvalue()
        # 计算年化收益
        start_date = data.p.dataname.index[0]
        end_date = data.p.dataname.index[-1]
        days = (end_date - start_date).days
        annual_return = (pow((1 + total_return/100), 365/days) - 1) * 100 if days > 0 else 0
        logger.info(f"1. 收益情况：总收益率={total_return:.2f}% | 年化收益={annual_return:.2f}% | 最终资金={final_cash:,.2f} 港元")
    except Exception as e:
        logger.warning(f"1. 收益情况：无法计算 ({str(e)})")

    # 风险指标
    try:
        max_dd = strategy.analyzers.drawdown.get_analysis()["max"]["drawdown"]
        # 计算Calmar比率
        try:
            annual_return = (pow((1 + total_return/100), 365/days) - 1) * 100 if days > 0 else 0
            calmar_ratio = annual_return / max_dd if max_dd > 0 else 0
        except:
            calmar_ratio = 0
        logger.info(f"2. 风险指标：最大回撤={max_dd:.2f}% | Calmar比率={calmar_ratio:.2f}")
    except Exception as e:
        logger.warning(f"2. 风险指标：无法计算 ({str(e)})")

    # 交易统计
    try:
        trade_stats = strategy.analyzers.trade_analyzer.get_analysis()
        total_trades = trade_stats["total"]["total"]
        won_trades = trade_stats.get("won", {}).get("total", 0)
        lost_trades = trade_stats.get("lost", {}).get("total", 0)
        win_rate = (won_trades / total_trades) * 100 if total_trades > 0 else 0
        # 计算盈亏比
        try:
            avg_win = trade_stats.get("won", {}).get("pnl", {}).get("average", 0)
            avg_loss = abs(trade_stats.get("lost", {}).get("pnl", {}).get("average", 1))
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        except:
            profit_factor = 0
        logger.info(
            f"3. 交易统计：总交易={total_trades} | 盈利={won_trades} | 亏损={lost_trades} | 胜率={win_rate:.2f}% | 盈亏比={profit_factor:.2f}")
    except Exception as e:
        logger.warning(f"3. 交易统计：无法计算 ({str(e)})")

    # 夏普比率
    try:
        sharpe_ratio = strategy.analyzers.sharpe_ratio.get_analysis().get("sharperatio", 0)
        sharpe_ratio = sharpe_ratio if sharpe_ratio is not None else 0
        logger.info(f"4. 风险调整收益：夏普比率={sharpe_ratio:.2f}")
    except Exception as e:
        logger.warning(f"4. 风险调整收益：无法计算 ({str(e)})")

    # 信号统计
    try:
        logger.info(
            f"5. 信号统计：买入信号={strategy.buy_signals_count} | 卖出信号={strategy.sell_signals_count} | 实际买入={strategy.executed_buys_count} | 实际卖出={strategy.executed_sells_count}")
    except Exception as e:
        logger.warning(f"5. 信号统计：无法计算 ({str(e)})")

    # 保存信号记录
    try:
        if hasattr(strategy, 'indicator') and hasattr(strategy.indicator, 'signal_record_manager'):
            # 获取信号记录并转换为DataFrame
            signals_df = strategy.indicator.signal_record_manager.transform_to_dataframe()

            if not signals_df.empty:
                signal_file_folder = settings.signals_root / relative_path.rsplit('.', 1)[0] / strategy.__class__.__name__
                os.makedirs(signal_file_folder, exist_ok=True)
                # 保存所有信号到一个文件
                signals_file_path = os.path.join(signal_file_folder, f"stock_signals_{current_time}.csv")
                signals_df.to_csv(signals_file_path, index=False, encoding='utf-8-sig')
                logger.info(f"6. 信号记录已保存至：{signals_file_path}")

    except Exception as e:
        logger.warning(f"信号保存失败：{str(e)}")

    html_file_path = settings.html_root / relative_path.rsplit('.', 1)[0] / strategy.__class__.__name__
    html_file_name = f"stock_with_trades_{current_time}.html"
    html_path = plotly_draw(csv_path, strategy, init_cash, html_file_name, html_file_path)
    logger.info(f"7. 回测可视化图表将保存至：{html_path}，对应股票数据：{csv_path}")
    logger.info("=" * 60)

    # 回测完成后保存记录
    try:
        # 获取已保存的信号文件路径
        signal_csv_relative_path = ''
        try:
            if hasattr(strategy, 'indicator') and hasattr(strategy.indicator, 'signal_record_manager'):
                signals_df = strategy.indicator.signal_record_manager.transform_to_dataframe()
                if not signals_df.empty:
                    signal_file_folder = settings.signals_root / relative_path.rsplit('.', 1)[0] / strategy.__class__.__name__
                    signals_file_path = os.path.join(signal_file_folder, f"stock_signals_{current_time}.csv")
                    signal_csv_relative_path = signals_file_path.replace(str(settings.signals_root) + '/', '') if signals_file_path else ''
        except:
            pass

        record_data['after_data'] = {
            'result_html_path': str(html_path) if html_path else '',
            'result_html_relative_path': f"{relative_path.rsplit('.', 1)[0]}/{strategy.__class__.__name__}/{html_file_name}" if html_path else '',
            'signal_csv_relative_path': signal_csv_relative_path,
        }

        # 尝试添加收益数据
        try:
            record_data['after_data']['return_stats'] = {
                'total_return': total_return,
                'annual_return': annual_return,
                'final_cash': final_cash
            }
        except:
            pass

        # 尝试添加风险数据
        try:
            record_data['after_data']['risk_stats'] = {
                'max_drawdown': max_dd,
                'calmar_ratio': calmar_ratio
            }
        except:
            pass

        # 尝试添加交易数据
        try:
            record_data['after_data']['trade_stats'] = {
                'total_trades': total_trades,
                'won_trades': won_trades,
                'lost_trades': lost_trades,
                'win_rate': win_rate,
                'profit_factor': profit_factor
            }
        except:
            pass

        # 尝试添加夏普比率
        try:
            record_data['after_data']['sharpe_ratio'] = sharpe_ratio
        except:
            pass

        record_data['complete_time'] = datetime.now().isoformat()

        backtest_record_manager.save(record_data)
    except Exception as e:
        logger.warning(f"保存回测记录失败: {str(e)}")

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
            ('open', 'open'), ('high', 'high'), ('low', 'low'), ('close', 'close'), ('volume', 'volume'),('market', 'market'),
            ('openinterest', -1)
        )

    data_feed = CustomPandasData(dataname=df)
    data_feed.timeframe = bt.TimeFrame.Days
    data_feed.compression = 1

    return data_feed

if __name__ == "__main__":
    # 设置CSV路径
    from settings import stock_data_root
    from core.strategy.trading.volume.enhanced_volume import EnhancedVolumeStrategy

    init_cash = 5000000
    # 执行回测
    csv_path = stock_data_root / "futu/HK.00700_腾讯控股_20220414_20260414.csv"
    # 启动回测-单个股票
    run_backtest_enhanced_volume_strategy(csv_path, EnhancedVolumeStrategy, init_cash)
    # 启动回测-批量股票
    run_backtest_enhanced_volume_strategy_multi(stock_data_root / "futu", EnhancedVolumeStrategy, init_cash)
#