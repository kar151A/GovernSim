"""SMTP TLS, delivery failures, and configuration persistence without real email."""
import smtplib
import socket
import ssl
import pytest
from app import mailer


@pytest.mark.parametrize('security', ['ssl', 'starttls'])
def test_smtp_uses_verified_tls_and_sends_only_to_requested_recipient(monkeypatch, security):
    calls = []
    class Transport:
        def __init__(self, *args, **kwargs):
            calls.append(('connect', args, kwargs))
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): calls.append(('ehlo',))
        def starttls(self, **kwargs): calls.append(('starttls', kwargs))
        def login(self, *args): calls.append(('login', args))
        def send_message(self, message):
            calls.append(('send', message))
            return {}
    monkeypatch.setattr(mailer.smtplib, 'SMTP_SSL', Transport)
    monkeypatch.setattr(mailer.smtplib, 'SMTP', Transport)
    settings = mailer.Settings('smtp.example.test', 465 if security == 'ssl' else 587,
                               security, 'sender@example.test', 'private-sender-key', 'sender@example.test')
    mailer.send_message('receiver@example.test', 'Test', 'Private code', connection=settings)
    if security == 'ssl':
        context = calls[0][2]['context']
        assert not any(call[0] == 'starttls' for call in calls)
    else:
        tls = next(i for i, call in enumerate(calls) if call[0] == 'starttls')
        login = next(i for i, call in enumerate(calls) if call[0] == 'login')
        assert tls < login
        context = calls[tls][1]['context']
    assert context.check_hostname
    import ssl
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert calls[-1][1]['To'] == 'receiver@example.test'
    assert calls[-1][1]['From'] == 'sender@example.test'


@pytest.mark.parametrize('security,sender', [('plain', 'sender@example.test'), ('ssl', ''),
                                            ('ssl', 'sender@example.test\nBcc: attacker@example.test')])
def test_invalid_or_plaintext_smtp_configuration_is_rejected(security, sender):
    with pytest.raises(mailer.DeliveryUnavailable):
        mailer.Settings('smtp.example.test', 465, security, '', '', sender).validate()


def test_smtp_authentication_error_does_not_expose_provider_message(monkeypatch):
    def fail(*args, **kwargs):
        raise smtplib.SMTPAuthenticationError(535, b'private provider response')
    monkeypatch.setattr(mailer.smtplib, 'SMTP_SSL', fail)
    with pytest.raises(mailer.DeliveryUnavailable) as result:
        mailer.send_message('receiver@example.test', 'Test', 'Private code', connection=mailer.Settings(
            'smtp.example.test', 465, 'ssl', 'sender@example.test', 'private-sender-key', 'sender@example.test'))
    assert 'private' not in str(result.value)


@pytest.mark.parametrize('host,password,stored', [('smtp.example.test', 'hidden-app-password', 'hidden-app-password'),
                                                ('smtp.gmail.com', 'abcd efgh ijkl mnop', 'abcdefghijklmnop')])
def test_configure_email_preserves_existing_env_and_hides_sender_password(tmp_path, monkeypatch, capsys, host, password, stored):
    import importlib.util
    from pathlib import Path
    from types import SimpleNamespace
    from app import config
    spec = importlib.util.spec_from_file_location('configure_email_test', Path(__file__).resolve().parents[2] / 'scripts/configure_email.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(config, 'AUTH_KEY', 'test-configuration-key')
    target = tmp_path / '.env'
    target.write_text('EXISTING_SETTING=preserve-me\n')
    answers = iter([host, 'ssl', '465', '', 'sender@example.test'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(module.getpass, 'getpass', lambda prompt: password)
    monkeypatch.setattr(module.mailer, 'send_message', lambda *args, **kwargs: None)
    monkeypatch.setattr(module.sys, 'argv', ['configure_email.py', '--admin-email', 'admin@example.test'])
    monkeypatch.setattr(module.db, 'init_db', lambda: None)
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def scalar(self, *args): return None
    monkeypatch.setattr(module.db, 'SessionLocal', Session)
    calls = []
    def run(*args, **kwargs):
        calls.append(args[0])
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(module.subprocess, 'run', run)
    module.main()
    contents = target.read_text()
    assert 'EXISTING_SETTING=preserve-me' in contents
    assert f"GOVERNSIM_SMTP_PASSWORD='{stored}'" in contents
    assert "GOVERNSIM_SMTP_USERNAME='admin@example.test'" in contents
    assert '--role' in calls[0] and 'ADMIN' in calls[0]
    output = capsys.readouterr().out
    assert password not in output and stored not in output


def test_configure_email_failed_delivery_saves_nothing(tmp_path, monkeypatch, capsys):
    import importlib.util
    from pathlib import Path
    from app import config
    spec = importlib.util.spec_from_file_location('configure_email_failure_test', Path(__file__).resolve().parents[2] / 'scripts/configure_email.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    monkeypatch.setattr(config, 'AUTH_KEY', 'test-configuration-key')
    answers = iter(['smtp.example.test', 'ssl', '465', 'sender@example.test', 'sender@example.test'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(module.getpass, 'getpass', lambda prompt: 'hidden-app-password')
    def fail(*args, **kwargs): raise mailer.DeliveryUnavailable('private raw provider response', reason='authentication', smtp_code=535)
    monkeypatch.setattr(module.mailer, 'send_message', fail)
    monkeypatch.setattr(module.sys, 'argv', ['configure_email.py', '--admin-email', 'admin@example.test'])
    with pytest.raises(SystemExit): module.main()
    assert not (tmp_path / '.env').exists()
    output = capsys.readouterr()
    assert 'SMTP 535' in output.err
    assert 'private raw provider response' not in output.err
    assert 'hidden-app-password' not in output.err + output.out


@pytest.mark.parametrize('error,reason,status', [
    (smtplib.SMTPAuthenticationError(535, b'private provider response'), 'authentication', 535),
    (smtplib.SMTPSenderRefused(550, b'private provider response', 'private-sender@example.test'), 'sender', 550),
    (smtplib.SMTPRecipientsRefused({'private-recipient@example.test': (550, b'private provider response')}), 'recipient', None),
    (smtplib.SMTPNotSupportedError('private provider response'), 'unsupported', None),
    (smtplib.SMTPDataError(554, b'private provider response'), 'rejected', 554),
    (ssl.SSLCertVerificationError(1, 'private provider response'), 'certificate', None),
    (ssl.SSLError(1, 'private provider response'), 'tls', None),
    (socket.gaierror(-2, 'private provider response'), 'dns', None),
    (TimeoutError('private provider response'), 'timeout', None),
    (ConnectionRefusedError('private provider response'), 'connection', None),
])
def test_smtp_failure_diagnostics_classify_cause_without_provider_data(monkeypatch, error, reason, status):
    def fail(*args, **kwargs): raise error
    monkeypatch.setattr(mailer.smtplib, 'SMTP_SSL', fail)
    with pytest.raises(mailer.DeliveryUnavailable) as caught:
        mailer.send_message('receiver@example.test', 'Test', 'private-message-body', connection=mailer.Settings(
            'smtp.example.test', 465, 'ssl', 'sender@example.test', 'private-sender-key', 'sender@example.test'))
    assert caught.value.reason == reason
    assert caught.value.smtp_code == status
    assert caught.value.__suppress_context__
    visible = caught.value.diagnostic + str(caught.value)
    for secret in ('private', 'receiver@example.test', 'sender@example.test'):
        assert secret not in visible
    if status:
        assert f'SMTP {status}' in visible
