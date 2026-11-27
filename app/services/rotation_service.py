from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models import KeyRotationLog, ExpiryAlert
from app.services.audit_service import log_audit
from app.services.crypto_service import encrypt_value


def sanitize_and_mask_key_identifier(input_identifier, provider='Unknown'):
    """Legacy helper retained for compatibility."""
    clean = input_identifier.strip()
    if '...' in clean:
        return clean
    length = len(clean)
    if length <= 8:
        return f"{clean[:2]}...{clean[-2:]}" if length >= 4 else f"{clean[:1]}...*"
    prefix_len = 7 if clean.startswith('sk-') or clean.startswith('AIza') else 4
    return f"{clean[:prefix_len]}...{clean[-4:]}"


def perform_key_rotation(key, new_key_id, user, reason, notes=None):
    """
    Executes instant rotation for an API key:
    - Encrypts and updates provider_key_id
    - Updates last_rotated_at to now
    - Resets expires_at to 30 days from now
    - Sets status back to Active and clears pending expiry alerts
    """
    now = datetime.now(timezone.utc)
    
    # Encrypt and store the new Key ID
    if new_key_id:
        key.provider_key_id = encrypt_value(new_key_id.strip())
    key.key_identifier = ''
    key.last_rotated_at = now
    key.next_rotation_at = None
    key.expires_at = now + timedelta(days=30)
    key.status = 'Active'
    
    # Clear any pending expiry alerts for this key since it has been rotated
    ExpiryAlert.query.filter_by(key_id=key.id, is_acknowledged=False).update({
        'is_acknowledged': True,
        'acknowledged_by': user.username if user else 'System',
        'acknowledged_at': now
    })
        
    # Create rotation log entry
    rot_log = KeyRotationLog(
        key_id=key.id,
        user_id=user.id if user else None,
        rotation_date=now,
        previous_identifier='Encrypted',
        new_identifier='Encrypted',
        reason=reason or 'Instant Key Rotation',
        status='Completed',
        notes=notes
    )
    db.session.add(rot_log)
    db.session.commit()
    
    # Audit log
    log_audit(
        action='KEY_ROTATED',
        resource_type='APIKey',
        resource_id=key.id,
        details=f"Instantly rotated key '{key.name}' [{key.provider}]. New expiry: {key.expires_at.strftime('%Y-%m-%d')}. Reason: {reason}",
        user=user
    )
    
    return rot_log
