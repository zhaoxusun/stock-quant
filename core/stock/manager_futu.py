import datetime
import os

import futu as ft
import pandas as pd
from futu import RET_OK

from common.logger import create_log
from common.util_csv import save_to_csv
from settings import stock_data_root

pd.set_option('display.max_columns', None)  # 显示所有列
pd.set_option('display.max_rows', None)  # 显示所有行
pd.set_option('display.width', None)  # 自动调整宽度
pd.set_option('display.max_colwidth', None)  # 显示完整列内容
logger = create_log('manager_futu')


class TestIndicatorFetcher:
    def __init__(self, host='127.0.0.1', port=11111):
        """
        初始化 Test5IndicatorFetcher 类，连接到 futuopend 服务。

        :param host: futuopend 服务的主机地址，默认为 127.0.0.1
        :param port: futuopend 服务的端口号，默认为 11111
        """
        self.quote_ctx = ft.OpenQuoteContext(host=host, port=port)

    def get_history_kline(self, stock_code, start=None, end=None, autype=ft.AuType.QFQ, output_dir='futu'):
        """
        获取指定股票的历史 K 线数据，并可选保存到CSV文件

        :param stock_code: 股票代码，例如 'HK.00700'
        :param start: 开始日期，格式为 'YYYY-MM-DD'，默认为 None
        :param end: 结束日期，格式为 'YYYY-MM-DD'，默认为 None
        :param autype: 复权类型，默认为前复权 QFQ
        :param output_dir: CSV文件保存目录，默认为'futu'
        :return: 包含 K 线数据的 DataFrame
        """
        try:
            ret, data, page_req_key = self.quote_ctx.request_history_kline(
                stock_code, ktype=ft.KLType.K_DAY, start=start, end=end, autype=autype
            )

            # 检查返回值是否有效
            if ret != ft.RET_OK:
                logger.error(f"获取历史 K 线数据失败: {data}")
                return pd.DataFrame()

            # 检查data是否为有效的DataFrame
            if not isinstance(data, pd.DataFrame) or data.empty:
                logger.warning(f"获取的K线数据为空或格式不正确: {type(data)}")
                return pd.DataFrame()

            # 创建临时DataFrame用于处理原始数据
            df = data.copy()

            # 从股票代码解析市场信息
            market = ''
            if stock_code.startswith('HK.'):
                market = 'HK'
            elif stock_code.startswith('SH.') or stock_code.startswith('SZ.'):
                market = 'CN'
            else:
                market = 'UNKNOWN'

            # 保存原始股票信息
            stock_name = stock_code
            if 'name' in df.columns and not df.empty:
                try:
                    stock_name = df['name'].iloc[0]
                except Exception as e:
                    logger.warning(f"获取股票名称失败: {e}")

            # 创建符合要求格式的新DataFrame
            result_df = pd.DataFrame()

            # 映射字段到要求的格式，确保字段存在
            if 'time_key' in df.columns:
                try:
                    result_df['date'] = pd.to_datetime(df['time_key']).dt.date  # 只保留日期部分
                except Exception as e:
                    logger.warning(f"日期格式转换失败: {e}")
                    result_df['date'] = pd.NA
            else:
                logger.warning("数据中不包含'time_key'字段")
                result_df['date'] = pd.NA

            # 映射其他必需字段
            for source_col, target_col in [('open', 'open'), ('high', 'high'), ('low', 'low'),
                                           ('close', 'close'), ('volume', 'volume')]:
                if source_col in df.columns:
                    result_df[target_col] = df[source_col]
                else:
                    logger.warning(f"数据中不包含'{source_col}'字段")
                    result_df[target_col] = pd.NA

            # 映射成交额字段
            if 'turnover' in df.columns:
                result_df['amount'] = df['turnover']
            else:
                logger.warning("数据中不包含'turnover'字段，使用close*volume计算成交额")
                if 'close' in df.columns and 'volume' in df.columns:
                    result_df['amount'] = df['close'] * df['volume']
                else:
                    result_df['amount'] = pd.NA

            # 添加股票信息
            result_df['stock_code'] = stock_code
            result_df['stock_name'] = stock_name
            result_df['market'] = market

            # 保存到CSV文件
            try:
                # 获取日期范围并格式化
                start_date_formatted = 'unknown'
                end_date_formatted = 'unknown'
                if not result_df.empty and 'date' in result_df.columns and not result_df['date'].isna().all():
                    valid_dates = result_df['date'].dropna()
                    if not valid_dates.empty:
                        start_date_formatted = valid_dates.min().strftime('%Y%m%d')
                        end_date_formatted = valid_dates.max().strftime('%Y%m%d')

                # 保存到CSV
                filename = os.path.join(stock_data_root, output_dir,
                                        f"{stock_code}_{stock_name}_{start_date_formatted}_{end_date_formatted}.csv")

                save_to_csv(result_df.round(2), filename)  # 整个df保留2位小数
            except Exception as e:
                logger.error(f"保存CSV文件时发生错误: {e}")

            logger.info(f"成功获取{stock_name}({stock_code})历史数据，共 {len(result_df)} 条记录")
            if not result_df.empty and 'date' in result_df.columns:
                valid_dates = result_df['date'].dropna()
                if not valid_dates.empty:
                    logger.info(f"数据时间范围: {valid_dates.min()} 至 {valid_dates.max()}")

            return result_df
        except Exception as e:
            logger.error(f"获取K线数据时发生异常: {e}")
            return pd.DataFrame()

    def close_connection(self):
        """
        关闭与 futuopend 服务的连接
        """
        try:
            self.quote_ctx.close()
        except Exception as e:
            logger.error(f"关闭连接时发生错误: {e}")

    def get_user_selected_stock_list(self, group_name):
        try:
            ret, data = self.quote_ctx.get_user_security(group_name)  # 假设性函数调用
            if ret == RET_OK:
                print(data)
                if data.shape[0] > 0:  # 如果自选股列表不为空
                    print(data['code'][0])  # 取第一条的股票代码
                    return data['code'].values.tolist()
                else:
                    return []
            else:
                print('error:', data)
                return []
        except Exception as e:
            logger.error(f"获取自选股列表时发生错误: {e}")
            return []


def get_user_selected_stock_list(group_name="港股"):
    fetcher = TestIndicatorFetcher()
    try:
        stock_list = fetcher.get_user_selected_stock_list(group_name)
        return stock_list
    except Exception as e:
        logger.error(f"获取自选股列表时发生错误: {e}")
        return []
    finally:
        fetcher.close_connection()


def indicator_fetcher(stock_code='HK.00700'):
    """
    根据股票代码，查询标记了目标买入或卖出信号的数据
    :param stock_code: 股票代码，例如 'HK.00700'
    :param back_time: 回溯时间，默认为365天（从当前时间向前追溯，最多追溯365天）
    :return: 标记了目标买入或卖出信号的数据
    """
    fetcher = TestIndicatorFetcher()
    try:
        # 获取K线数据
        df = fetcher.get_history_kline(stock_code)

        if not df.empty:
            logger.info(f"成功获取{stock_code}历史数据，共 {len(df)} 条记录")
            if 'date' in df.columns:
                valid_dates = df['date'].dropna()
                if not valid_dates.empty:
                    logger.info(f"数据时间范围: {valid_dates.min()} 至 {valid_dates.max()}")
        return df
    except Exception as e:
        logger.error(f"获取指标数据时发生错误: {e}")
        return pd.DataFrame()
    finally:
        fetcher.close_connection()


def get_single_hk_stock_history(stock_code, start_date, end_date, adjust_type=ft.AuType.QFQ, output_dir='futu'):
    fetcher = TestIndicatorFetcher()
    try:
        df = fetcher.get_history_kline(stock_code, start=start_date, end=end_date,
                                       autype=adjust_type, output_dir=output_dir)

        if not df.empty:
            logger.info("数据预览：")
            logger.info(df.head())
            return True
        else:
            logger.warning(f"未能获取股票 {stock_code} 的数据")
            return False
    except Exception as e:
        logger.error(f"获取股票 {stock_code} 数据时发生错误: {e}")
        return False
    finally:
        fetcher.close_connection()

def get_single_cn_stock_history(stock_code, start_date, end_date, adjust_type=ft.AuType.QFQ, output_dir='futu'):
    return get_single_hk_stock_history(stock_code, start_date, end_date, adjust_type, output_dir)


if __name__ == "__main__":

    # get_single_hk_stock_history(
    #     stock_code="HK.00700",
    #     start_date="2021-01-01",
    #     end_date="2025-10-17",
    #     adjust_type=ft.AuType.QFQ
    # )

    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_time = (datetime.datetime.now() - datetime.timedelta(days=365*4)).strftime("%Y-%m-%d")

    stock_list = get_user_selected_stock_list()
    for stock_code in stock_list:
        get_single_hk_stock_history(
            stock_code=stock_code,
            start_date=start_time,
            end_date=end_date,
            adjust_type=ft.AuType.QFQ
        )

    get_single_cn_stock_history(
        stock_code="SH.510210",
        start_date=start_time,
        end_date=end_date,
        adjust_type=ft.AuType.QFQ
    )
