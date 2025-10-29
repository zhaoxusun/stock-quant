import datetime
import os

import baostock as bs
import pandas as pd
from common.logger import create_log
from common.util_csv import save_to_csv
from core.stock.manager_common import standardize_stock_data
from settings import stock_data_root

logger = create_log('manage_akshare')

def init_baostock():
    """初始化Baostock连接"""
    lg = bs.login()
    if lg.error_code != '0':
        logger.info(f"登录失败: {lg.error_msg}")
        return False
    logger.info("登录成功")
    return True


def get_stock_name(stock_code):
    """
    获取股票完整基本信息（名称、行业、地区等）

    返回:
    DataFrame: 包含股票基本信息的DataFrame
    """
    rs = bs.query_stock_basic(code=stock_code)
    if rs.error_code != '0':
        logger.info(f"获取基本信息失败：{rs.error_msg}")
        return None

    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())
    return data_list[0][1]



def get_stock_history(stock_code, start_date, end_date, adjust_type='2'):
    """
    获取股票历史日线数据（修复列数不匹配问题）-前复权
    """
    # 1. 定义需要获取的字段（注意：字段数量需与后续columns列表一一对应）
    fields = "date,code,open,high,low,close,volume"  # 共7个字段
    # 2. 调用接口
    rs = bs.query_history_k_data_plus(
        stock_code,
        fields,  # 使用上面定义的字段
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag=adjust_type
    )

    if rs.error_code != '0':
        logger.info(f"获取数据失败: {rs.error_msg}")
        return None

    # 3. 提取数据
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())  # 每行数据的列数由fields决定

    # 4. 定义列名（关键：列名数量必须与fields字段数量完全一致）
    columns = ["date", "code", "open", "high", "low", "close", "volume"]  # 共7个列名，与fields对应

    # 5. 验证列数是否匹配（新增校验，提前发现问题）
    if data_list and len(data_list[0]) != len(columns):
        raise ValueError(f"列数不匹配：定义了{len(columns)}个列名，但数据每行有{len(data_list[0])}个字段")

    # 6. 创建DataFrame
    df = pd.DataFrame(data_list, columns=columns)

    # 转换数据类型
    numeric_columns = ["open", "high", "low", "close", "volume"]
    df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
    df['date'] = pd.to_datetime(df['date'])

    if not df.empty:
        # 尝试获取股票名称
        try:
            stock_name = get_stock_name(stock_code)
            stock_name = f"A股{stock_name}"
        except:
            stock_name = stock_code

        # 标准化数据格式
        df = standardize_stock_data(df, stock_code, stock_name, 'CN')

        logger.info(f"成功获取{stock_name}历史数据，共 {len(df)} 条记录")
        logger.info(f"数据时间范围: {df['date'].min()} 至 {df['date'].max()}")

        return df
    else:
        logger.warning(f"无法获取{stock_code}历史数据")
        return pd.DataFrame()


def get_single_cn_stock_history(stock_code, start_date, end_date, adjust_type = '2', output_dir='baostock'):
    """
    获取单只港股的历史数据并保存到CSV

    参数:
    stock_code: 股票代码（如 '00700'）
    output_dir: 输出目录

    返回:
    bool: 是否成功获取并保存数据
    """
    try:
        if not init_baostock():
            return False

        # 获取历史数据
        df = get_stock_history(stock_code, start_date, end_date, adjust_type)

        if not df.empty:
            if df is not None:
                logger.info("数据预览：")
                logger.info(df.head())
            # 获取股票名称
            stock_name = df['stock_name'].iloc[0]

            # 获取日期范围并格式化
            start_date_formatted = df['date'].min().strftime('%Y%m%d')
            end_date_formatted = df['date'].max().strftime('%Y%m%d')
            # 保存到CSV
            filename = os.path.join(stock_data_root, output_dir,
                                    f"{stock_code}_{stock_name}_{start_date_formatted}_{end_date_formatted}.csv")
            save_to_csv(df.round(2), filename) # 整个df保留2位小数
            return True
        else:
            logger.warning(f"未能获取A股 {stock_code} 的数据")
            return False
    finally:
        bs.logout()
        logger.info("已退出连接")



if __name__ == "__main__":
    end_date = datetime.datetime.now().strftime("%Y-%m-%d")
    start_time = (datetime.datetime.now() - datetime.timedelta(days=365 * 4)).strftime("%Y-%m-%d")

    get_single_cn_stock_history(
        stock_code="sh.600519",
        start_date=start_time,
        end_date=end_date,
        adjust_type='2'
    )
