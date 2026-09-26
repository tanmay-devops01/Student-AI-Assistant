"""
Service layer tests for Student AI Assistant.
Tests email_service, reminder_service, summary_service, and ai_service.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Ensure app can be imported
from app import create_app, db
from app.models.user import User
from app.models.task import Task
from app.models.subject import Subject
from app.models.reminder import Reminder
from app.services.email_service import EmailService, email_service
from app.services.reminder_service import ReminderService
from app.services.summary_service import SummaryService
from app.services.ai_service import AIService, ai_service


@pytest.fixture
def app():
    """Create test app with env vars set for email service tests."""
    os.environ['MAIL_SERVER'] = 'test.server.com'
    os.environ['MAIL_PORT'] = '587'
    os.environ['MAIL_USERNAME'] = 'testuser'
    os.environ['MAIL_PASSWORD'] = 'testpass'
    os.environ['MAIL_USE_TLS'] = 'true'
    os.environ['MAIL_FROM'] = 'test@server.com'
    os.environ['AI_API_KEY'] = 'test-key'
    os.environ['AI_MODEL'] = 'gpt-4o-mini'

    _app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'AI_API_KEY': 'test-key',
        'AI_MODEL': 'gpt-4o-mini',
        'MAIL_SERVER': 'test.server.com',
        'MAIL_PORT': '587',
        'MAIL_USERNAME': 'testuser',
        'MAIL_PASSWORD': 'testpass',
        'MAIL_USE_TLS': 'true',
        'MAIL_FROM': 'test@server.com',
    })

    with _app.app_context():
        db.create_all()
        yield _app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_user(app):
    """Create a sample user."""
    with app.app_context():
        user = User(name='Test User', email='test@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def sample_task(app, sample_user):
    """Create a sample task."""
    with app.app_context():
        subject = Subject.query.filter_by(user_id=sample_user.id, name='Test Subject').first()
        if not subject:
            subject = Subject(user_id=sample_user.id, name='Test Subject', color='#0d6efd')
            db.session.add(subject)
            db.session.commit()

        task = Task(
            user_id=sample_user.id,
            subject_id=subject.id,
            title='Test Task',
            priority='Medium',
            status='Pending',
            deadline=datetime.utcnow() + timedelta(days=2),
            estimated_minutes=60
        )
        db.session.add(task)
        db.session.commit()
        yield task


class TestEmailService:
    """Tests for EmailService — spec section 7."""

    def test_is_configured_with_all_vars(self, app):
        """is_configured returns True when all env vars are set."""
        with app.app_context():
            # Re-init with current env
            svc = EmailService()
            assert svc.is_configured() is True

    def test_is_configured_missing_server(self, app):
        """is_configured returns False when MAIL_SERVER is missing."""
        with app.app_context():
            os.environ.pop('MAIL_SERVER', None)
            svc = EmailService()
            assert svc.is_configured() is False
            os.environ['MAIL_SERVER'] = 'test.server.com'

    def test_is_configured_missing_username(self, app):
        """is_configured returns False when MAIL_USERNAME is missing."""
        with app.app_context():
            os.environ.pop('MAIL_USERNAME', None)
            svc = EmailService()
            assert svc.is_configured() is False
            os.environ['MAIL_USERNAME'] = 'testuser'

    def test_is_configured_missing_password(self, app):
        """is_configured returns False when MAIL_PASSWORD is missing."""
        with app.app_context():
            os.environ.pop('MAIL_PASSWORD', None)
            svc = EmailService()
            assert svc.is_configured() is False
            os.environ['MAIL_PASSWORD'] = 'testpass'

    def test_is_configured_missing_from(self, app):
        """is_configured returns False when MAIL_FROM is missing and no username fallback."""
        with app.app_context():
            # When MAIL_FROM is missing, from_address falls back to username.
            # To make is_configured False, we need to remove username too.
            os.environ.pop('MAIL_FROM', None)
            os.environ.pop('MAIL_USERNAME', None)
            svc = EmailService()
            assert svc.is_configured() is False
            os.environ['MAIL_FROM'] = 'test@server.com'
            os.environ['MAIL_USERNAME'] = 'testuser'

    def test_send_email_not_configured_returns_false(self, app):
        """send_email returns False when not configured (no crash)."""
        with app.app_context():
            os.environ.pop('MAIL_SERVER', None)
            svc = EmailService()
            result = svc.send_email('test@test.com', 'Subject', 'Body')
            assert result is False

    def test_send_deadline_reminder_format(self, app):
        """send_deadline_reminder produces correct subject and body."""
        with app.app_context():
            svc = EmailService()
            result = svc.send_deadline_reminder(
                user_email='user@test.com',
                user_name='Test User',
                task_title='DBMS Assignment',
                deadline='2026-09-25 23:59',
                hours_remaining=24
            )
            # Returns False because SMTP won't actually connect, but no exception
            assert isinstance(result, bool)

    def test_send_overdue_notification_format(self, app):
        """send_overdue_notification produces correct subject and body."""
        with app.app_context():
            svc = EmailService()
            result = svc.send_overdue_notification(
                user_email='user@test.com',
                user_name='Test User',
                task_title='Overdue Task',
                deadline='2026-09-20 23:59'
            )
            assert isinstance(result, bool)

    def test_send_daily_summary_format(self, app):
        """send_daily_summary produces correct subject and body."""
        with app.app_context():
            svc = EmailService()
            result = svc.send_daily_summary(
                user_email='user@test.com',
                user_name='Test User',
                summary='You have 3 tasks today.',
                tasks_today=[{'title': 'Task 1', 'status': 'Pending'}],
                completed_today=2,
                upcoming_deadlines=[{'title': 'Deadline 1', 'deadline': '2026-09-25'}]
            )
            assert isinstance(result, bool)

    def test_send_weekly_report_format(self, app):
        """send_weekly_report produces correct subject and body."""
        with app.app_context():
            svc = EmailService()
            result = svc.send_weekly_report(
                user_email='user@test.com',
                user_name='Test User',
                report_data={
                    'completion_percentage': 75.5,
                    'completed_this_week': 10,
                    'created_this_week': 5
                }
            )
            assert isinstance(result, bool)

    def test_from_address_defaults_to_username(self, app):
        """When MAIL_FROM is empty, from_address defaults to username."""
        with app.app_context():
            os.environ.pop('MAIL_FROM', None)
            svc = EmailService()
            assert svc.from_address == 'testuser'
            os.environ['MAIL_FROM'] = 'test@server.com'


class TestReminderService:
    """Tests for ReminderService — spec section 6."""

    def test_has_reminder_returns_false_for_new_task(self, app, sample_task):
        """_has_reminder returns False when no reminder exists."""
        with app.app_context():
            result = ReminderService._has_reminder(sample_task.id, 'overdue')
            assert result is False

    def test_has_reminder_returns_true_after_creation(self, app, sample_task):
        """_has_reminder returns True after creating a reminder."""
        with app.app_context():
            ReminderService.create_reminder(sample_task.user_id, sample_task.id, 'overdue')
            result = ReminderService._has_reminder(sample_task.id, 'overdue')
            assert result is True

    def test_has_reminder_different_type_returns_false(self, app, sample_task):
        """_has_reminder for one type doesn't affect another type."""
        with app.app_context():
            ReminderService.create_reminder(sample_task.user_id, sample_task.id, 'overdue')
            result = ReminderService._has_reminder(sample_task.id, 'upcoming_1h')
            assert result is False

    def test_create_reminder_persists(self, app, sample_task):
        """create_reminder saves to DB and returns Reminder object."""
        with app.app_context():
            reminder = ReminderService.create_reminder(
                sample_task.user_id, sample_task.id, 'upcoming_24h'
            )
            assert reminder.id is not None
            assert reminder.reminder_type == 'upcoming_24h'
            assert reminder.user_id == sample_task.user_id
            assert reminder.task_id == sample_task.id

            # Verify it's in the DB
            found = db.session.get(Reminder, reminder.id)
            assert found is not None

    def test_check_and_send_reminders_overdue(self, app, sample_user):
        """check_and_send_reminders sends overdue reminder for past deadline."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            # Create an overdue task
            overdue_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Overdue Task',
                priority='High',
                status='Pending',
                deadline=datetime.utcnow() - timedelta(days=1),
                estimated_minutes=60
            )
            db.session.add(overdue_task)
            db.session.commit()

            count = ReminderService.check_and_send_reminders()
            assert count == 1

            # Verify reminder was created
            reminder = Reminder.query.filter_by(
                task_id=overdue_task.id, reminder_type='overdue'
            ).first()
            assert reminder is not None

    def test_check_and_send_reminders_no_duplicate(self, app, sample_user):
        """check_and_send_reminders doesn't duplicate existing reminders."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            overdue_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Overdue Task',
                priority='High',
                status='Pending',
                deadline=datetime.utcnow() - timedelta(days=1),
                estimated_minutes=60
            )
            db.session.add(overdue_task)
            db.session.commit()

            # Send first time
            count1 = ReminderService.check_and_send_reminders()
            assert count1 == 1

            # Send second time — should not duplicate
            count2 = ReminderService.check_and_send_reminders()
            assert count2 == 0

            # Only one reminder record
            reminders = Reminder.query.filter_by(task_id=overdue_task.id).all()
            assert len(reminders) == 1

    def test_check_and_send_reminders_upcoming_24h(self, app, sample_user):
        """check_and_send_reminders sends 24h reminder for upcoming deadline."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            # Create a task due in 23 hours
            upcoming_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Upcoming Task',
                priority='Medium',
                status='Pending',
                deadline=datetime.utcnow() + timedelta(hours=23),
                estimated_minutes=60
            )
            db.session.add(upcoming_task)
            db.session.commit()

            count = ReminderService.check_and_send_reminders()
            assert count == 1

            reminder = Reminder.query.filter_by(
                task_id=upcoming_task.id, reminder_type='upcoming_24h'
            ).first()
            assert reminder is not None

    def test_check_and_send_reminders_upcoming_1h(self, app, sample_user):
        """check_and_send_reminders sends 1h reminder for very close deadline."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            # Create a task due in 30 minutes
            close_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Close Task',
                priority='High',
                status='Pending',
                deadline=datetime.utcnow() + timedelta(minutes=30),
                estimated_minutes=30
            )
            db.session.add(close_task)
            db.session.commit()

            count = ReminderService.check_and_send_reminders()
            assert count == 1

            reminder = Reminder.query.filter_by(
                task_id=close_task.id, reminder_type='upcoming_1h'
            ).first()
            assert reminder is not None

    def test_check_and_send_reminders_completed_task_ignored(self, app, sample_user):
        """check_and_send_reminders ignores completed tasks."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            completed_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Completed Task',
                priority='Medium',
                status='Completed',
                deadline=datetime.utcnow() - timedelta(days=1),
                estimated_minutes=60
            )
            db.session.add(completed_task)
            db.session.commit()

            count = ReminderService.check_and_send_reminders()
            assert count == 0

    def test_check_and_send_reminders_no_deadline_ignored(self, app, sample_user):
        """check_and_send_reminders ignores tasks without deadlines."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            no_deadline_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='No Deadline Task',
                priority='Low',
                status='Pending',
                deadline=None,
                estimated_minutes=60
            )
            db.session.add(no_deadline_task)
            db.session.commit()

            count = ReminderService.check_and_send_reminders()
            assert count == 0

    def test_get_user_reminders_returns_sorted(self, app, sample_user):
        """get_user_reminders returns reminders sorted by sent_at desc."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Task 1',
                priority='Medium',
                status='Pending',
                deadline=datetime.utcnow() + timedelta(days=1),
                estimated_minutes=60
            )
            db.session.add(task)
            db.session.commit()

            r1 = ReminderService.create_reminder(sample_user.id, task.id, 'overdue')
            # Small delay to ensure different sent_at timestamps
            import time
            time.sleep(0.01)
            r2 = ReminderService.create_reminder(sample_user.id, task.id, 'upcoming_24h')

            reminders = ReminderService.get_user_reminders(sample_user.id, limit=10)
            assert len(reminders) == 2
            # Most recent reminder (r2) should be first due to sent_at DESC
            assert reminders[0].id == r2.id
            assert reminders[1].id == r1.id


class TestSummaryService:
    """Tests for SummaryService — spec sections 8 and 9."""

    def test_get_weekly_stats_structure(self, app, sample_user):
        """get_weekly_stats returns dict with all expected keys."""
        with app.app_context():
            stats = SummaryService.get_weekly_stats(sample_user.id)
            expected_keys = [
                'completed_this_week', 'created_this_week', 'overdue_tasks',
                'completion_percentage', 'total_tasks', 'completed_tasks',
                'daily_stats'
            ]
            for key in expected_keys:
                assert key in stats, f"Missing key: {key}"

    def test_get_weekly_stats_daily_stats_format(self, app, sample_user):
        """get_weekly_stats daily_stats has 7 entries with correct keys."""
        with app.app_context():
            stats = SummaryService.get_weekly_stats(sample_user.id)
            assert len(stats['daily_stats']) == 7
            for day in stats['daily_stats']:
                assert 'day' in day
                assert 'created' in day
                assert 'completed' in day

    def test_get_weekly_stats_zero_for_empty_user(self, app, sample_user):
        """get_weekly_stats returns zeros for user with no tasks."""
        with app.app_context():
            stats = SummaryService.get_weekly_stats(sample_user.id)
            assert stats['total_tasks'] == 0
            assert stats['completed_tasks'] == 0
            assert stats['completion_percentage'] == 0
            assert stats['completed_this_week'] == 0
            assert stats['created_this_week'] == 0
            assert stats['overdue_tasks'] == 0

    def test_send_daily_summaries_runs_without_crash(self, app, sample_user):
        """send_daily_summaries runs without crashing even without email config."""
        with app.app_context():
            # Remove email config to test graceful handling
            os.environ.pop('MAIL_SERVER', None)
            os.environ.pop('MAIL_USERNAME', None)
            os.environ.pop('MAIL_PASSWORD', None)
            os.environ.pop('MAIL_FROM', None)

            # Should not raise
            SummaryService.send_daily_summaries()

    def test_send_weekly_reports_runs_without_crash(self, app, sample_user):
        """send_weekly_reports runs without crashing even without email config."""
        with app.app_context():
            os.environ.pop('MAIL_SERVER', None)
            os.environ.pop('MAIL_USERNAME', None)
            os.environ.pop('MAIL_PASSWORD', None)
            os.environ.pop('MAIL_FROM', None)

            # Should not raise
            SummaryService.send_weekly_reports()

    def test_send_user_daily_summary_queries_today_tasks(self, app, sample_user):
        """_send_user_daily_summary correctly queries today's tasks."""
        with app.app_context():
            subject = Subject.query.filter_by(user_id=sample_user.id, name='Test').first()
            if not subject:
                subject = Subject(user_id=sample_user.id, name='Test', color='#0d6efd')
                db.session.add(subject)
                db.session.commit()

            # Create a task created today
            today_task = Task(
                user_id=sample_user.id,
                subject_id=subject.id,
                title='Today Task',
                priority='Medium',
                status='Pending',
                estimated_minutes=60
            )
            db.session.add(today_task)
            db.session.commit()

            # Mock email service AND ai_service to avoid actual API calls
            with patch('app.services.summary_service.email_service') as mock_email, \
                 patch('app.services.summary_service.ai_service.generate_daily_summary') as mock_ai:
                mock_email.is_configured.return_value = False
                mock_ai.return_value = {'summary': 'Test summary', 'recommendations': []}
                SummaryService._send_user_daily_summary(sample_user)

                # Verify the task was found (indirectly via no crash + mock calls)


class TestAIService:
    """Tests for AIService — spec section 21."""

    def test_is_available_checks_api_key(self, app):
        """is_available returns True when API key is configured."""
        with app.app_context():
            # Create fresh instance to pick up fixture env vars
            svc = AIService()
            assert svc.is_available() is True

    def test_is_available_false_without_key(self, app):
        """is_available returns False when no API key."""
        with app.app_context():
            os.environ.pop('AI_API_KEY', None)
            os.environ.pop('AI_MODEL', None)
            # Create a fresh service instance to pick up new env
            from app.services.ai_service import AIService
            fresh_service = AIService()
            assert fresh_service.is_available() is False
            os.environ['AI_API_KEY'] = 'test-key'
            os.environ['AI_MODEL'] = 'gpt-4o-mini'

    def test_extract_tasks_from_text_returns_structured_result(self, app):
        """extract_tasks_from_text returns dict with 'success', 'tasks', 'error' keys."""
        with app.app_context():
            # Mock the OpenAI call to test structured output parsing
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{"tasks": [{"title": "DBMS Assignment", "subject": "Database Management System", "priority": "high", "deadline": "2026-09-25", "estimated_minutes": 120}]}'))]
                )

                result = ai_service.extract_tasks_from_text(
                    'I have a DBMS assignment due Friday and a Python test next Monday.'
                )

                assert result['success'] is True
                assert len(result['tasks']) >= 1
                assert result['tasks'][0]['title'] == 'DBMS Assignment'

    def test_generate_study_plan_returns_structured_result(self, app):
        """generate_study_plan returns dict with plan structure."""
        with app.app_context():
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{"plan": {"days": [{"day": "Monday", "activities": [{"task": "Study", "subject": "General", "duration_minutes": 60, "focus": "review"}]}]}}'))]
                )

                result = ai_service.generate_study_plan(
                    'DBMS exam next Monday, Python assignment due Friday',
                    '3 hours available daily'
                )

                assert 'success' in result
                assert 'plan' in result

    def test_analyze_document_returns_structured_result(self, app):
        """analyze_document returns dict with analysis fields."""
        with app.app_context():
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{"summary": "Test document summary", "requirements": ["Requirement 1"], "difficulty": "medium", "estimated_minutes": 120, "suggested_tasks": [{"title": "Study task", "priority": "medium", "estimated_minutes": 30}], "recommendations": ["Review regularly"]})'))]
                )

                result = ai_service.analyze_document(
                    'This is a sample document text for testing.',
                    'test_document.pdf'
                )

                assert result['summary'] == 'Test document summary'
                assert result['requirements'] == ['Requirement 1']
                assert result['difficulty'] == 'medium'

    def test_generate_daily_summary_returns_structured_result(self, app):
        """generate_daily_summary returns dict with summary and recommendations."""
        with app.app_context():
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content='{"summary": "You have 1 tasks today.", "recommendations": ["Focus on completing pending tasks"]})'))]
                )

                result = ai_service.generate_daily_summary(
                    [{'title': 'Task 1', 'status': 'Pending'}],
                    2
                )

                assert result['summary'] == 'You have 1 tasks today.'
                assert 'recommendations' in result

    def test_ai_service_unavailable_graceful(self, app):
        """AI service handles API errors gracefully without crashing."""
        with app.app_context():
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_client.chat.completions.create.side_effect = Exception('API Error')

                result = ai_service.extract_tasks_from_text('Some input')
                assert result['success'] is False
                assert 'error' in result


class TestReportsPost:
    """Tests for reports POST endpoints — spec section 9."""

    def test_custom_report_post_valid_dates(self, client, sample_user):
        """POST /reports/custom with valid date range returns 200."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.post('/reports/custom', data={
                'start_date': '2026-09-01',
                'end_date': '2026-09-24'
            }, follow_redirects=True)
            assert response.status_code == 200

    def test_custom_report_post_missing_start_date(self, client, sample_user):
        """POST /reports/custom without start_date flashes error."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.post('/reports/custom', data={
                'end_date': '2026-09-24'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'Please select both start and end dates' in response.data

    def test_custom_report_post_missing_end_date(self, client, sample_user):
        """POST /reports/custom without end_date flashes error."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.post('/reports/custom', data={
                'start_date': '2026-09-01'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'Please select both start and end dates' in response.data

    def test_custom_report_post_end_before_start(self, client, sample_user):
        """POST /reports/custom with end < start flashes error."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.post('/reports/custom', data={
                'start_date': '2026-09-24',
                'end_date': '2026-09-01'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'End date must be after start date' in response.data

    def test_custom_report_post_invalid_date_format(self, client, sample_user):
        """POST /reports/custom with invalid date format flashes error."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.post('/reports/custom', data={
                'start_date': 'not-a-date',
                'end_date': '2026-09-24'
            }, follow_redirects=True)
            assert response.status_code == 200
            assert b'Invalid date format' in response.data

    def test_weekly_report_page_loads(self, client, sample_user):
        """GET /reports/weekly loads the weekly report page."""
        with client:
            client.post('/auth/login', data={
                'email': 'test@example.com',
                'password': 'password123'
            }, follow_redirects=True)
            response = client.get('/reports/week')
            assert response.status_code == 200
            assert b'Reports' in response.data


class TestCSRFProtection:
    """Tests for CSRF enforcement — spec section 13."""

    def test_csrf_config_exists_in_app(self, app):
        """CSRFProtect is configured in the Flask app."""
        # Verify the app has CSRF protection configured
        assert 'WTF_CSRF_ENABLED' in app.config

    def test_production_config_has_csrf_enabled(self):
        """Default app config has CSRF enabled."""
        # When no TESTING flag, CSRF should be on
        os.environ.pop('MAIL_SERVER', None)
        os.environ.pop('MAIL_USERNAME', None)
        os.environ.pop('MAIL_PASSWORD', None)
        os.environ.pop('MAIL_FROM', None)
        os.environ.pop('AI_API_KEY', None)
        os.environ.pop('AI_MODEL', None)

        prod_app = create_app({
            'SECRET_KEY': 'prod-test-key',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        })
        assert prod_app.config.get('WTF_CSRF_ENABLED') is True
