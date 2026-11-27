from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Application, APIKeyMetadata
from app.auth.decorators import admin_required
from app.services.audit_service import log_audit

applications_bp = Blueprint('applications', __name__, url_prefix='/applications')

@applications_bp.route('', methods=['GET'])
@login_required
def index():
    apps = Application.query.order_by(Application.created_at.desc()).all()
    return render_template('applications/index.html', applications=apps)

@applications_bp.route('/new', methods=['POST'])
@login_required
@admin_required
def create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    environment = request.form.get('environment', 'Production').strip()
    owner_team = request.form.get('owner_team', '').strip()
    
    if not name or not owner_team:
        flash('Application Name and Owner Team are required.', 'danger')
        return redirect(url_for('applications.index'))
        
    existing = Application.query.filter_by(name=name).first()
    if existing:
        flash(f"An application named '{name}' already exists.", 'danger')
        return redirect(url_for('applications.index'))
        
    app_obj = Application(
        name=name,
        description=description,
        environment=environment,
        owner_team=owner_team,
        contact_email='',
        status='Active'
    )
    db.session.add(app_obj)
    db.session.commit()
    
    log_audit(
        action='APP_CREATED',
        resource_type='Application',
        resource_id=app_obj.id,
        details=f"Created application '{app_obj.name}' ({environment})",
        user=current_user
    )
    flash(f"Application '{app_obj.name}' created successfully.", 'success')
    return redirect(url_for('applications.index'))

@applications_bp.route('/<int:app_id>/edit', methods=['POST'])
@login_required
@admin_required
def edit(app_id):
    app_obj = Application.query.get_or_404(app_id)
    app_obj.name = request.form.get('name', '').strip()
    app_obj.description = request.form.get('description', '').strip()
    app_obj.environment = request.form.get('environment', app_obj.environment).strip()
    app_obj.owner_team = request.form.get('owner_team', '').strip()
    app_obj.status = request.form.get('status', app_obj.status)
    
    db.session.commit()
    
    log_audit(
        action='APP_UPDATED',
        resource_type='Application',
        resource_id=app_obj.id,
        details=f"Updated application '{app_obj.name}'",
        user=current_user
    )
    flash(f"Application '{app_obj.name}' updated successfully.", 'success')
    return redirect(url_for('applications.index'))

@applications_bp.route('/<int:app_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(app_id):
    app_obj = Application.query.get_or_404(app_id)
    name = app_obj.name
    # Unlink keys or let cascade handle
    keys = APIKeyMetadata.query.filter_by(application_id=app_id).all()
    for k in keys:
        k.application_id = None
        
    db.session.delete(app_obj)
    db.session.commit()
    
    log_audit(
        action='APP_DELETED',
        resource_type='Application',
        resource_id=app_id,
        details=f"Deleted application '{name}'",
        user=current_user
    )
    flash(f"Application '{name}' deleted.", 'info')
    return redirect(url_for('applications.index'))
