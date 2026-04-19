import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, smtp_server, smtp_port, sender_email, sender_password):
        """
        初始化邮件发送器
        
        Args:
            smtp_server: SMTP服务器地址
            smtp_port: SMTP服务器端口
            sender_email: 发件人邮箱
            sender_password: 发件人密码
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
    
    async def send_email(self, receiver_email, subject, body):
        """
        发送邮件
        
        Args:
            receiver_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件正文
            
        Returns:
            bool: 是否发送成功
        """
        try:
            # 创建邮件
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = receiver_email
            message["Subject"] = subject
            
            # 添加邮件正文
            message.attach(MIMEText(body, "plain", "utf-8"))
            
            # 连接SMTP服务器并发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()  # 启用TLS加密
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"邮件发送成功: {receiver_email}")
            return True
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False

# 全局邮件发送器实例
email_sender = None

def init_email_sender(smtp_server, smtp_port, sender_email, sender_password):
    """
    初始化邮件发送器
    
    Args:
        smtp_server: SMTP服务器地址
        smtp_port: SMTP服务器端口
        sender_email: 发件人邮箱
        sender_password: 发件人密码
    """
    global email_sender
    email_sender = EmailSender(smtp_server, smtp_port, sender_email, sender_password)
    logger.info("邮件发送器初始化完成")

def get_email_sender():
    """
    获取邮件发送器实例
    
    Returns:
        EmailSender: 邮件发送器实例
    """
    global email_sender
    return email_sender
