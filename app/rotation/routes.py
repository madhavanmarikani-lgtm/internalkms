from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import APIKeyMetadata, KeyRotationLog
from app.auth.decorators import admin_required
from app.services.rotation_service import perform_key_rotation

rotation_bp = Blueprint('rotation', __name__, url_prefix='/rotation')


@rotation_bp.route('', methods=['GET'])
@login_required
@admin_required
def index():
    all_keys = APIKeyMetadata.query.filter(
        APIKeyMetadata.status != 'Revoked'
    ).order_by(APIKeyMetadata.expires_at.asc()).all()
    
    recent_logs = KeyRotationLog.query.order_by(KeyRotationLog.rotation_date.desc()).limit(20).all()
    
    return render_template(
        'rotation/index.html',
        all_keys=all_keys,
        recent_logs=recent_logs
    )


@rotation_bp.route('/<int:key_id>/rotate', methods=['POST'])
@login_required
@admin_required
def rotate_key(key_id):
    key = APIKeyMetadata.query.get_or_404(key_id)
    new_key_id = request.form.get('new_key_identifier', '').strip()
    reason = request.form.get('reason', 'Instant Key Rotation').strip()
    notes = request.form.get('notes', '').strip()
    
    if not new_key_id:
        flash('A new Key ID is required to rotate this key.', 'danger')
        return redirect(request.referrer or url_for('rotation.index'))
        
    perform_key_rotation(key, new_key_id, current_user, reason, notes)
    
    flash(f"Key '{key.name}' rotated immediately! Status is Active and expiry reset to {key.expires_at.strftime('%Y-%m-%d')}.", 'success')
    return redirect(request.referrer or url_for('rotation.index'))
