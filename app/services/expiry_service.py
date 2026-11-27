from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.extensions import db
from app.models import APIKeyMetadata, ExpiryAlert, SystemSetting
from app.services.email_service import send_expiry_alert_email, is_smtp_configured


def check_and_update_expiry_statuses(send_email=True):
    """
    Scans all API keys, updates status ('Expiring Soon', 'Expired', 'Active')
    and creates ExpiryAlert entries ONLY when <= critical_days (default 7 days) or Expired.
    """
    now = datetime.now(timezone.utc)
    critical_days = int(SystemSetting.get_value('expiry_critical_days', 7))
    
    keys = APIKeyMetadata.query.all()
    updated_count = 0
    new_alerts_count = 0
    pending_emails = []
    
    for key in keys:
        if not key.expires_at or key.status == 'Revoked':
            continue
            
        exp = key.expires_at if key.expires_at.tzinfo else key.expires_at.replace(tzinfo=timezone.utc)
        diff = exp - now
        days_left = diff.total_seconds() / 86400.0
        
        previous_status = key.status
        alert_type = None
        
        if days_left <= 0:
            key.status = 'Expired'
            alert_type = 'Expired'
            severity = 'danger'
            msg = f"Key '{key.name}' [{key.provider}] has expired on {exp.strftime('%Y-%m-%d')}."
        elif days_left <= critical_days:
            key.status = 'Expiring Soon'
            alert_type = f'Critical (<= {critical_days} days)'
            severity = 'danger'
            msg = f"CRITICAL: Key '{key.name}' expires in {int(days_left)} days on {exp.strftime('%Y-%m-%d')}!"
        else:
            if key.status == 'Expiring Soon':
                key.status = 'Active'
            
        if alert_type:
            existing = ExpiryAlert.query.filter_by(
                key_id=key.id,
                alert_type=alert_type
            ).first()
            
            if not existing:
                alert = ExpiryAlert(
                    key_id=key.id,
                    alert_type=alert_type,
                    severity=severity,
                    message=msg
                )
                db.session.add(alert)
                new_alerts_count += 1
                pending_emails.append((key, alert_type, days_left))
                
        if key.status != previous_status:
            updated_count += 1
            
    db.session.commit()

    if send_email:
        for key, alert_type, days_left in pending_emails:
            send_expiry_alert_email(key, alert_type, days_left)

    return {'updated_keys': updated_count, 'new_alerts': new_alerts_count}


def send_daily_expiry_reminders(force=False):
    """
    Runs daily at 10:30 AM IST.
    Sends a daily reminder email for every non-revoked key with <= 7 days remaining (or Expired),
    ensuring at most one reminder batch per IST calendar day.
    """
    ist_today = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m-%d')
    if not force:
        last_sent = SystemSetting.get_value('last_daily_reminder_ist_date', '')
        if last_sent == ist_today:
            return 0

    # Sync statuses first without double-sending inside check_and_update_expiry_statuses
    check_and_update_expiry_statuses(send_email=False)

    if not is_smtp_configured():
        return 0

    now = datetime.now(timezone.utc)
    critical_days = int(SystemSetting.get_value('expiry_critical_days', 7))
    keys = APIKeyMetadata.query.filter(APIKeyMetadata.status != 'Revoked').all()

    sent_count = 0
    for key in keys:
        if not key.expires_at:
            continue
        exp = key.expires_at if key.expires_at.tzinfo else key.expires_at.replace(tzinfo=timezone.utc)
        days_left = (exp - now).total_seconds() / 86400.0

        if days_left <= critical_days:
            alert_type = 'Expired' if days_left <= 0 else f'Daily Reminder ({int(days_left)}d left)'
            ok, _ = send_expiry_alert_email(key, alert_type, days_left)
            if ok:
                sent_count += 1

    SystemSetting.set_value('last_daily_reminder_ist_date', ist_today, 'Last IST date daily 10:30 AM reminder ran')
    return sent_count
