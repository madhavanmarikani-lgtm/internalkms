from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from app.services.audit_service import log_audit

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))
        
        user = User.query.filter((User.username == username) | (User.email == username)).first()
        
        if user and user.check_password(password):
            if not user.is_active_account:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('login.html', username=username)
                
            login_user(user, remember=remember)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            
            log_audit(
                action='USER_LOGIN',
                resource_type='Auth',
                resource_id=user.id,
                details=f"User {user.username} logged in successfully",
                user=user
            )
            
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
            log_audit(
                action='LOGIN_FAILED',
                resource_type='Auth',
                details=f"Failed login attempt for username: {username}"
            )
            
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    from flask import session
    username = current_user.username
    uid = current_user.id
    user_obj = current_user._get_current_object()
    
    session.pop('db_unlocked', None)
    logout_user()
    log_audit(
        action='USER_LOGOUT',
        resource_type='Auth',
        resource_id=uid,
        details=f"User {username} logged out"
    )
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    if not new_pw or len(new_pw) < 6:
        flash('New password must be at least 6 characters long.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    if new_pw != confirm_pw:
        flash('New password and confirmation do not match.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))

    current_user.set_password(new_pw)
    db.session.commit()

    log_audit(
        action='USER_PASSWORD_CHANGED',
        resource_type='User',
        resource_id=current_user.id,
        details=f"User {current_user.username} changed their password",
        user=current_user
    )
    flash('Your password has been updated successfully.', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))
