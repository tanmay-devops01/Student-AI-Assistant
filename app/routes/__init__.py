"""Routes package initialization."""
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.tasks import tasks_bp
from app.routes.subjects import subjects_bp
from app.routes.ai_assistant import ai_bp
from app.routes.documents import documents_bp
from app.routes.reports import reports_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'tasks_bp',
    'subjects_bp',
    'ai_bp',
    'documents_bp',
    'reports_bp'
]
