import pytest
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Application, APIKeyMetadata, KeyRotationLog, ExpiryAlert, AuditLog, SystemSetting
from app.services.expiry_service import check_and_update_expiry_statuses
from app.services.rotation_service import sanitize_and_mask_key_identifier, perform_key_rotation

@pytest.fixture
def app():
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        # Seed test admin & viewer
        admin = User(username='test_admin', email='admin@test.com', role='Admin')
        admin.set_password('AdminPass123')
        viewer = User(username='test_viewer', email='viewer@test.com', role='Viewer')
        viewer.set_password('ViewerPass123')
        db.session.add_all([admin, viewer])
        
        # Seed test app & key
        test_app = Application(
            name='Test AI App',
            owner_team='QA Team',
            contact_email='qa@test.com',
            environment='Production'
        )
        db.session.add(test_app)
        db.session.commit()
        
        test_key = APIKeyMetadata(
            name='Test OpenAI Key',
            provider='OpenAI',
            key_identifier='sk-proj-...99aa',
            environment='prod',
            openai_project='proj_test_core',
            allowed_models='gpt-4o, gpt-4o-mini',
            application_id=test_app.id,
            owner_name='Test Lead',
            owner_email='qa@test.com',
            team='QA Team',
            rotation_interval_days=90,
            last_rotated_at=datetime.now(timezone.utc),
            next_rotation_at=datetime.now(timezone.utc) + timedelta(days=90),
            expires_at=datetime.now(timezone.utc) + timedelta(days=5), # within critical 7d threshold
            status='Active'
        )
        db.session.add(test_key)
        db.session.commit()
        
    yield app
    
    with app.app_context():
        db.session.remove()
        db.drop_all()

@pytest.fixture
def test_client(app):
    return app.test_client()

def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

def logout(client):
    return client.get('/logout', follow_redirects=True)

def test_login_success(test_client):
    res = login(test_client, 'test_admin', 'AdminPass123')
    assert res.status_code == 200
    assert b'AI Key Dashboard' in res.data
    assert b'test_admin' in res.data

def test_login_invalid_password(test_client):
    res = login(test_client, 'test_admin', 'WrongPassword!')
    assert res.status_code == 200
    assert b'Invalid username or password' in res.data

def test_unauthenticated_redirect(test_client):
    res = test_client.get('/dashboard', follow_redirects=False)
    assert res.status_code == 302
    assert '/login' in res.headers['Location']

def test_role_authorization_viewer_blocked_from_admin_pages(test_client):
    login(test_client, 'test_viewer', 'ViewerPass123')
    
    # Try accessing admin users
    res = test_client.get('/admin/users', follow_redirects=True)
    assert res.status_code == 200
    assert b'Admin access is required' in res.data
    
    # Try accessing settings
    res = test_client.get('/admin/settings', follow_redirects=True)
    assert res.status_code == 200
    assert b'Admin access is required' in res.data

    # Try accessing key rotation (removed from viewer)
    res = test_client.get('/rotation', follow_redirects=True)
    assert res.status_code == 200
    assert b'Admin access is required' in res.data

    # Viewer sees Get Daily Report and NO Key Rotation
    dash = test_client.get('/dashboard')
    assert b'Get Daily Report' in dash.data
    assert b'--&gt;' in dash.data or b'-->' in dash.data
    assert b'Key Rotation' not in dash.data

    detail = test_client.get('/api-keys/1')
    assert b'Rotation History' not in detail.data
    assert b'Record Rotation' not in detail.data

    # Viewer blocked from Database and Email Monitoring tabs
    db_res = test_client.get('/admin/database', follow_redirects=True)
    assert b'Admin access is required' in db_res.data
    em_res = test_client.get('/admin/email-monitoring', follow_redirects=True)
    assert b'Admin access is required' in em_res.data

def test_role_authorization_admin_allowed(test_client):
    login(test_client, 'test_admin', 'AdminPass123')
    
    res = test_client.get('/admin/users')
    assert res.status_code == 200
    assert b'User Management' in res.data
    
    res = test_client.get('/admin/settings')
    assert res.status_code == 200
    assert b'System Governance Settings' in res.data

    res = test_client.get('/admin/database')
    assert res.status_code == 200
    assert b'Database Access Protected' in res.data

    # Wrong password rejected
    bad_unlock = test_client.post('/admin/database/unlock', data={'db_password': 'WrongPassword'}, follow_redirects=True)
    assert b'Incorrect database password' in bad_unlock.data

    # Unlock with valid database password
    unlock_res = test_client.post('/admin/database/unlock', data={'db_password': 'DbAdmin@2026'}, follow_redirects=True)
    assert unlock_res.status_code == 200
    assert b'Database Explorer' in unlock_res.data
    assert b'api_key_metadata' in unlock_res.data

    # Test edit row in database
    edit_res = test_client.post('/admin/database/edit', data={
        'table': 'api_key_metadata',
        'pk_col': 'id',
        'pk_val': '1',
        'col_owner_name': 'Updated DB Owner'
    }, follow_redirects=True)
    assert edit_res.status_code == 200
    assert b'Updated DB Owner' in edit_res.data

    # Test delete row in database
    del_res = test_client.post('/admin/database/delete', data={
        'table': 'api_key_metadata',
        'pk_col': 'id',
        'pk_val': '1'
    }, follow_redirects=True)
    assert del_res.status_code == 200
    assert b'deleted from' in del_res.data

def test_masking_security_never_stores_raw_keys(test_client):
    raw_key = "sk-proj-1234567890abcdef1234567890abcdef1234"
    masked = sanitize_and_mask_key_identifier(raw_key, 'OpenAI')
    assert "..." in masked
    assert masked == "sk-proj...1234"
    assert raw_key not in masked

def test_api_key_creation_admin(test_client, app):
    login(test_client, 'test_admin', 'AdminPass123')
    
    data = {
        'application_name': 'New Input App',
        'environment': 'UAT',
        'provider': 'Claude',
        'provider_key_id': 'key_ant_secret_99',
        'workspace_id': 'wrkspc_secret_01',
        'name': 'New Claude Key',
        'owner_name': 'Siddharth Verma',
        'allowed_models': 'claude-3-5-sonnet'
    }
    res = test_client.post('/api-keys/new', data=data, follow_redirects=True)
    assert res.status_code == 200
    assert b'New Claude Key' in res.data
    assert b'key_ant_secret_99' in res.data
    assert b'wrkspc_secret_01' in res.data
    
    with app.app_context():
        created = APIKeyMetadata.query.filter_by(name='New Claude Key').first()
        assert created is not None
        assert created.provider_key_id.startswith('gAAAAA')
        assert created.workspace_id.startswith('gAAAAA')
        assert created.decrypted_key_id == 'key_ant_secret_99'
        assert created.decrypted_workspace_id == 'wrkspc_secret_01'

def test_key_rotation_flow(test_client, app):
    login(test_client, 'test_admin', 'AdminPass123')
    
    # Rotate key #1
    rot_data = {
        'new_key_identifier': 'key_new_instant_8888',
        'reason': 'Instant test rotation',
        'notes': 'Verified immediately'
    }
    res = test_client.post('/rotation/1/rotate', data=rot_data, follow_redirects=True)
    assert res.status_code == 200
    assert b'rotated immediately' in res.data
    
    # Verify in DB within app context
    with app.app_context():
        key = db.session.get(APIKeyMetadata, 1)
        assert key.decrypted_key_id == 'key_new_instant_8888'
        assert key.provider_key_id.startswith('gAAAAA')
        assert key.next_rotation_at is None
        assert key.status == 'Active'
        assert key.days_until_expiry >= 29
        assert key.rotations.count() >= 1

def test_expiry_alerts_scan(test_client, app):
    # Key #1 has expires_at in 5 days, critical threshold is 7 days
    with app.app_context():
        result = check_and_update_expiry_statuses()
        assert result['new_alerts'] >= 1
        
        key = db.session.get(APIKeyMetadata, 1)
        assert key.status == 'Expiring Soon'
    
    # Check alert page via test client
    login(test_client, 'test_viewer', 'ViewerPass123')
    res = test_client.get('/alerts')
    assert res.status_code == 200
    assert b'Critical' in res.data

def test_audit_logs_and_csv_export(test_client):
    login(test_client, 'test_admin', 'AdminPass123')
    
    res = test_client.get('/audit')
    assert res.status_code == 200
    assert b'Audit Logs' in res.data

    # Verify all other redesigned pages return 200 OK
    for path in ['/dashboard', '/api-keys', '/api-keys/new', '/applications', '/rotation', '/alerts', '/admin/database', '/admin/settings', '/admin/email-monitoring']:
        page_res = test_client.get(path)
        assert page_res.status_code == 200, f"Failed on {path}"
    
    # CSV export
    csv_res = test_client.get('/audit/export')
    assert csv_res.status_code == 200
    assert csv_res.mimetype == 'text/csv'
    assert b'Timestamp (UTC)' in csv_res.data

    # Date-range filter on audit logs
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    filtered = test_client.get(f'/audit?date_from={today_str}&date_to={today_str}')
    assert filtered.status_code == 200
    assert b'USER_LOGIN' in filtered.data


def test_change_password_and_smtp_alert(test_client, app, monkeypatch):
    login(test_client, 'test_viewer', 'ViewerPass123')

    # Change password
    pw_res = test_client.post('/change-password', data={
        'current_password': 'ViewerPass123',
        'new_password': 'NewViewerPass99',
        'confirm_password': 'NewViewerPass99'
    }, follow_redirects=True)
    assert pw_res.status_code == 200
    assert b'password has been updated' in pw_res.data

    # Test SMTP email sending using .env / app.config with mocked SMTP
    sent_messages = []

    class DummySMTP:
        def __init__(self, host, port, timeout=15):
            self.host = host
            self.port = port
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def starttls(self):
            pass
        def login(self, user, password):
            assert user == 'alerts@test.com'
            assert password == 'secret-pw'
        def sendmail(self, from_addr, to_addrs, msg):
            sent_messages.append((from_addr, to_addrs, msg))

    import smtplib
    monkeypatch.setattr(smtplib, 'SMTP', DummySMTP)

    app.config['SMTP_HOST'] = 'smtp.test.com'
    app.config['SMTP_PORT'] = 587
    app.config['SMTP_USE_TLS'] = True
    app.config['SMTP_USER'] = 'alerts@test.com'
    app.config['SMTP_PASSWORD'] = 'secret-pw'
    app.config['SMTP_FROM_EMAIL'] = 'alerts@test.com'
    app.config['ALERT_RECIPIENT_EMAILS'] = 'ops@test.com'

    with app.app_context():
        ExpiryAlert.query.delete()
        db.session.commit()
        result = check_and_update_expiry_statuses()
        assert result['new_alerts'] >= 1
        assert len(sent_messages) == 1
        assert 'Test OpenAI Key' in sent_messages[0][2]

        # Test daily 10:30 AM IST reminder routine (sends once per IST day)
        from app.services.expiry_service import send_daily_expiry_reminders
        sent_messages.clear()
        count1 = send_daily_expiry_reminders()
        assert count1 == 1
        assert len(sent_messages) == 1
        # Calling again on the same IST day should not duplicate
        count2 = send_daily_expiry_reminders()
        assert count2 == 0
        assert len(sent_messages) == 1
