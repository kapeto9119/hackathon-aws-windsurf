import os
import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        """
        Initialize the EmailService
        """
        self.host = os.getenv("EMAIL_HOST")
        self.port = int(os.getenv("EMAIL_PORT", "587"))
        self.username = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.from_email = os.getenv("EMAIL_USER", "quote-agent@example.com")
    
    async def send_email(self, recipient: str, subject: str, body: str):
        """
        Send an email asynchronously
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = self.from_email
            message["To"] = recipient
            message["Subject"] = subject
            
            # Attach body
            message.attach(MIMEText(body, "plain"))
            
            # For demo purposes, just log the email instead of actually sending it
            logger.info(f"Would send email to {recipient} with subject: {subject}")
            logger.info(f"Email body: {body[:100]}...")
            
            # In a real implementation, uncomment this code to actually send the email
            """
            # Connect to SMTP server
            smtp = aiosmtplib.SMTP(hostname=self.host, port=self.port, use_tls=True)
            await smtp.connect()
            await smtp.login(self.username, self.password)
            
            # Send email
            await smtp.send_message(message)
            
            # Disconnect
            await smtp.quit()
            """
            
            return True
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
