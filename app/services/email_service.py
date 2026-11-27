import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app, render_template


def is_smtp_configured():
    cfg = current_app.config
    return bool(
        cfg.get('SMTP_HOST')
        and cfg.get('SMTP_USER')
        and cfg.get('SMTP_PASSWORD')
        and get_alert_recipients()
    )


def get_alert_recipients():
    from app.models import SystemSetting
    db_recipients = SystemSetting.get_value('alert_recipient_emails', '').strip()
    raw = db_recipients if db_recipients else current_app.config.get('ALERT_RECIPIENT_EMAILS', '')
    return [e.strip() for e in raw.split(',') if e.strip()]


def send_smtp_email(subject, html_body, text_body=None, recipients=None, key_id=None, key_name=None, trigger_type='Alert'):
    """
    Sends an email using SMTP credentials loaded strictly from .env / app.config
    and records the attempt in EmailLog.
    Returns (success: bool, message: str).
    """
    from app.extensions import db
    from app.models import EmailLog

    cfg = current_app.config
    host = cfg.get('SMTP_HOST')
    port = int(cfg.get('SMTP_PORT', 587))
    use_tls = cfg.get('SMTP_USE_TLS', True)
    user = cfg.get('SMTP_USER')
    password = cfg.get('SMTP_PASSWORD')
    from_email = cfg.get('SMTP_FROM_EMAIL') or user
    to_list = recipients or get_alert_recipients()
    recipients_str = ', '.join(to_list) if to_list else 'None'

    if not host or not user or not password or not to_list:
        err = 'SMTP is not configured in .env (SMTP_HOST, SMTP_USER, SMTP_PASSWORD, ALERT_RECIPIENT_EMAILS).'
        return False, err

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"AI Key Manager <{from_email}>"
    msg['To'] = recipients_str

    if text_body:
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(from_email, to_list, msg.as_string())
        db.session.add(EmailLog(
            key_id=key_id,
            key_name=key_name,
            recipients=recipients_str,
            subject=subject,
            trigger_type=trigger_type,
            status='Sent'
        ))
        db.session.commit()
        return True, f"Email sent to {recipients_str}"
    except Exception as exc:
        db.session.add(EmailLog(
            key_id=key_id,
            key_name=key_name,
            recipients=recipients_str,
            subject=subject,
            trigger_type=trigger_type,
            status='Failed',
            error_message=str(exc)
        ))
        db.session.commit()
        return False, str(exc)


def send_expiry_alert_email(key, alert_type, days_left):
    """Renders the customized HTML expiry alert template and sends it via SMTP."""
    if not is_smtp_configured():
        return False, 'SMTP not configured'

    from datetime import datetime, timezone
    from app.models import APIKeyMetadata, SystemSetting

    is_expired = days_left <= 0

    try:
        total_keys_count = APIKeyMetadata.query.count()
        now = datetime.now(timezone.utc)
        critical_days = int(SystemSetting.get_value('expiry_critical_days', 7))
        expiring_keys_count = 0
        for k in APIKeyMetadata.query.filter(APIKeyMetadata.status != 'Revoked').all():
            if k.expires_at:
                exp = k.expires_at if k.expires_at.tzinfo else k.expires_at.replace(tzinfo=timezone.utc)
                if (exp - now).total_seconds() / 86400.0 <= critical_days:
                    expiring_keys_count += 1
    except Exception:
        total_keys_count = 1
        expiring_keys_count = 1

    subject = (
        f"[EXPIRED] AI Key '{key.name}' ({key.environment}) has expired"
        if is_expired
        else f"[URGENT: {int(days_left)}d left] AI Key '{key.name}' ({key.environment}) expiring soon"
    )

    html_body = render_template(
        'emails/expiry_alert.html',
        key=key,
        alert_type=alert_type,
        days_left=max(0, int(days_left)),
        is_expired=is_expired,
        total_keys_count=total_keys_count,
        expiring_keys_count=expiring_keys_count
    )

    text_body = (
        f"AI Key Manager Alert ({expiring_keys_count} Expiring / {total_keys_count} Total Keys): {alert_type}\n"
        f"Key Name: {key.name}\n"
        f"Application: {key.application.name if key.application else 'Standalone'}\n"
        f"Environment: {key.environment}\n"
        f"Provider: {key.provider}\n"
        f"Owner: {key.owner_name}\n"
        f"Allowed Models: {key.allowed_models or 'All'}\n"
        f"Expiry Date: {key.expires_at.strftime('%Y-%m-%d') if key.expires_at else 'N/A'}\n"
    )

    return send_smtp_email(
        subject,
        html_body,
        text_body=text_body,
        key_id=getattr(key, 'id', None),
        key_name=getattr(key, 'name', None),
        trigger_type=alert_type
    )
