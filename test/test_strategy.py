from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from settings import stock_data_root
from core.strategy.trading.volume.enhanced_volume import EnhancedVolumeStrategy
logger = create_log('test_strategy')

if __name__ == "__main__":
    init_cash = 5000000
    csv_path = stock_data_root / "futu/HK.00700_腾讯控股_20220414_20260414.csv"
    # 启动回测-单个股票
    run_backtest_enhanced_volume_strategy(csv_path, EnhancedVolumeStrategy, init_cash)
    # 启动回测-批量股票
    # run_backtest_enhanced_volume_strategy_multi(stock_data_root / "futu", EnhancedVolumeStrategy,init_cash)