from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import APIKeyMetadata, Application, KeyRotationLog, ExpiryAlert
from app.auth.decorators import admin_required
from app.services.audit_service import log_audit
from app.services.crypto_service import encrypt_value

api_keys_bp = Blueprint('api_keys', __name__, url_prefix='/api-keys')

AVAILABLE_PROVIDERS = [
    'OpenAI', 'Google', 'Claude', 'Kling', 'Seedance'
]

ENVIRONMENTS = ['Production', 'UAT']


def _get_or_create_application(app_name, environment='Production'):
    if not app_name:
        return None
    existing = Application.query.filter(Application.name.ilike(app_name)).first()
    if existing:
        return existing
    new_app = Application(
        name=app_name,
        environment=environment,
        owner_team='Engineering',
        contact_email='',
        status='Active'
    )
    db.session.add(new_app)
    db.session.flush()
    return new_app


@api_keys_bp.route('', methods=['GET'])
@login_required
def index():
    provider_filter = request.args.get('provider', '').strip()
    env_filter = request.args.get('environment', '').strip()
    status_filter = request.args.get('status', '').strip()
    app_filter = request.args.get('application_id', '').strip()
    search_query = request.args.get('q', '').strip()
    
    query = APIKeyMetadata.query
    
    if provider_filter:
        query = query.filter(APIKeyMetadata.provider == provider_filter)
    if env_filter:
        query = query.filter(APIKeyMetadata.environment == env_filter)
    if status_filter:
        query = query.filter(APIKeyMetadata.status == status_filter)
    if app_filter and app_filter.isdigit():
        query = query.filter(APIKeyMetadata.application_id == int(app_filter))
    if search_query:
        term = f"%{search_query}%"
        query = query.filter(
            (APIKeyMetadata.name.ilike(term)) |
            (APIKeyMetadata.owner_name.ilike(term)) |
            (APIKeyMetadata.allowed_models.ilike(term))
        )
        
    keys = query.order_by(APIKeyMetadata.created_at.desc()).all()
    applications = Application.query.order_by(Application.name.asc()).all()
    
    return render_template(
        'api_keys/index.html',
        keys=keys,
        applications=applications,
        providers=AVAILABLE_PROVIDERS,
        environments=ENVIRONMENTS,
        current_provider=provider_filter,
        current_env=env_filter,
        current_status=status_filter,
        current_app=app_filter,
        search_query=search_query
    )


@api_keys_bp.route('/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    applications = Application.query.order_by(Application.name.asc()).all()
    now = datetime.now(timezone.utc)
    default_expiry_date = (now + timedelta(days=30)).strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        app_name = request.form.get('application_name', '').strip()
        environment = request.form.get('environment', 'Production').strip()
        provider = request.form.get('provider', '').strip()
        
        project_name = request.form.get('project_name', '').strip()
        provider_key_id = request.form.get('provider_key_id', '').strip()
        workspace_id = request.form.get('workspace_id', '').strip()
        
        name = request.form.get('name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        allowed_models = request.form.get('allowed_models', 'gpt-4o').strip()
        
        # Backend validation
        if not app_name or not name or not provider or not owner_name:
            flash('Please fill in all required fields (Application, Environment, AI Provider, Key Name, Owner).', 'danger')
            return render_template(
                'api_keys/form.html',
                action='Create',
                applications=applications,
                providers=AVAILABLE_PROVIDERS,
                environments=ENVIRONMENTS,
                default_expiry_date=default_expiry_date,
                key=None
            )
            
        app_obj = _get_or_create_application(app_name, environment)
        
        # Expiry date is strictly 30 days from creation date and not editable
        expires_at = now + timedelta(days=30)
        next_rotation = now + timedelta(days=30)
        
        new_key = APIKeyMetadata(
            name=name,
            provider=provider,
            key_identifier='',
            environment=environment,
            application_id=app_obj.id if app_obj else None,
            openai_project=encrypt_value(project_name) if project_name else None,
            provider_key_id=encrypt_value(provider_key_id) if provider_key_id else None,
            workspace_id=encrypt_value(workspace_id) if workspace_id else None,
            owner_name=owner_name,
            owner_email=f"{owner_name.lower().replace(' ', '.')}@company.com",
            team="AI Operations",
            allowed_models=allowed_models or 'All',
            reason=None,
            rotation_interval_days=30,
            last_rotated_at=now,
            next_rotation_at=next_rotation,
            expires_at=expires_at,
            status='Active'
        )
        
        db.session.add(new_key)
        db.session.commit()
        
        # Log initial creation in rotation history
        init_rotation = KeyRotationLog(
            key_id=new_key.id,
            user_id=current_user.id,
            rotation_date=now,
            previous_identifier=None,
            new_identifier='Encrypted',
            reason='Initial registration',
            status='Completed'
        )
        db.session.add(init_rotation)
        db.session.commit()
        
        log_audit(
            action='KEY_CREATED',
            resource_type='APIKey',
            resource_id=new_key.id,
            details=f"Created API key '{new_key.name}' [{new_key.provider}] for {app_name}",
            user=current_user
        )
        
        flash(f"API Key '{new_key.name}' registered successfully! Expires on {expires_at.strftime('%Y-%m-%d')}.", 'success')
        return redirect(url_for('api_keys.index'))
        
    return render_template(
        'api_keys/form.html',
        action='Create',
        applications=applications,
        providers=AVAILABLE_PROVIDERS,
        environments=ENVIRONMENTS,
        default_expiry_date=default_expiry_date,
        key=None
    )


@api_keys_bp.route('/<int:key_id>', methods=['GET'])
@login_required
def detail(key_id):
    key = APIKeyMetadata.query.get_or_404(key_id)
    rotations = key.rotations.order_by(KeyRotationLog.rotation_date.desc()).all()
    alerts = key.alerts.order_by(ExpiryAlert.triggered_at.desc()).all()
    return render_template('api_keys/detail.html', key=key, rotations=rotations, alerts=alerts)


@api_keys_bp.route('/<int:key_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(key_id):
    key = APIKeyMetadata.query.get_or_404(key_id)
    applications = Application.query.order_by(Application.name.asc()).all()
    default_expiry_date = key.expires_at.strftime('%Y-%m-%d') if key.expires_at else ''
    
    if request.method == 'POST':
        app_name = request.form.get('application_name', '').strip()
        if app_name:
            app_obj = _get_or_create_application(app_name, request.form.get('environment', key.environment))
            key.application_id = app_obj.id if app_obj else None
            
        key.environment = request.form.get('environment', key.environment).strip()
        key.provider = request.form.get('provider', key.provider).strip()
        key.name = request.form.get('name', key.name).strip()
        key.owner_name = request.form.get('owner_name', key.owner_name).strip() or key.owner_name
        key.allowed_models = request.form.get('allowed_models', key.allowed_models or 'All').strip()
        key.status = request.form.get('status', key.status)
        
        project_name = request.form.get('project_name', '').strip()
        provider_key_id = request.form.get('provider_key_id', '').strip()
        workspace_id = request.form.get('workspace_id', '').strip()
        
        key.openai_project = encrypt_value(project_name) if project_name else None
        key.provider_key_id = encrypt_value(provider_key_id) if provider_key_id else None
        key.workspace_id = encrypt_value(workspace_id) if workspace_id else None
        
        # NOTE: expires_at is NOT editable (fixed 30 days from creation)
        db.session.commit()
        
        log_audit(
            action='KEY_UPDATED',
            resource_type='APIKey',
            resource_id=key.id,
            details=f"Updated API key '{key.name}' [{key.provider}]",
            user=current_user
        )
        
        flash(f"API Key '{key.name}' updated successfully.", 'success')
        return redirect(url_for('api_keys.index'))
        
    return render_template(
        'api_keys/form.html',
        action='Edit',
        applications=applications,
        providers=AVAILABLE_PROVIDERS,
        environments=ENVIRONMENTS,
        default_expiry_date=default_expiry_date,
        key=key
    )


@api_keys_bp.route('/<int:key_id>/revoke', methods=['POST'])
@login_required
@admin_required
def revoke(key_id):
    key = APIKeyMetadata.query.get_or_404(key_id)
    key.status = 'Revoked'
    db.session.commit()
    
    log_audit(
        action='KEY_REVOKED',
        resource_type='APIKey',
        resource_id=key.id,
        details=f"Revoked API key '{key.name}' [{key.provider}]",
        user=current_user
    )
    flash(f"API Key '{key.name}' status has been marked as Revoked.", 'warning')
    return redirect(request.referrer or url_for('api_keys.index'))


@api_keys_bp.route('/<int:key_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(key_id):
    key = APIKeyMetadata.query.get_or_404(key_id)
    key_name = key.name
    db.session.delete(key)
    db.session.commit()
    
    log_audit(
        action='KEY_DELETED',
        resource_type='APIKey',
        resource_id=key_id,
        details=f"Deleted API key '{key_name}'",
        user=current_user
    )
    flash(f"API Key '{key_name}' deleted.", 'info')
    return redirect(url_for('api_keys.index'))
