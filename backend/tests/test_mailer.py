"""SMTP TLS, delivery failures, and configuration persistence without real email."""
import smtplib
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


def test_configure_email_preserves_existing_env_and_hides_sender_password(tmp_path, monkeypatch, capsys):
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
    answers = iter(['smtp.example.test', 'ssl', '465', 'sender@example.test', 'sender@example.test'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(module.getpass, 'getpass', lambda prompt: 'hidden-app-password')
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
    assert "GOVERNSIM_SMTP_PASSWORD='hidden-app-password'" in contents
    assert '--role' in calls[0] and 'ADMIN' in calls[0]
    assert 'hidden-app-password' not in capsys.readouterr().out


def test_configure_email_failed_delivery_saves_nothing(tmp_path, monkeypatch):
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
    def fail(*args, **kwargs): raise mailer.DeliveryUnavailable()
    monkeypatch.setattr(module.mailer, 'send_message', fail)
    monkeypatch.setattr(module.sys, 'argv', ['configure_email.py', '--admin-email', 'admin@example.test'])
    with pytest.raises(SystemExit): module.main()
    assert not (tmp_path / '.env').exists()
