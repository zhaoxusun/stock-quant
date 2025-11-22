import os
import time
import json
import requests
from common.logger import create_log

logger = create_log('wechat_notifier')


class WechatNotifier:
    """企业微信webhook消息通知服务类（从环境变量读取配置）"""

    def __init__(self):
        # 从环境变量读取企业微信webhook配置
        self.webhook_url = os.environ.get('WECHAT_WEBHOOK_QUANT', '')
        self.timeout = 10

    def send_text_message(self, content, mentioned_list=None, mentioned_mobile_list=None):
        """
        发送文本消息
        :param content: 消息内容
        :param mentioned_list: @的用户列表，如 ["@all"]
        :param mentioned_mobile_list: @的手机号列表，如 ["@all"]
        :return: 是否发送成功
        """
        if not self.webhook_url:
            logger.error("企业微信webhook URL未在环境变量WECHAT_WEBHOOK_QUANT中配置")
            return False

        mentioned_list = mentioned_list or []
        mentioned_mobile_list = mentioned_mobile_list or []

        data = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_list": mentioned_list,
                "mentioned_mobile_list": mentioned_mobile_list
            }
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=self.timeout
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("发送文本消息成功")
                return True
            else:
                logger.error(f"发送文本消息失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            logger.error(f"发送文本消息异常: {str(e)}")
            return False

    def send_markdown_message(self, content):
        """
        发送Markdown消息
        :param content: Markdown格式的消息内容
        :return: 是否发送成功
        """
        if not self.webhook_url:
            logger.error("企业微信webhook URL未在环境变量WECHAT_WEBHOOK_QUANT中配置")
            return False

        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=self.timeout
            )
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("发送Markdown消息成功")
                return True
            else:
                logger.error(f"发送Markdown消息失败: {result.get('errmsg')}")
                return False
        except Exception as e:
            logger.error(f"发送Markdown消息异常: {str(e)}")
            return False

    def send_file_message(self, file_path):
        """
        发送文件消息
        :param file_path: 文件路径
        :return: 是否发送成功
        """
        if not self.webhook_url:
            logger.error("企业微信webhook URL未在环境变量WECHAT_WEBHOOK_QUANT中配置")
            return False

        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False

        try:
            # 第一步：获取webhook key并构建上传URL
            if 'key=' not in self.webhook_url:
                logger.error("webhook URL格式不正确，缺少key参数")
                return False

            key = self.webhook_url.split('key=')[1].split('&')[0]
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file"

            # 上传文件
            files = {'media': open(file_path, 'rb')}
            response = requests.post(
                upload_url,
                files=files,
                timeout=self.timeout
            )
            upload_result = response.json()

            if upload_result.get('errcode') != 0:
                logger.error(f"上传文件失败: {upload_result.get('errmsg')}")
                return False

            media_id = upload_result.get('media_id')

            # 第二步：发送文件消息
            send_data = {
                "msgtype": "file",
                "file": {
                    "media_id": media_id
                }
            }

            send_response = requests.post(
                self.webhook_url,
                json=send_data,
                timeout=self.timeout
            )
            send_result = send_response.json()

            if send_result.get('errcode') == 0:
                logger.info("发送文件消息成功")
                return True
            else:
                logger.error(f"发送文件消息失败: {send_result.get('errmsg')}")
                return False

        except Exception as e:
            logger.error(f"发送文件消息异常: {str(e)}")
            return False

    def send_html_report(self, html_file_path, title="回测报告", description=""):
        """
        发送HTML报告
        :param html_file_path: HTML文件路径
        :param title: 报告标题
        :param description: 报告描述
        :return: 是否发送成功
        """
        if not self.webhook_url:
            logger.error("企业微信webhook URL未在环境变量WECHAT_WEBHOOK_QUANT中配置")
            return False
        # 先发送一个Markdown格式的说明消息
        markdown_content = f"""# {title}

        ## 描述
        {description}
        
        ## 时间
        {time.strftime('%Y-%m-%d %H:%M:%S')}
        
        HTML报告已作为附件发送，请查收。"""

        self.send_markdown_message(markdown_content)

        # 然后发送HTML文件作为附件
        return self.send_file_message(html_file_path)


# 创建全局通知器实例
wechat_notifier = WechatNotifier()


# 便捷函数
def send_wechat_message(content, mentioned_list=None, mentioned_mobile_list=None):
    """发送微信文本消息的便捷函数"""
    return wechat_notifier.send_text_message(content, mentioned_list, mentioned_mobile_list)


def send_wechat_report(html_file_path, title="回测报告", description=""):
    """发送微信HTML报告的便捷函数"""
    return wechat_notifier.send_html_report(html_file_path, title, description)


# if __name__ == '__main__':
#
#     # 导入微信通知模块
#     from core.notification.wechat_notifier import send_wechat_message, send_wechat_report
#
#     # 发送文本消息
#     send_wechat_message("回测任务已完成！", mentioned_mobile_list=["@all"])
#
#     # 发送带HTML附件的报告
#     html_report_path = "/Users/romanzhao/PycharmProjects/stock-quant/html/akshare/00700_港股00700_20211101_20251028/EnhancedVolumeStrategy/stock_with_trades_20251107_141540.html"
#     send_wechat_report(
#         html_file_path=html_report_path,
#         title="股票回测周报",
#         description="本周共完成10只股票的回测，平均收益率8.5%"
#     )