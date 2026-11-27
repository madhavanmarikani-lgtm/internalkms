import os
from datetime import datetime, timezone, timedelta
from app import create_app
from app.extensions import db
from app.models import User, Application, APIKeyMetadata, KeyRotationLog, ExpiryAlert, AuditLog, SystemSetting
from app.services.expiry_service import check_and_update_expiry_statuses
from app.services.crypto_service import encrypt_value

def run_seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        
        # 1. Seed Users
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@internal.enterprise.com',
                role='Admin',
                is_active_account=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=60)
            )
            admin_user.set_password('Admin@12345')
            db.session.add(admin_user)
        else:
            admin_user = User.query.filter_by(username='admin').first()
            admin_user.set_password('Admin@12345')
            
        if not User.query.filter_by(username='viewer').first():
            viewer_user = User(
                username='viewer',
                email='viewer@internal.enterprise.com',
                role='Viewer',
                is_active_account=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=45)
            )
            viewer_user.set_password('Viewer@12345')
            db.session.add(viewer_user)
        else:
            viewer_user = User.query.filter_by(username='viewer').first()
            viewer_user.set_password('Viewer@12345')

        db.session.commit()

        # 2. Seed Applications
        app_support = Application.query.filter_by(name="Customer Support Copilot").first()
        if not app_support:
            apps = [
                Application(name="Customer Support Copilot", environment="Production", owner_team="Support Eng", contact_email=""),
                Application(name="Document Intelligence", environment="Production", owner_team="NLP Ops", contact_email=""),
                Application(name="Code Review Assistant", environment="UAT", owner_team="SecOps", contact_email=""),
                Application(name="Creative Video Studio", environment="Production", owner_team="Media AI", contact_email=""),
                Application(name="Enterprise Search RAG", environment="UAT", owner_team="Search", contact_email=""),
            ]
            db.session.add_all(apps)
            db.session.commit()

        app1 = Application.query.filter_by(name="Customer Support Copilot").first()
        app2 = Application.query.filter_by(name="Document Intelligence").first()
        app3 = Application.query.filter_by(name="Code Review Assistant").first()
        app4 = Application.query.filter_by(name="Creative Video Studio").first()
        app5 = Application.query.filter_by(name="Enterprise Search RAG").first()

        now = datetime.now(timezone.utc)

        # 3. Clean out existing keys to re-populate with encrypted identifiers
        ExpiryAlert.query.delete()
        KeyRotationLog.query.delete()
        APIKeyMetadata.query.delete()
        db.session.commit()

        keys_data = [
            # 1. OpenAI (Project Name + Key ID)
            {
                "name": "Support GPT-4o Primary",
                "provider": "OpenAI",
                "environment": "Production",
                "application_id": app1.id if app1 else None,
                "openai_project": encrypt_value("proj_support_prod"),
                "provider_key_id": encrypt_value("key_oa_01928374"),
                "workspace_id": None,
                "owner_name": "Arun Kumar",
                "owner_email": "arun@company.com",
                "team": "Support",
                "allowed_models": "gpt-4o, gpt-4o-mini",
                "reason": "Primary customer support triage deployment",
                "created_at": now - timedelta(days=5),
                "last_rotated_at": now - timedelta(days=5),
                "expires_at": now + timedelta(days=25),
                "status": "Active"
            },
            {
                "name": "Search RAG OpenAI Key",
                "provider": "OpenAI",
                "environment": "UAT",
                "application_id": app5.id if app5 else None,
                "openai_project": encrypt_value("proj_search_uat"),
                "provider_key_id": encrypt_value("key_oa_88776655"),
                "workspace_id": None,
                "owner_name": "Karthik Subramanian",
                "owner_email": "karthik@company.com",
                "team": "Search",
                "allowed_models": "text-embedding-3-large, gpt-4o",
                "reason": "UAT vector indexing test run",
                "created_at": now - timedelta(days=25),
                "last_rotated_at": now - timedelta(days=25),
                "expires_at": now + timedelta(days=5),  # 7-day Alert!
                "status": "Expiring Soon"
            },

            # 2. Google (Project Name)
            {
                "name": "Gemini 1.5 Pro Embeddings",
                "provider": "Google",
                "environment": "Production",
                "application_id": app5.id if app5 else None,
                "openai_project": encrypt_value("gcp-gemini-search-prod"),
                "provider_key_id": None,
                "workspace_id": None,
                "owner_name": "Karthik Subramanian",
                "owner_email": "karthik@company.com",
                "team": "Search",
                "allowed_models": "gemini-1.5-pro, text-embedding-004",
                "reason": "Multimodal indexing pipeline",
                "created_at": now - timedelta(days=27),
                "last_rotated_at": now - timedelta(days=27),
                "expires_at": now + timedelta(days=3),  # 7-day Alert!
                "status": "Expiring Soon"
            },
            {
                "name": "Document Parsing Flash",
                "provider": "Google",
                "environment": "Production",
                "application_id": app2.id if app2 else None,
                "openai_project": encrypt_value("gcp-doc-intel-prod"),
                "provider_key_id": None,
                "workspace_id": None,
                "owner_name": "Siddharth Verma",
                "owner_email": "siddharth@company.com",
                "team": "NLP",
                "allowed_models": "gemini-1.5-flash",
                "reason": "High-speed PDF extraction service",
                "created_at": now - timedelta(days=10),
                "last_rotated_at": now - timedelta(days=10),
                "expires_at": now + timedelta(days=20),
                "status": "Active"
            },

            # 3. Claude (Key ID + Workspace ID)
            {
                "name": "Doc Intelligence Claude Sonnet",
                "provider": "Claude",
                "environment": "Production",
                "application_id": app2.id if app2 else None,
                "openai_project": None,
                "provider_key_id": encrypt_value("key_ant_99112233"),
                "workspace_id": encrypt_value("wrkspc_nlp_prod_01"),
                "owner_name": "Siddharth Verma",
                "owner_email": "siddharth@company.com",
                "team": "NLP",
                "allowed_models": "claude-3-5-sonnet, claude-3-5-haiku",
                "reason": "Long-context contract summarization",
                "created_at": now - timedelta(days=26),
                "last_rotated_at": now - timedelta(days=26),
                "expires_at": now + timedelta(days=4),  # 7-day Alert!
                "status": "Expiring Soon"
            },
            {
                "name": "Code Review Security Bot",
                "provider": "Claude",
                "environment": "UAT",
                "application_id": app3.id if app3 else None,
                "openai_project": None,
                "provider_key_id": encrypt_value("key_ant_44556677"),
                "workspace_id": encrypt_value("wrkspc_secops_uat_02"),
                "owner_name": "Deepa Sundaram",
                "owner_email": "deepa@company.com",
                "team": "SecOps",
                "allowed_models": "claude-3-5-sonnet",
                "reason": "Automated PR security scanner",
                "created_at": now - timedelta(days=12),
                "last_rotated_at": now - timedelta(days=12),
                "expires_at": now + timedelta(days=18),
                "status": "Active"
            },

            # 4. Kling & 5. Seedance
            {
                "name": "Kling Video Generation Prod",
                "provider": "Kling",
                "environment": "Production",
                "application_id": app4.id if app4 else None,
                "openai_project": encrypt_value("proj_kling_media_prod"),
                "provider_key_id": None,
                "workspace_id": None,
                "owner_name": "Priya Ramesh",
                "owner_email": "priya@company.com",
                "team": "Media AI",
                "allowed_models": "kling-v1.6-pro",
                "reason": "Marketing video generation workflow",
                "created_at": now - timedelta(days=8),
                "last_rotated_at": now - timedelta(days=8),
                "expires_at": now + timedelta(days=22),
                "status": "Active"
            },
            {
                "name": "Seedance Motion Synthesis UAT",
                "provider": "Seedance",
                "environment": "UAT",
                "application_id": app4.id if app4 else None,
                "openai_project": encrypt_value("proj_seedance_uat"),
                "provider_key_id": None,
                "workspace_id": None,
                "owner_name": "Ananya Joshi",
                "owner_email": "ananya@company.com",
                "team": "Media AI",
                "allowed_models": "seedance-1.0-pro",
                "reason": "UAT testing for video motion pipeline",
                "created_at": now - timedelta(days=32),
                "last_rotated_at": now - timedelta(days=32),
                "expires_at": now - timedelta(days=2),
                "status": "Expired"
            }
        ]

        for kd in keys_data:
            k = APIKeyMetadata(**kd)
            db.session.add(k)
            db.session.flush()

            rot = KeyRotationLog(
                key_id=k.id,
                user_id=admin_user.id,
                rotation_date=k.last_rotated_at or now,
                previous_identifier=None,
                new_identifier='Encrypted',
                reason=k.reason or "Initial registration",
                status="Completed",
                notes="Encrypted identifiers stored"
            )
            db.session.add(rot)

        db.session.commit()
        print(f"Seeded {len(keys_data)} keys with encrypted IDs across OpenAI, Google, Claude, Kling, Seedance.")

        # 4. Run Expiry Scan
        res = check_and_update_expiry_statuses()
        print(f"Expiry scan: {res}")

if __name__ == '__main__':
    run_seed()
    print("Database seeding completed successfully!")
