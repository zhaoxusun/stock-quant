# 废弃，直接集成到frontend_app中，前端直接调用API获取信号数据
# import os
# import pandas as pd
# from pathlib import Path
# import settings
# import sys
# from datetime import datetime
#
#
# class SignalsAnalyzer:
#     def __init__(self):
#         self.signals_root = settings.signals_root
#         self.all_signals_df = None
#
#     def load_all_signals(self):
#         """加载所有信号CSV文件并合并到一个DataFrame"""
#         # 检查signals路径是否存在
#         if not self.signals_root.exists():
#             print(f"提示：signals路径 '{self.signals_root}' 不存在，无法加载信号数据。")
#             return False
#
#         all_data = []
#         signal_files_found = False
#
#         # 遍历signals路径下的所有CSV文件
#         print(f"正在遍历signals路径下的所有CSV文件...")
#         for root, dirs, files in os.walk(self.signals_root):
#             for file in files:
#                 if file.endswith('.csv') and file.startswith('stock_signals_'):
#                     signal_files_found = True
#                     file_path = os.path.join(root, file)
#
#                     try:
#                         # 提取文件路径中的元信息
#                         relative_path = os.path.relpath(file_path, self.signals_root)
#                         path_parts = relative_path.split(os.sep)
#
#                         # 解析数据源、股票代码和策略名称
#                         data_source = path_parts[0] if len(path_parts) > 0 else 'unknown'
#                         stock_info = path_parts[1].split('_') if len(path_parts) > 1 else ['unknown']
#                         stock_code = stock_info[0] if stock_info else 'unknown'
#                         stock_name = stock_info[1] if len(stock_info) > 1 else 'unknown'
#                         strategy_name = path_parts[2] if len(path_parts) > 2 else 'unknown'
#
#                         # 读取CSV文件
#                         df = pd.read_csv(file_path)
#
#                         # 添加元信息列
#                         df['data_source'] = data_source
#                         df['stock_code'] = stock_code
#                         df['stock_name'] = stock_name
#                         df['strategy_name'] = strategy_name
#                         df['file_path'] = file_path
#
#                         all_data.append(df)
#                         print(f"加载文件: {file_path}")
#                     except Exception as e:
#                         print(f"加载文件失败: {file_path}, 错误: {str(e)}")
#
#         if not signal_files_found:
#             print(f"提示：在 '{self.signals_root}' 路径下未找到信号CSV文件。")
#             return False
#
#         # 合并所有数据
#         self.all_signals_df = pd.concat(all_data, ignore_index=True)
#
#         # 转换date列为datetime类型并按时间倒序排列
#         if 'date' in self.all_signals_df.columns:
#             self.all_signals_df['date'] = pd.to_datetime(self.all_signals_df['date'])
#             self.all_signals_df = self.all_signals_df.sort_values('date', ascending=False)
#
#         print(f"信号数据加载完成，共加载 {len(self.all_signals_df)} 条记录。")
#         return True
#
#     def filter_signals(self, strategy_name=None, stock_code=None, signal_type=None):
#         """
#         根据策略名称、股票代码和信号类型筛选数据
#         :param strategy_name: 策略名称
#         :param stock_code: 股票代码
#         :param signal_type: 信号类型 (如 normal_buy, normal_sell, strong_buy, strong_sell)
#         :return: 筛选后的DataFrame
#         """
#         if self.all_signals_df is None:
#             print("请先调用load_all_signals方法加载数据。")
#             return None
#
#         filtered_df = self.all_signals_df.copy()
#
#         # 应用筛选条件
#         if strategy_name:
#             filtered_df = filtered_df[filtered_df['strategy_name'] == strategy_name]
#
#         if stock_code:
#             filtered_df = filtered_df[filtered_df['stock_code'] == stock_code]
#
#         if signal_type:
#             filtered_df = filtered_df[filtered_df['signal_type'] == signal_type]
#
#         return filtered_df
#
#     def generate_summary_statistics(self):
#         """生成信号统计摘要"""
#         if self.all_signals_df is None:
#             print("请先调用load_all_signals方法加载数据。")
#             return None
#
#         # 按策略名称统计
#         strategy_stats = self.all_signals_df.groupby('strategy_name').agg({
#             'signal_type': ['count', 'nunique'],
#             'stock_code': 'nunique'
#         }).reset_index()
#         strategy_stats.columns = ['策略名称', '总信号数', '信号类型数', '涉及股票数']
#
#         # 按股票代码统计
#         stock_stats = self.all_signals_df.groupby('stock_code').agg({
#             'signal_type': ['count', 'nunique'],
#             'strategy_name': 'nunique'
#         }).reset_index()
#         stock_stats.columns = ['股票代码', '总信号数', '信号类型数', '涉及策略数']
#
#         # 按信号类型统计
#         signal_type_stats = self.all_signals_df.groupby('signal_type').agg({
#             'date': ['count', 'min', 'max'],
#             'stock_code': 'nunique',
#             'strategy_name': 'nunique'
#         }).reset_index()
#         signal_type_stats.columns = ['信号类型', '信号数', '最早日期', '最晚日期', '涉及股票数', '涉及策略数']
#
#         return {
#             'strategy_stats': strategy_stats,
#             'stock_stats': stock_stats,
#             'signal_type_stats': signal_type_stats
#         }
#
#     def display_summary(self):
#         """显示信号统计摘要"""
#         stats = self.generate_summary_statistics()
#         if stats is None:
#             return
#
#         print("\n===== 信号统计摘要 =====")
#         print("\n1. 按策略名称统计:")
#         print(stats['strategy_stats'].to_string(index=False))
#
#         print("\n2. 按股票代码统计:")
#         print(stats['stock_stats'].to_string(index=False))
#
#         print("\n3. 按信号类型统计:")
#         print(stats['signal_type_stats'].to_string(index=False))
#
#     def export_filtered_signals(self, filtered_df, output_file=None):
#         """导出筛选后的信号数据到CSV文件"""
#         if filtered_df is None or filtered_df.empty:
#             print("没有数据可导出。")
#             return False
#
#         if output_file is None:
#             # 生成默认文件名
#             current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
#             output_file = f"filtered_signals_{current_time}.csv"
#
#         try:
#             filtered_df.to_csv(output_file, index=False, encoding='utf-8-sig')
#             print(f"筛选后的信号数据已导出到: {output_file}")
#             return True
#         except Exception as e:
#             print(f"导出数据失败: {str(e)}")
#             return False
#
#
# def main():
#     """主函数，提供命令行交互"""
#     analyzer = SignalsAnalyzer()
#
#     # 加载所有信号数据
#     if not analyzer.load_all_signals():
#         sys.exit(1)
#
#     # 显示统计摘要
#     analyzer.display_summary()
#
#     # 提供筛选选项
#     print("\n===== 信号筛选功能 ======")
#     print("可用的策略名称:", analyzer.all_signals_df['strategy_name'].unique().tolist())
#     print("可用的股票代码:", analyzer.all_signals_df['stock_code'].unique().tolist())
#     print("可用的信号类型:", analyzer.all_signals_df['signal_type'].unique().tolist())
#
#     # 获取用户输入的筛选条件
#     strategy_name = input("请输入要筛选的策略名称 (留空表示不筛选): ").strip() or None
#     stock_code = input("请输入要筛选的股票代码 (留空表示不筛选): ").strip() or None
#     signal_type = input("请输入要筛选的信号类型 (留空表示不筛选): ").strip() or None
#
#     # 执行筛选
#     filtered_df = analyzer.filter_signals(strategy_name, stock_code, signal_type)
#
#     # 显示筛选结果
#     if filtered_df is not None and not filtered_df.empty:
#         print(f"\n筛选结果: 共 {len(filtered_df)} 条记录")
#         print("前10条记录:")
#         print(filtered_df.head(10).to_string(index=False))
#
#         # 询问是否导出
#         export = input("是否导出筛选结果? (y/n): ").strip().lower()
#         if export == 'y':
#             output_file = input("请输入输出文件名 (留空使用默认名称): ").strip() or None
#             analyzer.export_filtered_signals(filtered_df, output_file)
#     else:
#         print("没有找到符合条件的记录。")
#
#
# if __name__ == "__main__":
#     main()
