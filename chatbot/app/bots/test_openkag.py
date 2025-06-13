import logging
import requests
from dingtalk_stream import AckMessage
import dingtalk_stream
import argparse
import pathlib
from app.core.config import LOG_DIR

def define_options():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--client_id', dest='client_id', required=True,
        help='app_key or suite_key from https://open-dev.digntalk.com'
    )
    parser.add_argument(
        '--client_secret', dest='client_secret', required=True,
        help='app_secret or suite_secret from https://open-dev.digntalk.com'
    )
    parser.add_argument(
        '--url', dest='url', default='http://localhost:9222/v1/chatbot/chat',
    )
    options = parser.parse_args()
    return options

def setup_logger(client_id=None):
    logger = logging.getLogger()
    
    # 移除现有的处理器，避免重复添加
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 添加流处理器(控制台输出)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
    logger.addHandler(stream_handler)
    
    # 如果指定了client_id，添加文件处理器
    if client_id:
        bot_log_dir = LOG_DIR / client_id
        if not bot_log_dir.exists():
            bot_log_dir.mkdir(parents=True, exist_ok=True)
            
        file_handler = logging.FileHandler(bot_log_dir / "bot.log")
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]'))
        logger.addHandler(file_handler)
    
    logger.setLevel(logging.INFO)
    return logger
  
class OpenKagHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self,
                 client_id: str,
                 client_secret: str,
                 url: str,
                 logger: logging.Logger = None):
        super(dingtalk_stream.ChatbotHandler, self).__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = url
        self.logger = logger or logging.getLogger(__name__)
            
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        text = incoming_message.text.content.strip()
        
        self.logger.info(f"收到消息: {text} 来自: {incoming_message.sender_nick} ({incoming_message.sender_staff_id})")
        
        # 确定聊天类型
        chat_type = 'private' if incoming_message.conversation_type == '1' else 'group'
        message_from_id = incoming_message.sender_staff_id

        # 请求体
        data = {
            "question": text,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "message_from_id": message_from_id,
            "chat_type": chat_type
        }

        try:
            # 发送请求
            self.logger.info(f"向API发送请求: {self.url}")
            response = requests.post(
                self.url,
                json=data
            )
            
            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                # 返回data中的answer
                answer = result['data']['answer']
                self.logger.info(f"得到回复: {answer[:100]}..." if len(answer) > 100 else f"得到回复: {answer}")
                # 将API返回的结果发送回钉钉
                self.reply_text(answer, incoming_message)
            else:
                error_message = f"请求失败，状态码: {response.status_code}\n错误信息: {response.text}"
                self.logger.error(error_message)
                self.reply_text(error_message, incoming_message)

        except Exception as e:
            error_message = f"发生错误: {str(e)}"
            self.logger.error(error_message, exc_info=True)
            self.reply_text(error_message, incoming_message)
            
        return AckMessage.STATUS_OK, 'OK'

def main():
    options = define_options()
    logger = setup_logger(options.client_id)
    
    logger.info(f"启动机器人，client_id: {options.client_id}")

    credential = dingtalk_stream.Credential(options.client_id, options.client_secret)
    client = dingtalk_stream.DingTalkStreamClient(credential)
    
    handler = OpenKagHandler(
        client_id=options.client_id,
        client_secret=options.client_secret,
        url=options.url,
        logger=logger
    )
    
    logger.info("注册回调处理器")
    client.register_callback_handler(
        dingtalk_stream.chatbot.ChatbotMessage.TOPIC,
        handler
    )
    
    logger.info("开始监听消息")
    client.start_forever()


if __name__ == '__main__':
    main() 