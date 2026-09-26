"""
Student AI Assistant Application
A comprehensive web application for students to manage assignments, tasks, subjects,
and deadlines with AI-powered assistance.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
scheduler = BackgroundScheduler()


def create_app(config_override=None):
    """Application factory pattern for Flask."""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///student_assistant.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(Path(__file__).parent.parent, 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload
    app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
    app.config['DEBUG'] = os.environ.get('DEBUG', 'false').lower() == 'true'

    # Apply any config overrides (useful for testing)
    if config_override:
        app.config.update(config_override)

    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.tasks import tasks_bp
    from app.routes.subjects import subjects_bp
    from app.routes.ai_assistant import ai_bp
    from app.routes.documents import documents_bp
    from app.routes.reports import reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(reports_bp)

    # Register error handlers
    register_error_handlers(app)

    # Initialize scheduler and start background jobs
    init_scheduler(app)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app


def register_error_handlers(app):
    """Register custom error handlers."""
    @app.errorhandler(404)
    def not_found_error(error):
        return (
            '<!DOCTYPE html><html><head><title>404 Not Found</title></head>'
            '<body style="text-align:center;padding:50px;font-family:Arial">'
            '<h1>404 - Page Not Found</h1>'
            '<p>The page you are looking for does not exist.</p>'
            '<a href="/">Return to Dashboard</a>'
            '</body></html>'
        ), 404

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template('errors/csrf.html'), 400

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return (
            '<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head>'
            '<body style="text-align:center;padding:50px;font-family:Arial">'
            '<h1>500 - Internal Server Error</h1>'
            '<p>Something went wrong. Please try again later.</p>'
            '<a href="/">Return to Dashboard</a>'
            '</body></html>'
        ), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        from flask import flash, redirect, url_for
        flash('File too large. Maximum size is 10MB.', 'error')
        return redirect(url_for('documents.upload'))


def init_scheduler(app):
    """Initialize background scheduler for reminders and summaries."""
    from flask import current_app

    if not scheduler.running:
        # Schedule reminder check every 30 minutes
        def reminder_job():
            with app.app_context():
                from app.services.reminder_service import ReminderService
                try:
                    ReminderService.check_and_send_reminders()
                except Exception as e:
                    app.logger.error(f"Error in reminder check: {str(e)}")

        scheduler.add_job(
            func=reminder_job,
            trigger=IntervalTrigger(minutes=30),
            id='reminder_check',
            name='Check and send reminders',
            replace_existing=True,
            misfire_grace_time=60
        )

        # Schedule daily summary at 9:00 AM
        def daily_summary_job():
            with app.app_context():
                from app.services.summary_service import SummaryService
                try:
                    SummaryService.send_daily_summaries()
                except Exception as e:
                    app.logger.error(f"Error in daily summary: {str(e)}")

        scheduler.add_job(
            func=daily_summary_job,
            trigger='cron',
            hour=9,
            minute=0,
            id='daily_summary',
            name='Send daily study summary',
            replace_existing=True,
            misfire_grace_time=300
        )

        # Schedule weekly report on Monday at 8:00 AM
        def weekly_report_job():
            with app.app_context():
                from app.services.summary_service import SummaryService
                try:
                    SummaryService.send_weekly_reports()
                except Exception as e:
                    app.logger.error(f"Error in weekly report: {str(e)}")

        scheduler.add_job(
            func=weekly_report_job,
            trigger='cron',
            day_of_week='mon',
            hour=8,
            minute=0,
            id='weekly_report',
            name='Send weekly progress report',
            replace_existing=True,
            misfire_grace_time=300
        )

        scheduler.start()


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models.user import User
    return db.session.get(User, int(user_id))


# Create the application instance
app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
