"""TLS-only transactional SMTP delivery. Credentials and codes are never logged."""
from dataclasses import dataclass
from email.message import EmailMessage
import re
import smtplib
import ssl

from . import config


class DeliveryUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    security: str
    username: str
    password: str
    sender: str

    def validate(self):
        if (not self.host or not 1 <= self.port <= 65535 or self.security not in ('ssl', 'starttls')
                or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+', self.sender)
                or bool(self.username) != bool(self.password)):
            raise DeliveryUnavailable('Email delivery is not configured correctly.')


def settings():
    value = Settings(config.SMTP_HOST, config.SMTP_PORT, config.SMTP_SECURITY,
                     config.SMTP_USERNAME, config.SMTP_PASSWORD, config.SMTP_FROM)
    value.validate()
    return value


def send_message(recipient: str, subject: str, body: str, *, connection: Settings | None = None):
    value = connection or settings()
    value.validate()
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = value.sender, recipient, subject
    message.set_content(body)
    context = ssl.create_default_context()
    try:
        if value.security == 'ssl':
            transport = smtplib.SMTP_SSL(value.host, value.port, timeout=10, context=context)
        else:
            transport = smtplib.SMTP(value.host, value.port, timeout=10)
        with transport as smtp:
            if value.security == 'starttls':
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            if value.username:
                smtp.login(value.username, value.password)
            refused = smtp.send_message(message)
            if refused:
                raise DeliveryUnavailable('Email delivery was not accepted.')
    except (OSError, smtplib.SMTPException) as from_error:
        raise DeliveryUnavailable('Email delivery is temporarily unavailable.') from from_error


def send_code(recipient: str, code: str, purpose: str):
    action = 'set up your account' if purpose == 'signup' else 'reset your password'
    send_message(recipient, f'GovernSim: {"account verification" if purpose == "signup" else "password reset"} code',
                 f'Your GovernSim verification code is:\n\n{code}\n\n'
                 f'Use it in the browser where you requested it to {action}. '
                 'It expires in 5 minutes and can be used once. Never share this code.\n\n'
                 'If you did not request this, ignore this email. Your account has not changed.\n')
