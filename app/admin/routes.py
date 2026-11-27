import csv
import hmac
import io
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, send_file, current_app, session
from flask_login import login_required, current_user
from sqlalchemy import text, inspect
from app.extensions import db
from app.models import User, SystemSetting
from app.auth.decorators import admin_required
from app.services.audit_service import log_audit

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/users', methods=['GET'])
@login_required
@admin_required
def users():
    user_list = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=user_list)

@admin_bp.route('/users/new', methods=['POST'])
@login_required
@admin_required
def create_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role', 'Viewer')
    
    if not username or not email or not password:
        flash('Username, Email, and Password are required.', 'danger')
        return redirect(url_for('admin.users'))
        
    if User.query.filter_by(username=username).first():
        flash(f"Username '{username}' already taken.", 'danger')
        return redirect(url_for('admin.users'))
        
    if User.query.filter_by(email=email).first():
        flash(f"Email '{email}' is already registered.", 'danger')
        return redirect(url_for('admin.users'))
        
    new_user = User(
        username=username,
        email=email,
        role=role if role in ['Admin', 'Viewer'] else 'Viewer',
        is_active_account=True
    )
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    log_audit(
        action='USER_CREATED',
        resource_type='User',
        resource_id=new_user.id,
        details=f"Created user {username} with role {role}",
        user=current_user
    )
    flash(f"User '{username}' created successfully.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    if user_id == current_user.id:
        flash("You cannot deactivate your own account.", 'danger')
        return redirect(url_for('admin.users'))
        
    user = User.query.get_or_404(user_id)
    user.is_active_account = not user.is_active_account
    db.session.commit()
    
    status_str = "activated" if user.is_active_account else "deactivated"
    log_audit(
        action='USER_STATUS_CHANGED',
        resource_type='User',
        resource_id=user.id,
        details=f"User {user.username} {status_str}",
        user=current_user
    )
    flash(f"User '{user.username}' has been {status_str}.", 'info')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    if user_id == current_user.id:
        flash("You cannot change your own role.", 'danger')
        return redirect(url_for('admin.users'))
        
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role in ['Admin', 'Viewer']:
        old_role = user.role
        user.role = new_role
        db.session.commit()
        
        log_audit(
            action='USER_ROLE_CHANGED',
            resource_type='User',
            resource_id=user.id,
            details=f"Changed role for {user.username} from {old_role} to {new_role}",
            user=current_user
        )
        flash(f"Updated role for '{user.username}' to {new_role}.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')
    if not new_password or len(new_password) < 6:
        flash("Password must be at least 6 characters.", 'danger')
        return redirect(url_for('admin.users'))
        
    user.set_password(new_password)
    db.session.commit()
    
    log_audit(
        action='USER_PASSWORD_RESET',
        resource_type='User',
        resource_id=user.id,
        details=f"Password reset for user {user.username}",
        user=current_user
    )
    flash(f"Password reset successfully for '{user.username}'.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        app_title = request.form.get('app_title', 'AI Key Manager').strip()
        notice_days = request.form.get('expiry_notice_days', '30').strip()
        warning_days = request.form.get('expiry_warning_days', '14').strip()
        critical_days = request.form.get('expiry_critical_days', '7').strip()
        alert_recipients = request.form.get('alert_recipient_emails', '').strip()
        
        SystemSetting.set_value('app_title', app_title, 'Application header title')
        SystemSetting.set_value('expiry_notice_days', notice_days, 'Days threshold for notice alert')
        SystemSetting.set_value('expiry_warning_days', warning_days, 'Days threshold for warning alert')
        SystemSetting.set_value('expiry_critical_days', critical_days, 'Days threshold for critical alert')
        SystemSetting.set_value('alert_recipient_emails', alert_recipients, 'Comma-separated alert recipient emails')
        
        log_audit(
            action='SETTINGS_UPDATED',
            resource_type='Settings',
            details="System settings updated by administrator",
            user=current_user
        )
        flash('System settings updated successfully.', 'success')
        return redirect(url_for('admin.settings'))
        
    from app.services.email_service import is_smtp_configured, get_alert_recipients
    env_recipients = current_app.config.get('ALERT_RECIPIENT_EMAILS', '')
    db_recipients = SystemSetting.get_value('alert_recipient_emails', '').strip()
    active_recipients = db_recipients if db_recipients else env_recipients

    current_settings = {
        'app_title': SystemSetting.get_value('app_title', 'AI Key Manager'),
        'expiry_notice_days': SystemSetting.get_value('expiry_notice_days', '30'),
        'expiry_warning_days': SystemSetting.get_value('expiry_warning_days', '14'),
        'expiry_critical_days': SystemSetting.get_value('expiry_critical_days', '7'),
        'alert_recipient_emails': active_recipients,
    }
    return render_template(
        'admin/settings.html',
        settings=current_settings,
        smtp_configured=is_smtp_configured(),
        smtp_host=current_app.config.get('SMTP_HOST', ''),
        smtp_port=current_app.config.get('SMTP_PORT', 587),
        smtp_recipients=active_recipients
    )


@admin_bp.route('/settings/test-email', methods=['POST'])
@login_required
@admin_required
def send_test_email():
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    from app.models import APIKeyMetadata
    from app.services.email_service import send_expiry_alert_email, send_smtp_email

    sample_key = APIKeyMetadata.query.filter(APIKeyMetadata.status != 'Revoked').order_by(APIKeyMetadata.expires_at.asc()).first()
    if sample_key:
        days_left = sample_key.days_until_expiry if sample_key.days_until_expiry is not None else 5
        ok, msg = send_expiry_alert_email(sample_key, f'Critical (<= 7 days)', days_left)
    else:
        dummy_key = SimpleNamespace(
            id=1,
            name='Sample OpenAI Key',
            application=SimpleNamespace(name='AI Key Manager'),
            environment='Production',
            provider='OpenAI',
            owner_name=current_user.username,
            allowed_models='gpt-6.2-astra',
            expires_at=datetime.now(timezone.utc) + timedelta(days=5)
        )
        ok, msg = send_expiry_alert_email(dummy_key, 'Critical (<= 7 days)', 5)

    if ok:
        log_audit(action='SMTP_TEST_SENT', resource_type='Settings', details=msg, user=current_user)
        flash(f'Alert email sent successfully using template: {msg}', 'success')
    else:
        flash(f'Failed to send test email: {msg}', 'danger')
    return redirect(url_for('admin.settings'))


def _is_db_unlocked():
    return session.get('db_unlocked') is True


@admin_bp.route('/database/unlock', methods=['POST'])
@login_required
@admin_required
def unlock_database():
    entered = request.form.get('db_password', '')
    expected = current_app.config.get('DATABASE_ACCESS_PASSWORD', 'DbAdmin@2026')
    if entered and hmac.compare_digest(entered, expected):
        session['db_unlocked'] = True
        log_audit(
            action='DATABASE_UNLOCKED',
            resource_type='Database',
            details=f"Admin {current_user.username} unlocked Database Explorer",
            user=current_user
        )
        flash('Database Explorer unlocked.', 'success')
        return redirect(url_for('admin.database'))
    log_audit(
        action='DATABASE_UNLOCK_FAILED',
        resource_type='Database',
        details=f"Failed database password attempt by {current_user.username}",
        user=current_user
    )
    flash('Incorrect database password. Access denied.', 'danger')
    return redirect(url_for('admin.database'))


@admin_bp.route('/database/lock', methods=['POST'])
@login_required
@admin_required
def lock_database():
    session.pop('db_unlocked', None)
    flash('Database Explorer locked.', 'info')
    return redirect(url_for('admin.database'))


@admin_bp.route('/database', methods=['GET'])
@login_required
@admin_required
def database():
    if not _is_db_unlocked():
        return render_template('admin/database_unlock.html')

    inspector = inspect(db.engine)
    table_names = sorted(inspector.get_table_names())
    
    table_counts = {}
    for t in table_names:
        count = db.session.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        table_counts[t] = count
        
    selected_table = request.args.get('table', 'api_key_metadata' if 'api_key_metadata' in table_names else (table_names[0] if table_names else ''))
    if selected_table not in table_names and table_names:
        selected_table = table_names[0]
        
    columns = []
    rows = []
    pk_col = None
    pk_index = None
    if selected_table:
        pk_info = inspector.get_pk_constraint(selected_table)
        pk_cols = pk_info.get('constrained_columns') or []
        pk_col = pk_cols[0] if pk_cols else None
        
        result = db.session.execute(text(f'SELECT * FROM "{selected_table}" LIMIT 500'))
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
        if pk_col and pk_col in columns:
            pk_index = columns.index(pk_col)
        
    return render_template(
        'admin/database.html',
        table_names=table_names,
        table_counts=table_counts,
        selected_table=selected_table,
        columns=columns,
        rows=rows,
        pk_col=pk_col,
        pk_index=pk_index
    )


@admin_bp.route('/database/edit', methods=['POST'])
@login_required
@admin_required
def edit_db_row():
    if not _is_db_unlocked():
        flash('Database password required.', 'danger')
        return redirect(url_for('admin.database'))
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    table = request.form.get('table', '').strip()
    pk_col = request.form.get('pk_col', '').strip()
    pk_val = request.form.get('pk_val', '').strip()
    
    if table not in table_names or not pk_col:
        flash('Invalid table or primary key.', 'danger')
        return redirect(url_for('admin.database'))
        
    cols_meta = [c['name'] for c in inspector.get_columns(table)]
    if pk_col not in cols_meta:
        flash('Invalid primary key column.', 'danger')
        return redirect(url_for('admin.database', table=table))
        
    updates = {}
    set_clauses = []
    for col in cols_meta:
        if col == pk_col:
            continue
        field_key = f'col_{col}'
        if field_key in request.form:
            val = request.form.get(field_key)
            # Treat literal 'NULL' or empty optional if checkbox not needed; keep exact string or None if null checkbox checked
            if request.form.get(f'null_{col}') == '1':
                val = None
            updates[f'p_{col}'] = val
            set_clauses.append(f'"{col}" = :p_{col}')
            
    if set_clauses:
        updates['pk_val'] = pk_val
        sql = text(f'UPDATE "{table}" SET {", ".join(set_clauses)} WHERE "{pk_col}" = :pk_val')
        db.session.execute(sql, updates)
        db.session.commit()
        log_audit(
            action='DATABASE_ROW_UPDATED',
            resource_type='Database',
            resource_id=f'{table}:{pk_val}',
            details=f"Admin edited row {pk_col}={pk_val} in table '{table}'",
            user=current_user
        )
        flash(f"Row {pk_col}={pk_val} in '{table}' updated successfully.", 'success')
        
    return redirect(url_for('admin.database', table=table))


@admin_bp.route('/database/delete', methods=['POST'])
@login_required
@admin_required
def delete_db_row():
    if not _is_db_unlocked():
        flash('Database password required.', 'danger')
        return redirect(url_for('admin.database'))
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    table = request.form.get('table', '').strip()
    pk_col = request.form.get('pk_col', '').strip()
    pk_val = request.form.get('pk_val', '').strip()
    
    if table not in table_names or not pk_col:
        flash('Invalid table or primary key.', 'danger')
        return redirect(url_for('admin.database'))
        
    cols_meta = [c['name'] for c in inspector.get_columns(table)]
    if pk_col not in cols_meta:
        flash('Invalid primary key column.', 'danger')
        return redirect(url_for('admin.database', table=table))
        
    if table == 'users' and str(pk_val) == str(current_user.id):
        flash('You cannot delete your own active user record.', 'danger')
        return redirect(url_for('admin.database', table=table))
        
    if table == 'api_key_metadata':
        db.session.execute(text('DELETE FROM "expiry_alerts" WHERE "key_id" = :pk_val'), {'pk_val': pk_val})
        db.session.execute(text('DELETE FROM "key_rotation_logs" WHERE "key_id" = :pk_val'), {'pk_val': pk_val})
        
    db.session.execute(text(f'DELETE FROM "{table}" WHERE "{pk_col}" = :pk_val'), {'pk_val': pk_val})
    db.session.commit()
    
    log_audit(
        action='DATABASE_ROW_DELETED',
        resource_type='Database',
        resource_id=f'{table}:{pk_val}',
        details=f"Admin deleted row {pk_col}={pk_val} from table '{table}'",
        user=current_user
    )
    flash(f"Row {pk_col}={pk_val} deleted from '{table}'.", 'info')
    return redirect(url_for('admin.database', table=table))


@admin_bp.route('/database/export', methods=['GET'])
@login_required
@admin_required
def export_table_csv():
    if not _is_db_unlocked():
        flash('Database password required.', 'danger')
        return redirect(url_for('admin.database'))
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    selected_table = request.args.get('table', '')
    if selected_table not in table_names:
        flash('Invalid table selected for export.', 'danger')
        return redirect(url_for('admin.database'))
        
    result = db.session.execute(text(f'SELECT * FROM "{selected_table}"'))
    columns = list(result.keys())
    rows = result.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(list(row))
        
    output.seek(0)
    log_audit(
        action='DATABASE_TABLE_EXPORTED',
        resource_type='Database',
        resource_id=selected_table,
        details=f"Admin exported table '{selected_table}' as CSV",
        user=current_user
    )
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename={selected_table}.csv'}
    )


@admin_bp.route('/database/download', methods=['GET'])
@login_required
@admin_required
def download_db():
    if not _is_db_unlocked():
        flash('Database password required.', 'danger')
        return redirect(url_for('admin.database'))
    db_path = os.path.join(current_app.config['INSTANCE_DIR'], 'ai_key_manager.db')
    if not os.path.exists(db_path):
        flash('Database file not found.', 'danger')
        return redirect(url_for('admin.database'))
        
    log_audit(
        action='DATABASE_BACKUP_DOWNLOADED',
        resource_type='Database',
        details="Admin downloaded SQLite database backup",
        user=current_user
    )
    return send_file(db_path, as_attachment=True, download_name='ai_key_manager.db')


@admin_bp.route('/email-monitoring', methods=['GET'])
@login_required
@admin_required
def email_monitoring():
    from datetime import datetime, timezone
    from app.models import EmailLog, APIKeyMetadata
    from app.services.email_service import is_smtp_configured, get_alert_recipients

    logs = EmailLog.query.order_by(EmailLog.sent_at.desc()).limit(200).all()
    total_sent = EmailLog.query.filter_by(status='Sent').count()
    total_failed = EmailLog.query.filter_by(status='Failed').count()

    now = datetime.now(timezone.utc)
    critical_days = int(SystemSetting.get_value('expiry_critical_days', 7))
    queued_keys = []
    for k in APIKeyMetadata.query.filter(APIKeyMetadata.status != 'Revoked').all():
        if k.expires_at:
            exp = k.expires_at if k.expires_at.tzinfo else k.expires_at.replace(tzinfo=timezone.utc)
            days_left = (exp - now).total_seconds() / 86400.0
            if days_left <= critical_days:
                queued_keys.append(k)

    last_reminder_date = SystemSetting.get_value('last_daily_reminder_ist_date', 'Not run yet')

    return render_template(
        'admin/email_monitoring.html',
        logs=logs,
        total_sent=total_sent,
        total_failed=total_failed,
        queued_keys=queued_keys,
        smtp_configured=is_smtp_configured(),
        recipients=get_alert_recipients(),
        last_reminder_date=last_reminder_date
    )


@admin_bp.route('/email-monitoring/run-now', methods=['POST'])
@login_required
@admin_required
def run_daily_reminder_now():
    from app.services.expiry_service import send_daily_expiry_reminders
    sent = send_daily_expiry_reminders(force=True)
    log_audit(
        action='DAILY_REMINDER_TRIGGERED',
        resource_type='Email',
        details=f"Admin manually triggered daily reminder job ({sent} email(s) sent)",
        user=current_user
    )
    flash(f'Daily reminder job executed: {sent} email(s) sent.', 'success' if sent >= 0 else 'info')
    return redirect(url_for('admin.email_monitoring'))
