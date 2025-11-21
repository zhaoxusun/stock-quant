import datetime
import os

from common.logger import create_log
from common.util_csv import read_data, combine_data
from settings import signals_root
logger = create_log('signal_handler')

def signal_get():
    """获取所有信号文件信息"""
    try:
        if not os.path.exists(signals_root):
            raise Exception('信号目录不存在')

        signal_files = []
        # 遍历信号目录
        for root, dirs, files in os.walk(signals_root):
            for file in files:
                if file.endswith('.csv') and file.startswith('stock_signals_'):
                    file_path = os.path.join(root, file)
                    # 从路径中提取元数据
                    relative_path = os.path.relpath(file_path, signals_root)
                    parts = relative_path.split(os.sep)

                    # 解析路径信息
                    data_source = parts[0] if len(parts) > 0 else 'unknown'
                    stock_info = parts[1] if len(parts) > 1 else 'unknown'
                    strategy_name = parts[2] if len(parts) > 2 else 'unknown'

                    # 获取文件创建时间
                    file_time = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')

                    signal_files.append({
                        'file_path': relative_path,
                        'data_source': data_source,
                        'stock_info': stock_info,
                        'strategy_name': strategy_name,
                        'file_time': file_time
                    })

        # 按文件创建时间倒序排序
        signal_files.sort(key=lambda x: x['file_time'], reverse=True)
        return signal_files

    except Exception as e:
        logger.error(f"获取信号文件失败: {str(e)}")
        raise e



def signals_analyze(file_paths, filters):
    """分析信号文件"""
    try:
        all_signals = []

        for file_path in file_paths:
            full_path = os.path.join(signals_root, file_path)

            if not os.path.exists(full_path):
                continue

            # 读取CSV文件
            df = read_data(full_path)

            # 从文件路径中提取元数据
            parts = file_path.split(os.sep)
            data_source = parts[0] if len(parts) > 0 else 'unknown'
            stock_info = parts[1] if len(parts) > 1 else 'unknown'
            strategy_name = parts[2] if len(parts) > 2 else 'unknown'

            # 添加元数据到DataFrame
            df['data_source'] = data_source
            df['stock_info'] = stock_info
            df['strategy_name'] = strategy_name
            df['file_path'] = file_path

            all_signals.append(df)

        if not all_signals:
            raise Exception('没有找到有效的信号文件')

        # 合并所有信号数据
        combined_df = combine_data(all_signals, True)

        # 应用筛选条件
        if filters:
            if 'strategy_name' in filters and filters['strategy_name']:
                combined_df = combined_df[combined_df['strategy_name'] == filters['strategy_name']]

            if 'stock_code' in filters and filters['stock_code']:
                combined_df = combined_df[combined_df['stock_info'].str.contains(filters['stock_code'])]

            if 'signal_type' in filters and filters['signal_type']:
                combined_df = combined_df[combined_df['signal_type'] == filters['signal_type']]

            # 添加时间范围筛选
            if 'start_date' in filters and filters['start_date']:
                combined_df = combined_df[combined_df['date'] >= filters['start_date']]

            if 'end_date' in filters and filters['end_date']:
                combined_df = combined_df[combined_df['date'] <= filters['end_date']]

        # 按时间倒序排序
        combined_df = combined_df.sort_values(by='date', ascending=False)
        return combined_df
    except Exception as e:
        logger.error(f"分析信号失败: {str(e)}")
        raise Exception(f"分析信号失败: {str(e)}")
