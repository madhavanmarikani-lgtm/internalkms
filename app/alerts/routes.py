from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import ExpiryAlert
from app.auth.decorators import admin_required
from app.services.expiry_service import check_and_update_expiry_statuses
from app.services.audit_service import log_audit

alerts_bp = Blueprint('alerts', __name__, url_prefix='/alerts')

@alerts_bp.route('', methods=['GET'])
@login_required
def index():
    status_filter = request.args.get('status', 'unack')  # 'unack', 'acked', 'all'
    severity_filter = request.args.get('severity', '')
    
    query = ExpiryAlert.query
    
    if status_filter == 'unack':
        query = query.filter_by(is_acknowledged=False)
    elif status_filter == 'acked':
        query = query.filter_by(is_acknowledged=True)
        
    if severity_filter:
        query = query.filter_by(severity=severity_filter)
        
    alerts = query.order_by(ExpiryAlert.triggered_at.desc()).all()
    
    unack_count = ExpiryAlert.query.filter_by(is_acknowledged=False).count()
    acked_count = ExpiryAlert.query.filter_by(is_acknowledged=True).count()
    
    return render_template(
        'alerts/index.html',
        alerts=alerts,
        status_filter=status_filter,
        severity_filter=severity_filter,
        unack_count=unack_count,
        acked_count=acked_count
    )

@alerts_bp.route('/<int:alert_id>/acknowledge', methods=['POST'])
@login_required
def acknowledge(alert_id):
    alert = ExpiryAlert.query.get_or_404(alert_id)
    alert.is_acknowledged = True
    alert.acknowledged_by = current_user.username
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.session.commit()
    
    log_audit(
        action='ALERT_ACKNOWLEDGED',
        resource_type='Alert',
        resource_id=alert.id,
        details=f"Alert for Key#{alert.key_id} acknowledged by {current_user.username}",
        user=current_user
    )
    flash(f"Alert acknowledged.", 'info')
    return redirect(request.referrer or url_for('alerts.index'))

@alerts_bp.route('/check-now', methods=['POST'])
@login_required
def check_now():
    result = check_and_update_expiry_statuses()
    flash(f"Scanned all keys! {result['updated_keys']} keys refreshed, {result['new_alerts']} new alerts created.", 'success')
    return redirect(url_for('alerts.index'))
