"""TLS-only transactional SMTP delivery. Credentials and codes are never logged."""
from dataclasses import dataclass
from email.message import EmailMessage
import re
import smtplib
import socket
import ssl

from . import config


class DeliveryUnavailable(Exception):
    def __init__(self, message='Email delivery is temporarily unavailable.', *, reason='delivery', smtp_code=None):
        super().__init__(message)
        self.reason = reason
        self.smtp_code = smtp_code if isinstance(smtp_code, int) and 100 <= smtp_code <= 599 else None

    @property
    def diagnostic(self):
        # Only fixed descriptions and a numeric status are safe for local diagnostics.
        # Never include the provider response, credentials, message body or recipient map.
        descriptions = {
            'configuration': 'Invalid SMTP settings. Check the host, port, TLS mode, sender and username/password pair.',
            'authentication': 'The email server rejected the sender login. Use an App Password generated for the same account as the SMTP username.',
            'timeout': 'The SMTP connection timed out. Check your network/firewall. For Gmail, try STARTTLS on port 587 if SSL port 465 is blocked.',
            'dns': 'The SMTP hostname could not be resolved. Check the host spelling and your internet/DNS connection.',
            'certificate': 'The SMTP TLS certificate could not be verified. Check your computer clock and trusted certificates.',
            'tls': 'The SMTP TLS connection failed. Check the TLS mode and port supplied by your email provider.',
            'unsupported': 'The server does not support the requested TLS or authentication method. Check the SMTP provider settings.',
            'sender': 'The server rejected the From address. Use a sender address allowed by the authenticated SMTP account.',
            'recipient': 'The server rejected the delivery-test recipient. Check the admin email and provider delivery restrictions.',
            'rejected': 'The SMTP server rejected the request. Check the provider account settings and sending restrictions.',
            'connection': 'Could not connect to the SMTP server, or it disconnected. Check the host, port, network and firewall.',
        }
        detail = descriptions.get(self.reason, 'Email delivery failed. Check the SMTP sender configuration.')
        return detail + (f' (SMTP {self.smtp_code})' if self.smtp_code else '')


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
            raise DeliveryUnavailable('Email delivery is not configured correctly.', reason='configuration')


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
                raise DeliveryUnavailable(reason='recipient')
    except smtplib.SMTPAuthenticationError as error:
        raise DeliveryUnavailable(reason='authentication', smtp_code=error.smtp_code) from None
    except smtplib.SMTPSenderRefused as error:
        raise DeliveryUnavailable(reason='sender', smtp_code=error.smtp_code) from None
    except smtplib.SMTPRecipientsRefused:
        raise DeliveryUnavailable(reason='recipient') from None
    except smtplib.SMTPNotSupportedError:
        raise DeliveryUnavailable(reason='unsupported') from None
    except smtplib.SMTPResponseException as error:
        raise DeliveryUnavailable(reason='rejected', smtp_code=error.smtp_code) from None
    except ssl.SSLCertVerificationError:
        raise DeliveryUnavailable(reason='certificate') from None
    except ssl.SSLError:
        raise DeliveryUnavailable(reason='tls') from None
    except socket.gaierror:
        raise DeliveryUnavailable(reason='dns') from None
    except TimeoutError:
        raise DeliveryUnavailable(reason='timeout') from None
    except (OSError, smtplib.SMTPException):
        raise DeliveryUnavailable(reason='connection') from None


def send_code(recipient: str, code: str, purpose: str):
    action = 'set up your account' if purpose == 'signup' else 'reset your password'
    send_message(recipient, f'GovernSim: {"account verification" if purpose == "signup" else "password reset"} code',
                 f'Your GovernSim verification code is:\n\n{code}\n\n'
                 f'Use it in the browser where you requested it to {action}. '
                 'It expires in 5 minutes and can be used once. Never share this code.\n\n'
                 'If you did not request this, ignore this email. Your account has not changed.\n')
