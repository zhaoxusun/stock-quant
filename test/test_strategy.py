from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from settings import stock_data_root

logger = create_log('test_strategy')


if __name__ == "__main__":
    # 设置CSV路径
    # kline_csv_path = stock_data_root / "baostock/sh.600519_A股贵州茅台_20230103_20251013.csv"
    # kline_csv_path = stock_data_root / "akshare/00700_港股00700_20210104_20251013.csv"
    init_cash = 5000000
    # 启动回测-单个股票
    kline_csv_path = stock_data_root / "futu/HK.00700_腾讯控股_20210104_20250127.csv"
    # run_backtest_enhanced_volume_strategy(kline_csv_path,init_cash)
    # 启动回测-批量股票
    kline_csv_path_folder = stock_data_root / "futu"
    run_backtest_enhanced_volume_strategy_multi(folder_path=kline_csv_path_folder, init_cash=5000000)
