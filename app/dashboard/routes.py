from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models import APIKeyMetadata, Application, ExpiryAlert, AuditLog, KeyRotationLog
from app.services.expiry_service import check_and_update_expiry_statuses

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Sync expiry statuses on dashboard visit
    check_and_update_expiry_statuses()
    
    total_keys = APIKeyMetadata.query.count()
    active_keys = APIKeyMetadata.query.filter_by(status='Active').count()
    expiring_soon_keys = APIKeyMetadata.query.filter_by(status='Expiring Soon').count()
    expired_keys = APIKeyMetadata.query.filter_by(status='Expired').count()
    revoked_keys = APIKeyMetadata.query.filter_by(status='Revoked').count()
    total_apps = Application.query.count()
    
    unacked_alerts_count = ExpiryAlert.query.filter_by(is_acknowledged=False).count()
    
    # Provider breakdown for Chart.js
    provider_counts = db.session.query(
        APIKeyMetadata.provider, func.count(APIKeyMetadata.id)
    ).group_by(APIKeyMetadata.provider).all()
    
    provider_labels = [p[0] for p in provider_counts]
    provider_data = [p[1] for p in provider_counts]
    
    # Environment breakdown for Chart.js
    env_counts = db.session.query(
        APIKeyMetadata.environment, func.count(APIKeyMetadata.id)
    ).group_by(APIKeyMetadata.environment).all()
    
    env_labels = [e[0] for e in env_counts]
    env_data = [e[1] for e in env_counts]
    
    # Keys due for rotation soon (within 30 days) or overdue
    now = datetime.now(timezone.utc)
    in_7_days = now + timedelta(days=7)
    in_30_days = now + timedelta(days=30)
    
    # 7-day expiring keys
    expiring_7d = APIKeyMetadata.query.filter(
        APIKeyMetadata.status != 'Revoked',
        APIKeyMetadata.expires_at != None,
        APIKeyMetadata.expires_at <= in_7_days,
        APIKeyMetadata.expires_at >= now
    ).order_by(APIKeyMetadata.expires_at.asc()).all()

    # All keys for clean dashboard list
    all_keys = APIKeyMetadata.query.order_by(APIKeyMetadata.created_at.desc()).all()
    
    upcoming_rotations = APIKeyMetadata.query.filter(
        APIKeyMetadata.status != 'Revoked',
        APIKeyMetadata.next_rotation_at != None,
        APIKeyMetadata.next_rotation_at <= in_30_days
    ).order_by(APIKeyMetadata.next_rotation_at.asc()).limit(5).all()
    
    # Critical alerts
    critical_alerts = ExpiryAlert.query.filter_by(is_acknowledged=False).order_by(
        ExpiryAlert.triggered_at.desc()
    ).limit(5).all()
    
    # Recent audit logs
    recent_audits = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(7).all()
    
    # Monthly budget sum
    budget_sum = db.session.query(func.sum(APIKeyMetadata.monthly_budget_limit)).scalar() or 0.0

    return render_template(
        'dashboard.html',
        total_keys=total_keys,
        active_keys=active_keys,
        expiring_soon_keys=expiring_soon_keys,
        expired_keys=expired_keys,
        revoked_keys=revoked_keys,
        total_apps=total_apps,
        unacked_alerts_count=unacked_alerts_count,
        budget_sum=budget_sum,
        provider_labels=provider_labels,
        provider_data=provider_data,
        env_labels=env_labels,
        env_data=env_data,
        upcoming_rotations=upcoming_rotations,
        critical_alerts=critical_alerts,
        recent_audits=recent_audits,
        expiring_7d=expiring_7d,
        all_keys=all_keys
    )
