from flask import request
from flask_login import current_user
from app.extensions import db
from app.models import AuditLog

def log_audit(action, resource_type, resource_id=None, details=None, user=None, ip_address=None):
    """
    Record an event in the AuditLog.
    """
    try:
        username = 'System'
        user_id = None
        
        if user:
            username = user.username
            user_id = user.id
        elif current_user and current_user.is_authenticated:
            username = current_user.username
            user_id = current_user.id
            
        ip = ip_address
        if not ip:
            try:
                ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            except Exception:
                ip = '127.0.0.1'
                
        entry = AuditLog(
            username=username,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=ip,
            details=details
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    except Exception as e:
        db.session.rollback()
        print(f"Error logging audit: {e}")
        return None
