import os
from flask import Flask
from config import config_by_name
from app.extensions import db, login_manager, migrate, csrf

def create_app(config_name=None):
    if not config_name:
        config_name = os.environ.get('FLASK_CONFIG', 'default')
        
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass
        
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    # Register blueprints
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.api_keys.routes import api_keys_bp
    from app.applications.routes import applications_bp
    from app.rotation.routes import rotation_bp
    from app.alerts.routes import alerts_bp
    from app.audit.routes import audit_bp
    from app.admin.routes import admin_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_keys_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(rotation_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(admin_bp)

    # Start daily 10:30 AM IST reminder scheduler
    from app.services.scheduler_service import init_scheduler
    init_scheduler(app)
    
    # Context processor to inject system name, unread alert count, and daily report keys
    @app.context_processor
    def inject_global_data():
        from app.models import SystemSetting, ExpiryAlert, APIKeyMetadata
        from flask_login import current_user
        app_name = SystemSetting.get_value('app_title', 'AI Key Manager')
        unack_alerts = 0
        daily_report_keys = []
        if current_user and current_user.is_authenticated:
            try:
                unack_alerts = ExpiryAlert.query.filter_by(is_acknowledged=False).count()
                daily_report_keys = APIKeyMetadata.query.order_by(APIKeyMetadata.updated_at.desc()).all()
            except Exception:
                unack_alerts = 0
                daily_report_keys = []
        return dict(
            global_app_title=app_name,
            global_unack_alerts=unack_alerts,
            global_daily_report_keys=daily_report_keys
        )
        
    return app
