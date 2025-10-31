from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from core.strategy.trading.volume.enhanced_volume import EnhancedVolumeStrategy
from settings import stock_data_root
from core.stock.manager_futu import get_user_selected_stock_list, get_single_hk_stock_history
import futu as ft
import datetime


logger = create_log('test_strategy')


if __name__ == "__main__":

    # k线数据获取
    # end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    # start_time = (datetime.datetime.now() - datetime.timedelta(days=365*4)).strftime("%Y-%m-%d")
    #
    # stock_list = get_user_selected_stock_list()
    # for stock_code in stock_list:
    #     get_single_hk_stock_history(
    #         stock_code=stock_code,
    #         start_date=start_time,
    #         end_date=end_date,
    #         adjust_type=ft.AuType.QFQ
    #     )

    # 启动回测-单个股票
    kline_csv_path = stock_data_root / "futu/HK.00175_吉利汽车_20211028_20251027.csv"
    run_backtest_enhanced_volume_strategy(kline_csv_path, EnhancedVolumeStrategy)
    # 启动回测-批量股票
    kline_csv_path_folder = stock_data_root / "akshare"
    run_backtest_enhanced_volume_strategy_multi(kline_csv_path_folder, EnhancedVolumeStrategy)
