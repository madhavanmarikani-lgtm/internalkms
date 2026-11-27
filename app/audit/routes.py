import csv
import io
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from app.models import AuditLog

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')


def _build_filtered_audit_query():
    action_filter = request.args.get('action', '').strip()
    resource_filter = request.args.get('resource_type', '').strip()
    user_filter = request.args.get('user', '').strip()
    search_query = request.args.get('q', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    query = AuditLog.query
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if resource_filter:
        query = query.filter(AuditLog.resource_type == resource_filter)
    if user_filter:
        query = query.filter(AuditLog.username.ilike(f"%{user_filter}%"))
    if search_query:
        term = f"%{search_query}%"
        query = query.filter(
            (AuditLog.details.ilike(term)) |
            (AuditLog.action.ilike(term)) |
            (AuditLog.username.ilike(term))
        )
    if date_from:
        try:
            start_dt = datetime.strptime(date_from, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            query = query.filter(AuditLog.timestamp >= start_dt)
        except ValueError:
            pass
    if date_to:
        try:
            end_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(AuditLog.timestamp <= end_dt)
        except ValueError:
            pass
            
    return query, {
        'current_action': action_filter,
        'current_resource': resource_filter,
        'current_user_filter': user_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to
    }


@audit_bp.route('', methods=['GET'])
@login_required
def index():
    query, filters = _build_filtered_audit_query()
    logs = query.order_by(AuditLog.timestamp.desc()).limit(200).all()
    
    actions = [r[0] for r in AuditLog.query.with_entities(AuditLog.action).distinct().all()]
    resources = [r[0] for r in AuditLog.query.with_entities(AuditLog.resource_type).distinct().all()]
    
    return render_template(
        'audit/index.html',
        logs=logs,
        actions=actions,
        resources=resources,
        **filters
    )


@audit_bp.route('/export', methods=['GET'])
@login_required
def export_csv():
    query, _ = _build_filtered_audit_query()
    logs = query.order_by(AuditLog.timestamp.desc()).limit(1000).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Timestamp (UTC)', 'Username', 'Action', 'Resource Type', 'Resource ID', 'IP Address', 'Details'])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
            log.username,
            log.action,
            log.resource_type,
            log.resource_id or '',
            log.ip_address or '',
            log.details or ''
        ])
        
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=ai_key_manager_audit_logs.csv'}
    )
