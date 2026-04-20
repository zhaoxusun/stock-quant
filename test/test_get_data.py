import datetime
import futu as ft

from common.logger import create_log
import core.stock.manager_futu as manager_futu
import core.stock.manager_akshare as manager_akshare
import core.stock.manager_baostock as manager_baostock

logger = create_log('test_get_data')


def test_futu_get_data():


    '''
    futu get data
    '''

    manager_futu.get_single_hk_stock_history(
        stock_code="HK.00700",
        start_date="2021-01-01",
        end_date="2025-10-17",
        adjust_type=ft.AuType.QFQ
    )

    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_time = (datetime.datetime.now() - datetime.timedelta(days=365*4)).strftime("%Y-%m-%d")

    stock_list = manager_futu.get_user_selected_stock_list(group_name="特别关注")
    for stock_code in stock_list:
        manager_futu.get_single_hk_stock_history(
            stock_code=stock_code,
            start_date=start_time,
            end_date=end_date,
            adjust_type=ft.AuType.QFQ
        )

    manager_futu.get_single_cn_stock_history(
        stock_code="SH.510210",
        start_date=start_time,
        end_date=end_date,
        adjust_type=ft.AuType.QFQ
    )

def test_akshare_get_data():

    '''
    akshare get data
    '''

    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_time = (datetime.datetime.now() - datetime.timedelta(days=365*4)).strftime("%Y-%m-%d")
    # 示例1：获取单只港股数据
    manager_akshare.get_single_hk_stock_history(
        stock_code="00700",  # 腾讯控股
        start_date=start_time,
        end_date=end_date,
        adjust_type='qfq'
    )

    # 示例2：获取标普500 ETF(IVV)数据
    manager_akshare.get_single_us_history(
        stock_code="IVV",  # 标普500 ETF
        start_date=start_time,
        end_date=end_date
    )

def test_baostock_get_data():

    '''
    baostock get data
    '''

    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_time = (datetime.datetime.now() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")

    manager_baostock.get_single_cn_stock_history(
        stock_code="sh.600519",
        start_date=start_time,
        end_date=end_date,
        adjust_type='2'
    )

if __name__ == "__main__":
    # test_futu_get_data()
    test_akshare_get_data()
    # test_baostock_get_data()
