import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime

def send_email(sender_email: str, sender_password: str, recipient_email: str, subject: str, body: str, attachment_path: str = None) -> bool:
    """
    Send an email using Gmail SMTP server.
    
    Args:
        sender_email: Gmail address of the sender
        sender_password: App password for Gmail account (not regular password)
        recipient_email: Email address of the recipient
        subject: Subject line of the email
        body: Body text of the email
        attachment_path: Optional path to file to attach to email
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = subject

        # Add body to email
        message.attach(MIMEText(body, "plain"))

        # Add attachment if provided
        if attachment_path:
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                
                filename = os.path.basename(attachment_path)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}",
                )
                message.attach(part)

        # Create SMTP session
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            
            # Send email
            server.send_message(message)
            
        return True

    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False
