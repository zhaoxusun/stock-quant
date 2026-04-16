from common.logger import create_log
import datetime
from weasyprint import HTML
from weasyprint.css import CSS
import os
from bs4 import BeautifulSoup

logger = create_log("util_html")


def signals_to_html(signals_data, filters=None, summary=None):
    """将信号数据转换为HTML报告

    参数:
        signals_data: 信号数据列表，每个元素是包含信号信息的字典
        filters: 筛选条件字典
        summary: 统计信息字典

    返回:
        HTML格式的报告字符串
    """
    try:
        # 设置默认筛选条件和统计信息
        if filters is None:
            filters = {}
        if summary is None:
            summary = {}
        
        # 如果 summary 为空或没有统计数据，从 signals_data 计算
        if not summary.get('total_signals'):
            summary = {
                'total_signals': len(signals_data),
                'buy_signals': len([s for s in signals_data if s.get('signal_type') and 'buy' in s.get('signal_type')]),
                'sell_signals': len([s for s in signals_data if s.get('signal_type') and 'sell' in s.get('signal_type')]),
                'neutral_signals': len([s for s in signals_data if s.get('signal_type') and 'neutral' in s.get('signal_type')]),
                'unique_stocks': len(set([s.get('stock_info', '') for s in signals_data])),
                'unique_strategies': len(set([s.get('strategy_name', '') for s in signals_data])),
                'date_range': '',
                'signal_type_counts': {}
            }

        # 获取筛选条件
        strategy_filter = filters.get('strategy_name', '')
        stock_filter = filters.get('stock_code', '')
        signal_type_filter = filters.get('signal_type', '')
        start_date = filters.get('start_date', '')
        end_date = filters.get('end_date', '')

        # 获取统计信息
        total_signals = summary.get('total_signals', 0)
        buy_signals = summary.get('buy_signals', 0)
        sell_signals = summary.get('sell_signals', 0)
        neutral_signals = summary.get('neutral_signals', 0)
        unique_stocks = summary.get('unique_stocks', 0)
        unique_strategies = summary.get('unique_strategies', 0)
        date_range = summary.get('date_range', '')
        signal_type_counts = summary.get('signal_type_counts', {})
        
        # 如果没有 signal_type_counts，从 signals_data 计算
        if not signal_type_counts and signals_data:
            signal_type_counts = {}
            dates = []
            for s in signals_data:
                st = s.get('signal_type', '')
                if st:
                    signal_type_counts[st] = signal_type_counts.get(st, 0) + 1
                d = s.get('date', '')
                if d:
                    dates.append(d)
            if dates:
                dates.sort()
                date_range = f"{dates[0]} 至 {dates[-1]}"
        
        # 生成信号类型分布HTML
        distribution_html = ''
        if signal_type_counts:
            type_names = {
                'normal_buy': '普通买入',
                'strong_buy': '强势买入',
                'buy': '买入',
                'normal_sell': '普通卖出',
                'strong_sell': '强势卖出',
                'sell': '卖出',
                'neutral': '中性',
                'hold': '持有'
            }
            type_colors = {
                'normal_buy': '#2ecc71',
                'strong_buy': '#27ae60',
                'buy': '#2ecc71',
                'normal_sell': '#e74c3c',
                'strong_sell': '#c0392b',
                'sell': '#e74c3c',
                'neutral': '#f39c12',
                'hold': '#95a5a6'
            }
            for signal_type, count in sorted(signal_type_counts.items(), key=lambda x: x[1], reverse=True):
                name = type_names.get(signal_type, signal_type)
                color = type_colors.get(signal_type, '#3498db')
                percentage = (count / total_signals * 100) if total_signals > 0 else 0
                distribution_html += f'''
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <div style="min-width: 80px; color: #ccc;">{name}</div>
                    <div style="flex: 1; height: 8px; background: #555; border-radius: 4px; margin: 0 10px; overflow: hidden;">
                        <div style="width: {percentage:.1f}%; height: 100%; background: {color}; border-radius: 4px;"></div>
                    </div>
                    <div style="min-width: 100px; color: #999;">{count} 条 ({percentage:.1f}%)</div>
                </div>'''
        
        # 生成信号类型分布图表的HTML
        distribution_section = f'''
        <div style="background: #3a3a3a; padding: 15px; border-radius: 8px; margin-top: 15px;">
            <h4 style="color: #fff; margin-bottom: 15px;">📊 信号类型分布</h4>
            {distribution_html}
        </div>''' if distribution_html else ''

        # 生成信号表格行
        table_rows = []
        for signal in signals_data:
            signal_type_class = ''
            if signal.get('signal_type') and 'buy' in signal.get('signal_type'):
                signal_type_class = 'price-up'
            elif signal.get('signal_type') and 'sell' in signal.get('signal_type'):
                signal_type_class = 'price-down'

            table_row = f"                <tr>\n"
            table_row += f"                    <td>{signal.get('date', '-')}</td>\n"
            table_row += f"                    <td class='{signal_type_class}'>{signal.get('signal_type', '-')}</td>\n"
            table_row += f"                    <td>{signal.get('description', '-')}</td>\n"
            table_row += f"                    <td>{signal.get('stock_info', '-')}</td>\n"
            table_row += f"                    <td>{signal.get('data_source', '-')}</td>\n"
            table_row += f"                    <td>{signal.get('strategy_name', '-')}</td>\n"
            table_row += f"                </tr>"
            table_rows.append(table_row)

        # 创建HTML内容
        html_content = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>信号分析报告 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body {{ background-color: #2a2a2a; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .stats-container {{ display: flex; justify-content: space-around; margin-bottom: 30px; flex-wrap: wrap; }}
        .stat-box {{
            text-align: center;
            padding: 15px;
            background: #3a3a3a;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            margin: 10px;
            flex: 1;
            min-width: 200px;
            color: #e0e0e0;
        }}
        .stat-value {{ font-size: 1.8rem; font-weight: bold; margin: 5px 0; }}
        .price-up {{ color: #ff6b6b; }}
        .price-down {{ color: #4ecdc4; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #3a3a3a;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            color: #e0e0e0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #555;
        }}
        th {{
            background-color: #4a4a4a;
            color: #fff;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #404040;
        }}
        .filters {{
            background: #3a3a3a;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            color: #e0e0e0;
        }}
        .timestamp {{ text-align: right; color: #999; margin-top: 10px; font-size: 0.9rem; }}
        h1, h2, h3 {{ color: #fff; }}
        strong {{ color: #ccc; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>信号分析报告</h1>
            <p>此报告包含根据筛选条件分析的信号数据</p>
        </div>

        <div class="filters">
            <h3>筛选条件</h3>
            <div class="row">
                <div class="col-md-4">
                    <strong>策略：</strong>{strategy_filter or '全部策略'}
                </div>
                <div class="col-md-4">
                    <strong>股票：</strong>{stock_filter or '全部股票'}
                </div>
                <div class="col-md-4">
                    <strong>信号类型：</strong>{signal_type_filter or '全部类型'}
                </div>
            </div>
            <div class="row mt-2">
                <div class="col-md-6">
                    <strong>起始时间：</strong>{start_date or '不限制'}
                </div>
                <div class="col-md-6">
                    <strong>结束时间：</strong>{end_date or '不限制'}
                </div>
            </div>
        </div>

        <div class="stats-container">
            <div class="stat-box">
                <div>总信号数</div>
                <div class="stat-value">{total_signals}</div>
            </div>
            <div class="stat-box">
                <div>买入信号</div>
                <div class="stat-value price-up">{buy_signals}</div>
            </div>
            <div class="stat-box">
                <div>卖出信号</div>
                <div class="stat-value price-down">{sell_signals}</div>
            </div>
            <div class="stat-box">
                <div>中性信号（暂未实现）</div>
                <div class="stat-value" style="color: #f39c12;">{neutral_signals}</div>
            </div>
            <div class="stat-box">
                <div>涉及股票（不聚合，每个文件代表一只股票）</div>
                <div class="stat-value">{unique_stocks}</div>
            </div>
            <div class="stat-box">
                <div>涉及策略数</div>
                <div class="stat-value" style="color: #9b59b6;">{unique_strategies}</div>
            </div>
        </div>
        
        <div style="background: #3a3a3a; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <strong style="color: #ccc;">📅 信号时间范围：</strong> <span style="color: #3498db;">{date_range or '全部时间'}</span>
        </div>
        {distribution_section}

        <h2>信号详情</h2>
        <table>
            <thead>
                <tr>
                    <th>日期</th>
                    <th>信号类型</th>
                    <th>描述</th>
                    <th>股票信息</th>
                    <th>数据源</th>
                    <th>策略</th>
                </tr>
            </thead>
            <tbody>
{chr(10).join(table_rows)}
            </tbody>
        </table>

        <div class="timestamp">
            报告生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
'''

        logger.info(f"成功生成HTML报告，包含{len(signals_data)}条信号")
        return html_content

    except Exception as e:
        logger.error(f"生成HTML报告失败: {str(e)}")
        raise



def save_clean_html(html_content, task_id):
    # 后续工作流中可以使用改方法，调用generate_html_report接口获取返回值的html_content值，在调用该方法生成html文件，拓展通知功能（html作为附件一起发送）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    output_path = os.path.join(project_root, f'{task_id}_fixed_signal_analysis.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"成功保存HTML报告到 {output_path}")
    return output_path



def html_to_pdf(html_content, output_pdf_path):
    """
    背景加宽适配表格！同步滚动无错位，视觉100%对齐
    :param html_content: 输入HTML内容字符串
    :param output_pdf_path: 输出PDF路径
    """
    try:
        # 核心调整：背景宽度≥表格最小宽度，同步滚动，精确控制边距
        fixed_css = CSS(string="""
            /* 1. 全局重置：确保无默认边距和填充 */
            * {
                margin: 0 !important;
                padding: 0 !important;
                box-sizing: border-box;
            }

            html, body {
                width: 100%;
                background-color: #2a2a2a;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                overflow-x: hidden;
            }

            /* 2. 背景容器：完全填充页面，无偏移 */
            .bg-wrapper {
                width: 100%;
                min-width: 600px;
                background-color: #2a2a2a;
                margin: 0 !important;
                padding: 0 !important;
            }

            /* 3. 内容容器：精确控制内边距，避免偏移 */
            .content-wrapper {
                width: 100%;
                padding: 15px !important;
                box-sizing: border-box;
                color: #e0e0e0;
                margin: 0 !important;
            }

            /* 4. 表格滚动容器：确保无额外边距 */
            .table-wrapper {
                width: 100%;
                overflow-x: auto;
                margin: 15px 0 !important;
                padding: 0 !important;
            }

            /* 5. 表格：精确控制宽度和边距 */
            table {
                min-width: 600px;
                width: 100%;  /* 改为100%以完全填充容器 */
                border-collapse: collapse;
                word-wrap: break-word;
                margin: 0 !important;
                padding: 0 !important;
            }

            /* 6. 列宽精确控制 */
            th:nth-child(1), td:nth-child(1) { width: 13%; }
            th:nth-child(2), td:nth-child(2) { width: 13%; }
            th:nth-child(3), td:nth-child(3) { width: 8%; }
            th:nth-child(4), td:nth-child(4) { width: 32%; }
            th:nth-child(5), td:nth-child(5) { width: 10%; }
            th:nth-child(6), td:nth-child(6) { width: 24%; }

            /* 其他样式调整 */
            h1, h2, h3 {
                text-align: center;
                margin: 18px 0 !important;
                color: #fff;
                font-size: 1.4rem;
            }

            .stats-container {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
                margin: 20px 0 !important;
                padding: 0 !important;
            }

            .stat-box {
                min-width: 45%;
                text-align: center;
                padding: 10px !important;
                background: #3a3a3a;
                border-radius: 8px;
                margin: 0 !important;
            }

            .stat-value {
                font-size: 1.5rem;
                font-weight: bold;
                color: #fff;
            }

            th, td {
                border: 1px solid #888;
                padding: 8px 6px !important;
                font-size: 13px;
                text-align: left;
                vertical-align: middle;
            }

            th {
                background-color: #4a4a4a;
                color: #fff;
            }

            /* 确保没有默认边距和缩进 */
            tbody, thead, tr {
                margin: 0 !important;
                padding: 0 !important;
            }
        """)

        # 重构结构：给所有内容套「加宽背景容器」
        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 创建新的body标签以确保干净的结构
        new_body = soup.new_tag('body')

        # 2. 创建加宽背景容器
        bg_wrapper = soup.new_tag('div', attrs={'class': 'bg-wrapper'})

        # 3. 创建内容容器
        content_wrapper = soup.new_tag('div', attrs={'class': 'content-wrapper'})
        bg_wrapper.append(content_wrapper)
        new_body.append(bg_wrapper)

        # 4. 把原内容全部移到内容容器中
        for child in list(soup.body.children):
            if child.name not in ['script', 'style']:  # 排除可能干扰的标签
                content_wrapper.append(child)

        # 5. 给表格套滚动容器
        for table in content_wrapper.find_all('table'):
            table_wrapper = soup.new_tag('div', attrs={'class': 'table-wrapper'})
            table.wrap(table_wrapper)

        # 6. 替换原body
        soup.body.replace_with(new_body)

        # 转换为字符串
        modified_html = str(soup)

        # 转换PDF：使用更精确的页面设置
        # 由于直接使用内容而非文件路径，base_url设置为当前目录
        html_obj = HTML(string=modified_html, base_url=os.getcwd())
        html_obj.write_pdf(
            output_pdf_path,
            stylesheets=[fixed_css],
            resolution=150,
            presentational_hints=True,
            # 关键：设置所有边距为0，并使用精确的页面大小
            options={
                'margin-top': '0mm',
                'margin-right': '0mm',
                'margin-bottom': '0mm',
                'margin-left': '0mm',
                'zoom': 1.0,  # 确保不缩放
                'page-size': 'A4'  # 指定页面大小
            }
        )
        print(f"✅ 转换成功！背景加宽对齐版PDF已保存到：{os.path.abspath(output_pdf_path)}")
        return True
    except Exception as e:
        print(f"❌ 转换失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 示例用法
    # sample_signals = [
    #     {
    #         'date': '2023-10-01',
    #         'signal_type': 'buy',
    #         'description': '买入信号',
    #         'stock_info': '腾讯控股(00700)',
    #         'data_source': 'futu',
    #         'strategy_name': 'EnhancedVolumeStrategy'
    #     },
    #     {
    #         'date': '2023-10-02',
    #         'signal_type': 'sell',
    #         'description': '卖出信号',
    #         'stock_info': '阿里巴巴(09988)',
    #         'data_source': 'futu',
    #         'strategy_name': 'SingleVolumeStrategy'
    #     }
    # ]
    #
    # html = signals_to_html(sample_signals)
    # print(html)
    #
    # content = "\n<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>信号分析报告 - 2025-11-12 12:47:43</title>\n    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css\">\n    <style>\n        body { background-color: #2a2a2a; }\n        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }\n        .header { text-align: center; margin-bottom: 30px; }\n        .stats-container { display: flex; justify-content: space-around; margin-bottom: 30px; flex-wrap: wrap; }\n        .stat-box {\n            text-align: center;\n            padding: 15px;\n            background: #3a3a3a;\n            border-radius: 8px;\n            box-shadow: 0 4px 8px rgba(0,0,0,0.3);\n            margin: 10px;\n            flex: 1;\n            min-width: 200px;\n            color: #e0e0e0;\n        }\n        .stat-value { font-size: 1.8rem; font-weight: bold; margin: 5px 0; }\n        .price-up { color: #ff6b6b; }\n        .price-down { color: #4ecdc4; }\n        table {\n            width: 100%;\n            border-collapse: collapse;\n            background: #3a3a3a;\n            border-radius: 8px;\n            overflow: hidden;\n            box-shadow: 0 4px 8px rgba(0,0,0,0.3);\n            color: #e0e0e0;\n        }\n        th, td {\n            padding: 12px;\n            text-align: left;\n            border-bottom: 1px solid #555;\n        }\n        th {\n            background-color: #4a4a4a;\n            color: #fff;\n            font-weight: 600;\n        }\n        tr:hover {\n            background-color: #404040;\n        }\n        .filters {\n            background: #3a3a3a;\n            padding: 20px;\n            border-radius: 8px;\n            margin-bottom: 20px;\n            box-shadow: 0 4px 8px rgba(0,0,0,0.3);\n            color: #e0e0e0;\n        }\n        .timestamp { text-align: right; color: #999; margin-top: 10px; font-size: 0.9rem; }\n        h1, h2, h3 { color: #fff; }\n        strong { color: #ccc; }\n    </style>\n</head>\n<body>\n    <div class=\"container\">\n        <div class=\"header\">\n            <h1>信号分析报告</h1>\n            <p>此报告包含根据筛选条件分析的信号数据</p>\n        </div>\n\n        <div class=\"filters\">\n            <h3>筛选条件</h3>\n            <div class=\"row\">\n                <div class=\"col-md-4\">\n                    <strong>策略：</strong>全部策略\n                </div>\n                <div class=\"col-md-4\">\n                    <strong>股票：</strong>全部股票\n                </div>\n                <div class=\"col-md-4\">\n                    <strong>信号类型：</strong>全部类型\n                </div>\n            </div>\n            <div class=\"row mt-2\">\n                <div class=\"col-md-6\">\n                    <strong>起始时间：</strong>2025-11-05\n                </div>\n                <div class=\"col-md-6\">\n                    <strong>结束时间：</strong>2025-11-12\n                </div>\n            </div>\n        </div>\n\n        <div class=\"stats-container\">\n            <div class=\"stat-box\">\n                <div>总信号数</div>\n                <div class=\"stat-value\">2</div>\n            </div>\n            <div class=\"stat-box\">\n                <div>买入信号</div>\n                <div class=\"stat-value price-up\">2</div>\n            </div>\n            <div class=\"stat-box\">\n                <div>卖出信号</div>\n                <div class=\"stat-value price-down\">0</div>\n            </div>\n            <div class=\"stat-box\">\n                <div>涉及股票数</div>\n                <div class=\"stat-value\">1</div>\n            </div>\n        </div>\n\n        <h2>信号详情</h2>\n        <table>\n            <thead>\n                <tr>\n                    <th>日期</th>\n                    <th>信号类型</th>\n                    <th>描述</th>\n                    <th>股票信息</th>\n                    <th>数据源</th>\n                    <th>策略</th>\n                </tr>\n            </thead>\n            <tbody>\n                <tr>\n                    <td>2025-11-05</td>\n                    <td class='price-up'>normal_buy</td>\n                    <td>-</td>\n                    <td>HK.09626_哔哩哔哩-W_20211108_20251105</td>\n                    <td>futu</td>\n                    <td>EnhancedVolumeStrategy</td>\n                </tr>\n                <tr>\n                    <td>2025-11-05</td>\n                    <td class='price-up'>normal_buy</td>\n                    <td>-</td>\n                    <td>HK.09626_哔哩哔哩-W_20211108_20251105</td>\n                    <td>futu</td>\n                    <td>SingleVolumeStrategy</td>\n                </tr>\n            </tbody>\n        </table>\n\n        <div class=\"timestamp\">\n            报告生成时间：2025-11-12 12:47:43\n        </div>\n    </div>\n</body>\n</html>\n"
    # save_clean_html(content,'test_task_id')
    # 示例：直接从文件读取HTML内容作为示例
    html_file_path = '/Users/romanzhao/PycharmProjects/stock-quant/task_20251121172103_fixed_signal_analysis.html'
    with open(html_file_path, 'r', encoding='utf-8') as f:
        sample_html_content = f.read()

    output_pdf = "signal_report_bg_wid1e.pdf"  # 背景加宽版PDF
    html_to_pdf(sample_html_content, output_pdf)





