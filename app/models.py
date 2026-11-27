from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='Viewer')  # 'Admin' or 'Viewer'
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    rotations = db.relationship('KeyRotationLog', backref='rotated_by', lazy='dynamic')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def is_admin(self):
        return self.role == 'Admin'
        
    @property
    def is_active(self):
        return self.is_active_account

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    environment = db.Column(db.String(50), default='Production', nullable=False)
    owner_team = db.Column(db.String(100), nullable=False)
    contact_email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(30), default='Active', nullable=False)  # Active, Deprecated, Maintenance
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    api_keys = db.relationship('APIKeyMetadata', backref='application', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Application {self.name}>'


class APIKeyMetadata(db.Model):
    __tablename__ = 'api_key_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    provider = db.Column(db.String(60), nullable=False)  # OpenAI, Google, Claude, Kling, Seedance
    key_identifier = db.Column(db.String(60), nullable=True, default='')
    environment = db.Column(db.String(30), default='Production', nullable=False)  # Production, UAT
    
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=True)
    
    # Encrypted credential identifiers (stored encrypted via Fernet)
    openai_project = db.Column(db.Text, nullable=True)       # Encrypted Project Name / ID
    provider_key_id = db.Column(db.Text, nullable=True)      # Encrypted Key ID (OpenAI / Claude)
    workspace_id = db.Column(db.Text, nullable=True)         # Encrypted Workspace ID (Claude)
    
    allowed_models = db.Column(db.String(255), default='gpt-4o', nullable=True)
    owner_name = db.Column(db.String(100), default='Key Owner', nullable=False)
    owner_email = db.Column(db.String(120), nullable=True)
    team = db.Column(db.String(100), nullable=True)
    reason = db.Column(db.String(255), nullable=True)
    
    rate_limit_rpm = db.Column(db.Integer, nullable=True)
    rate_limit_tpm = db.Column(db.Integer, nullable=True)
    monthly_budget_limit = db.Column(db.Float, nullable=True)
    cost_center = db.Column(db.String(80), nullable=True)
    
    status = db.Column(db.String(30), default='Active', nullable=False)
    
    rotation_interval_days = db.Column(db.Integer, default=30, nullable=False)
    last_rotated_at = db.Column(db.DateTime, nullable=True)
    next_rotation_at = db.Column(db.DateTime, nullable=True)
    
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    rotations = db.relationship('KeyRotationLog', backref='key_metadata', lazy='dynamic', cascade='all, delete-orphan')
    alerts = db.relationship('ExpiryAlert', backref='key_metadata', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def decrypted_project_name(self):
        from app.services.crypto_service import decrypt_value
        return decrypt_value(self.openai_project)

    @property
    def decrypted_key_id(self):
        from app.services.crypto_service import decrypt_value
        return decrypt_value(self.provider_key_id)

    @property
    def decrypted_workspace_id(self):
        from app.services.crypto_service import decrypt_value
        return decrypt_value(self.workspace_id)

    @property
    def days_until_expiry(self):
        if not self.expires_at:
            return None
        now = datetime.now(timezone.utc)
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        delta = exp - now
        return delta.days

    @property
    def days_until_rotation(self):
        if not self.next_rotation_at:
            return None
        now = datetime.now(timezone.utc)
        rot = self.next_rotation_at if self.next_rotation_at.tzinfo else self.next_rotation_at.replace(tzinfo=timezone.utc)
        delta = rot - now
        return delta.days

    def __repr__(self):
        return f'<APIKeyMetadata {self.name} [{self.provider}]>'


class KeyRotationLog(db.Model):
    __tablename__ = 'key_rotation_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.Integer, db.ForeignKey('api_key_metadata.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    rotation_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    previous_identifier = db.Column(db.String(60), nullable=True)
    new_identifier = db.Column(db.String(60), nullable=False)
    reason = db.Column(db.String(255), default='Routine Scheduled Rotation', nullable=False)
    status = db.Column(db.String(30), default='Completed', nullable=False)  # Completed, In Progress, Scheduled, Failed
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<KeyRotationLog Key#{self.key_id} on {self.rotation_date}>'


class ExpiryAlert(db.Model):
    __tablename__ = 'expiry_alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    key_id = db.Column(db.Integer, db.ForeignKey('api_key_metadata.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # Expired, Critical, Warning, Notice
    severity = db.Column(db.String(20), default='warning', nullable=False)  # danger, warning, info
    message = db.Column(db.String(255), nullable=False)
    triggered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_acknowledged = db.Column(db.Boolean, default=False, nullable=False)
    acknowledged_by = db.Column(db.String(64), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<ExpiryAlert Key#{self.key_id} - {self.alert_type}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(60), nullable=False, index=True)  # KEY_CREATED, KEY_UPDATED, KEY_ROTATED, etc.
    resource_type = db.Column(db.String(40), nullable=False)  # APIKey, Application, User, Setting, Auth
    resource_id = db.Column(db.String(60), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.username}>'


class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(60), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @staticmethod
    def get_value(key, default=None):
        setting = SystemSetting.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set_value(key, value, description=None):
        setting = SystemSetting.query.filter_by(key=key).first()
        if not setting:
            setting = SystemSetting(key=key, value=str(value), description=description)
            db.session.add(setting)
        else:
            setting.value = str(value)
            if description:
                setting.description = description
        db.session.commit()
        return setting


class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    sent_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    key_id = db.Column(db.Integer, nullable=True)
    key_name = db.Column(db.String(120), nullable=True)
    recipients = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    trigger_type = db.Column(db.String(60), default='Alert', nullable=False)  # Critical Alert, Daily Reminder, Test Email
    status = db.Column(db.String(20), default='Sent', nullable=False)  # Sent, Failed
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<EmailLog {self.status} to {self.recipients}>'
