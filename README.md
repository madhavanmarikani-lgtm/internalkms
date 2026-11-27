# AI Key Manager

A centralized, responsive, and secure internal **AI API Key Governance & Lifecycle Management Dashboard** built with **Python Flask**, **Bootstrap 5**, **Jinja2**, and **SQLite**.

Designed specifically for engineering, DevOps, and SecOps teams to track and govern AI model API keys across core providers (**OpenAI**, **Claude**, and **Gemini**) while strictly enforcing **zero raw secret storage**.

---

## 1. Core Security Principle: Metadata-Only Vault

> [!IMPORTANT]
> **Zero Raw Secret Retention Policy:**
> Under no circumstances does this application store or request actual full API keys.
> - Only **masked key identifiers** (e.g. `sk-proj-...8a1f`, `AIzaSy...4e9x`) are stored and displayed.
> - Real secrets remain exclusively in dedicated production vaults (e.g. HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager).
> - All backend inputs strictly sanitize raw submissions before saving.
> - Full CSRF protection is enforced across all forms and API endpoints.

---

## 2. Technology Stack

- **Backend**: Python 3.12+ / Flask 2.3+
- **Database & ORM**: SQLite (`instance/ai_key_manager.db`), Flask-SQLAlchemy
- **Authentication**: Flask-Login
- **Password Hashing**: Werkzeug (`generate_password_hash`, `check_password_hash`)
- **Database Migrations**: Flask-Migrate (Alembic)
- **CSRF Protection**: Flask-WTF
- **Frontend / Templating**: Jinja2 HTML5 templates
- **Styling**: Bootstrap 5.3 + Bootstrap Icons
- **Interactive Visualizations**: Chart.js 4.4
- **Interactions**: Vanilla JavaScript (no React/Node/external JS frameworks)

---

## 3. Application Architecture

```
ai-key-manager/
│
├── app/
│   ├── __init__.py               # Flask application factory
│   ├── models.py                 # SQLAlchemy DB models (User, APIKeyMetadata, Application, etc.)
│   ├── extensions.py             # Extension instances (db, login_manager, migrate, csrf)
│   ├── auth/
│   │   ├── routes.py             # Login, logout, session management
│   │   └── decorators.py         # @admin_required role decorator
│   ├── dashboard/
│   │   └── routes.py             # Overview KPI metrics & Chart.js distribution feeds
│   ├── api_keys/
│   │   └── routes.py             # Key metadata CRUD, filtering, masking
│   ├── applications/
│   │   └── routes.py             # Internal apps & microservices registration
│   ├── rotation/
│   │   └── routes.py             # Lifecycle rotation schedule & overdue management
│   ├── alerts/
│   │   └── routes.py             # Automated expiry warning engine (30d, 14d, 7d, expired)
│   ├── audit/
│   │   └── routes.py             # Immutable audit trail & CSV export
│   ├── admin/
│   │   └── routes.py             # User management & system governance settings
│   ├── services/
│   │   ├── expiry_service.py     # Automated expiration status scanner
│   │   ├── rotation_service.py   # Key rotation logic & masking helpers
│   │   └── audit_service.py      # Structured audit logging utility
│   ├── templates/                # Jinja2 templates (Bootstrap 5)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── api_keys/
│   │   │   ├── index.html
│   │   │   ├── form.html
│   │   │   └── detail.html
│   │   ├── applications/
│   │   │   └── index.html
│   │   ├── rotation/
│   │   │   └── index.html
│   │   ├── alerts/
│   │   │   └── index.html
│   │   ├── audit/
│   │   │   └── index.html
│   │   └── admin/
│   │       ├── users.html
│   │       └── settings.html
│   └── static/
│       ├── css/
│       │   └── custom.css        # Enterprise dashboard layout styling
│       └── js/
│           └── main.js           # Vanilla JS helpers (copy, prefixes, sidebar toggle)
│
├── instance/
│   └── ai_key_manager.db         # SQLite database
│
├── migrations/                   # Alembic database migration scripts
├── tests/
│   └── test_app.py               # Pytest automated test suite
├── config.py                     # Environment-specific configuration
├── requirements.txt              # Python package dependencies
├── run.py                        # Entrypoint server script
├── seed.py                       # Database seeding script with realistic AI keys
└── README.md
```

---

## 4. User Roles & Access Control

| Capability | Admin | Viewer |
| :--- | :---: | :---: |
| View Dashboard & Metrics | Yes | Yes |
| View Key Metadata & Details | Yes | Yes |
| View Consuming Applications | Yes | Yes |
| Monitor Expiry Alerts | Yes | Yes |
| View Rotation Status & History | Yes | Yes |
| View & Export Audit Trail | Yes | Yes |
| Register / Edit / Revoke / Delete Keys | **Yes** | No |
| Create / Edit / Delete Applications | **Yes** | No |
| Execute Key Rotation Workflow | **Yes** | No |
| Manage Users (Create, Toggle, Reset Password) | **Yes** | No |
| Configure System Settings & Alert Thresholds | **Yes** | No |

---

## 5. Quickstart & Installation

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Seed the Database
Populates initial Admin/Viewer credentials, 11 realistic AI keys, 5 applications, rotation logs, and active alerts:
```bash
python seed.py
```

### Step 3: Run the Application
```bash
python run.py
```
Open your browser and navigate to:
**http://localhost:5000**

---

## 6. Pre-Configured Demo Credentials

The login screen provides quick one-click credential buttons:

| Role | Username | Password | Access Level |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@12345` | Full administrative control & metadata CRUD |
| **Viewer** | `viewer` | `Viewer@12345` | Read-only governance & monitoring |

---

## 7. Running Automated Tests

Run the full pytest suite:
```bash
pytest -v
```
All test cases verify authentication, role authorization, masked identifier security, key rotation workflows, expiry alerts scanning, and CSV export.
