"""
Student AI Assistant - Test Suite
"""

import pytest
import os
import sys
import tempfile
import io
import json
import zipfile
import re
from datetime import datetime, timedelta

# Add the parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.subject import Subject
from app.models.task import Task
from app.models.document import Document


@pytest.fixture
def app():
    """Create and configure a test application instance."""
    import tempfile
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'UPLOAD_FOLDER': tempfile.mkdtemp()
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        # Cleanup handled by temp_dir auto-deletion on Windows
    
@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def logged_in_client(app, client):
    """Create a test client with a logged-in user."""
    # Use unique email to avoid conflicts with test_user fixture
    user_email = 'loggedin_test@example.com'
    with app.app_context():
        user = User(name='Test User', email=user_email)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()

        # Log in with follow_redirects to ensure session is properly set
        client.post('/auth/login', data={
            'email': user_email,
            'password': 'password123'
        }, follow_redirects=True)

    return client


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = User(name='Test User', email='test_user@example.com')
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        # Return the email instead of the detached User object
        return user.email


class TestAuthentication:
    """Test authentication functionality."""
    
    def test_register_success(self, client, app):
        """Test successful user registration."""
        with app.app_context():
            response = client.post('/auth/register', data={
                'name': 'New User',
                'email': 'newuser@example.com',
                'password': 'password123',
                'confirm_password': 'password123'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Registration successful' in response.data
            
            # Verify user was created
            user = User.query.filter_by(email='newuser@example.com').first()
            assert user is not None
            assert user.name == 'New User'
    
    def test_register_duplicate_email(self, client, app):
        """Test registration with duplicate email."""
        with app.app_context():
            # Create first user
            user = User(name='First User', email='duplicate@example.com')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()
            
            # Try to register with same email
            response = client.post('/auth/register', data={
                'name': 'Second User',
                'email': 'duplicate@example.com',
                'password': 'password123',
                'confirm_password': 'password123'
            }, follow_redirects=True)
            
            assert b'This email is already registered' in response.data
    
    def test_register_validation(self, client, app):
        """Test registration with invalid data."""
        response = client.post('/auth/register', data={
            'name': '',
            'email': 'invalid-email',
            'password': '123',
            'confirm_password': '456'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Name must be at least 2 characters' in response.data or \
               b'Please enter a valid email address' in response.data
    
    def test_login_success(self, client, app):
        """Test successful login."""
        with app.app_context():
            user = User(name='Login Test', email='logintest2@example.com')
            user.set_password('testpass')
            db.session.add(user)
            db.session.commit()
            
            response = client.post('/auth/login', data={
                'email': 'logintest2@example.com',
                'password': 'testpass'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Welcome back' in response.data or b'Dashboard' in response.data

    def test_login_rejects_external_next_url(self, client, app):
        with app.app_context():
            user = User(name='Safe Redirect', email='safe-redirect@example.com')
            user.set_password('testpass')
            db.session.add(user)
            db.session.commit()
            response = client.post('/auth/login?next=https://example.org', data={
                'email': user.email,
                'password': 'testpass'
            })
            assert response.status_code == 302
            assert response.location.endswith('/dashboard')

    def test_login_csrf_token_is_required_and_form_includes_one(self, client, app):
        app.config['WTF_CSRF_ENABLED'] = True
        page = client.get('/auth/login')
        token_match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        assert token_match
        response = client.post('/auth/login', data={
            'csrf_token': token_match.group(1).decode(),
            'email': 'missing@example.com',
            'password': 'bad-password'
        })
        assert response.status_code == 200
        rejected = client.post('/auth/login', data={
            'email': 'missing@example.com',
            'password': 'bad-password'
        })
        assert rejected.status_code == 400
        assert b'This form has expired' in rejected.data
    
    def test_login_invalid_credentials(self, client, app):
        """Test login with invalid credentials."""
        response = client.post('/auth/login', data={
            'email': 'nonexistent@example.com',
            'password': 'wrongpass'
        }, follow_redirects=True)
        
        assert b'Invalid email or password' in response.data
    
    def test_logout(self, client, app, test_user):
        """Test user logout."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            
            # Log out
            response = client.post('/auth/logout', follow_redirects=True)
            assert response.status_code == 200
            assert b'You have been logged out' in response.data
    
    def test_protected_route(self, client):
        """Test that protected routes require login."""
        response = client.get('/dashboard')
        assert response.status_code == 302  # Redirect to login
        assert '/auth/login' in response.location


class TestTaskManagement:
    """Test task CRUD operations."""
    
    def test_create_task(self, logged_in_client, app):
        """Test creating a task."""
        with app.app_context():
            response = logged_in_client.post('/tasks/create', data={
                'title': 'Test Task',
                'description': 'A test task description',
                'priority': 'Medium',
                'status': 'Pending'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Task created' in response.data
            
            # Verify task was created
            task = Task.query.filter_by(title='Test Task').first()
            assert task is not None
            assert task.status == 'Pending'
    
    def test_create_task_validation(self, logged_in_client, app):
        """Test task creation with missing title."""
        response = logged_in_client.post('/tasks/create', data={
            'title': '',
            'priority': 'Medium'
        }, follow_redirects=True)
        
        assert b'Task title is required' in response.data
    
    def test_view_task(self, client, app, test_user):
        """Test viewing a task."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in as test_user
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            # Create a task
            task = Task(
                user_id=user.id,
                title='View Test Task',
                priority='Low'
            )
            db.session.add(task)
            db.session.commit()
            
            # View the task
            response = client.get(f'/tasks/{task.id}')
            assert response.status_code == 200
            assert b'View Test Task' in response.data
    
    def test_edit_task(self, client, app, test_user):
        """Test editing a task."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in as test_user
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            # Create a task
            task = Task(
                user_id=user.id,
                title='Edit Test Task',
                priority='Low'
            )
            db.session.add(task)
            db.session.commit()
            
            # Edit the task
            response = client.post(f'/tasks/{task.id}/edit', data={
                'title': 'Updated Task Title',
                'priority': 'High',
                'deadline': '2026-10-12T14:30'
            }, follow_redirects=True)
            
            assert response.status_code == 200
            
            # Verify changes
            task = db.session.get(Task, task.id)
            assert task.title == 'Updated Task Title'
            assert task.priority == 'High'
            assert task.deadline == datetime(2026, 10, 12, 14, 30)

    def test_user_progress_stats(self, app, test_user):
        with app.app_context():
            user = User.query.filter_by(email=test_user).first()
            user.tasks.append(Task(title='Completed', status='Completed'))
            user.tasks.append(Task(title='Pending', status='Pending'))
            db.session.commit()
            stats = user.get_progress_stats()
            assert stats['total_tasks'] == 2
            assert stats['completed_tasks'] == 1
            assert stats['completion_percentage'] == 50
    
    def test_delete_task(self, client, app, test_user):
        """Test deleting a task."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in as test_user
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            # Create a task
            task = Task(
                user_id=user.id,
                title='Delete Test Task',
                priority='Low'
            )
            db.session.add(task)
            db.session.commit()
            
            # Delete the task
            response = client.post(f'/tasks/{task.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'Task deleted' in response.data
            
            # Verify deletion
            task = db.session.get(Task, task.id)
            assert task is None
    
    def test_toggle_task_completion(self, client, app, test_user):
        """Test toggling task completion status."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in as test_user
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            # Create a pending task
            task = Task(
                user_id=user.id,
                title='Toggle Test Task',
                status='Pending'
            )
            db.session.add(task)
            db.session.commit()
            
            # Mark as complete
            response = client.post(f'/tasks/{task.id}/toggle', follow_redirects=True)
            assert response.status_code == 200
            
            task = db.session.get(Task, task.id)
            assert task.status == 'Completed'
            assert task.completed_at is not None
            
            # Mark as incomplete
            response = client.post(f'/tasks/{task.id}/toggle', follow_redirects=True)
            task = db.session.get(Task, task.id)
            assert task.status == 'Pending'
            assert task.completed_at is None
    
    def test_task_authorization(self, client, app):
        """Test that users cannot access other users' tasks."""
        with app.app_context():
            # Create two users
            user1 = User(name='User 1', email='user1@example.com')
            user1.set_password('password123')
            user2 = User(name='User 2', email='user2@example.com')
            user2.set_password('password123')
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Create task for user1
            task = Task(
                user_id=user1.id,
                title='User 1 Private Task',
                priority='High'
            )
            db.session.add(task)
            
            # Create task for user2
            task2 = Task(
                user_id=user2.id,
                title='User 2 Private Task',
                priority='Low'
            )
            db.session.add(task2)
            db.session.commit()
            
            # Log in as user2
            client.post('/auth/login', data={
                'email': 'user2@example.com',
                'password': 'password123'
            })
            
            # Try to access user1's task
            response = client.get(f'/tasks/{task.id}')
            assert response.status_code == 404  # Not found (security measure)
            
            # Verify user2 can access their own task
            response = client.get(f'/tasks/{task2.id}')
            assert response.status_code == 200
            assert b'User 2 Private Task' in response.data


class TestSubjectManagement:
    """Test subject CRUD operations."""
    
    def test_create_subject(self, logged_in_client, app):
        """Test creating a subject."""
        response = logged_in_client.post('/subjects/create', data={
            'name': 'Test Subject',
            'description': 'A test subject',
            'color': '#ff0000'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Subject created' in response.data
        
        subject = Subject.query.filter_by(name='Test Subject').first()
        assert subject is not None
    
    def test_subject_uniqueness(self, logged_in_client, app):
        """Test that subject names must be unique per user."""
        with app.app_context():
            subject = Subject(
                user_id=1,  # Test user ID
                name='Unique Subject',
                color='#000000'
            )
            db.session.add(subject)
            db.session.commit()
            
            response = logged_in_client.post('/subjects/create', data={
                'name': 'Unique Subject',
                'color': '#ffffff'
            }, follow_redirects=True)
            
            assert b'already exists' in response.data
    
    def test_delete_subject(self, client, app, test_user):
        """Test deleting a subject."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Log in as test_user
            client.post('/auth/login', data={
                'email': user.email,
                'password': 'password123'
            }, follow_redirects=True)
            subject = Subject(
                user_id=user.id,
                name='Delete Me',
                color='#cccccc'
            )
            db.session.add(subject)
            db.session.commit()
            
            response = client.post(f'/subjects/{subject.id}/delete', follow_redirects=True)
            assert response.status_code == 200
            assert b'Subject deleted' in response.data
            
            subject = db.session.get(Subject, subject.id)
            assert subject is None


class TestAIFeatures:
    """Test AI feature integration."""
    
    def test_ai_unavailable_graceful(self, logged_in_client, app):
        """Test that app works when AI is not configured."""
        with app.app_context():
            response = logged_in_client.get('/ai', follow_redirects=True)
            assert response.status_code == 200
            # Should show warning about AI not configured
            assert b'not configured' in response.data.lower() or \
                   b'AI Assistant' in response.data
    
    def test_study_plan_page_loads(self, logged_in_client):
        """Test that study plan page loads."""
        response = logged_in_client.get('/ai/study-plan')
        assert response.status_code == 200
        assert b'Generate Study Plan' in response.data
    
    def test_create_tasks_page_loads(self, logged_in_client):
        """Test that create tasks page loads."""
        response = logged_in_client.get('/ai/create-tasks')
        assert response.status_code == 200
        assert b'Create Tasks with AI' in response.data

    def test_confirm_tasks_applies_edits_and_skips_unchecked(self, logged_in_client, app):
        tasks = [
            {'title': 'Original title', 'subject': 'Old subject', 'priority': 'low', 'deadline': None, 'estimated_minutes': 30},
            {'title': 'Skipped title', 'subject': 'General', 'priority': 'medium', 'deadline': None, 'estimated_minutes': 60}
        ]
        response = logged_in_client.post('/ai/tasks/confirm', data={
            'tasks_data': json.dumps(tasks),
            'action': 'accept',
            'include_task': '1',
            'edit_title_1': 'Edited title',
            'edit_subject_1': 'Edited subject',
            'edit_priority_1': 'high',
            'edit_minutes_1': '45',
            'edit_deadline_1': ''
        }, follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            created = Task.query.filter_by(title='Edited title').first()
            assert created is not None
            assert created.priority == 'High'
            assert created.estimated_minutes == 45
            assert created.subject.name == 'Edited subject'
            assert Task.query.filter_by(title='Skipped title').first() is None


class TestDocuments:
    """Test document upload functionality."""
    
    def test_upload_page_loads(self, logged_in_client):
        """Test that upload page loads."""
        response = logged_in_client.get('/documents/upload')
        assert response.status_code == 200
        assert b'Upload Assignment' in response.data
    
    def test_documents_page_loads(self, logged_in_client):
        """Test that documents page loads."""
        response = logged_in_client.get('/documents', follow_redirects=True)
        assert response.status_code == 200
        assert b'Documents' in response.data
    
    def test_invalid_file_rejected(self, logged_in_client, app):
        """Test that invalid file types are rejected."""
        with app.app_context():
            # Try to upload an invalid file type
            response = logged_in_client.post('/documents/upload', data={
                'file': (b'invalid content', 'test.exe')
            }, content_type='multipart/form-data', follow_redirects=True)
            
            assert response.status_code == 200
            assert b'Invalid file type' in response.data

    def test_docx_upload_extracts_text_without_ai(self, logged_in_client, app, monkeypatch):
        from app.routes import documents as document_routes
        monkeypatch.setattr(document_routes.ai_service, 'is_available', lambda: False)
        docx = io.BytesIO()
        with zipfile.ZipFile(docx, 'w') as archive:
            archive.writestr(
                'word/document.xml',
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Assignment text</w:t></w:r></w:p></w:body></w:document>'
            )
        docx.seek(0)
        response = logged_in_client.post('/documents/upload', data={
            'file': (docx, 'assignment.docx')
        }, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        with app.app_context():
            document = Document.query.filter_by(original_filename='assignment.docx').first()
            assert document is not None
            assert document.extracted_text == 'Assignment text'


class TestReports:
    """Test reports functionality."""
    
    def test_weekly_report_loads(self, logged_in_client):
        """Test that weekly report page loads."""
        response = logged_in_client.get('/reports/week')
        assert response.status_code == 200
        assert b'Reports' in response.data
    
    def test_monthly_report_loads(self, logged_in_client):
        """Test that monthly report page loads."""
        response = logged_in_client.get('/reports/month')
        assert response.status_code == 200
    
    def test_custom_report_page_loads(self, logged_in_client):
        """Test that custom report page loads."""
        response = logged_in_client.get('/reports/custom')
        assert response.status_code == 200
        assert b'Custom Report' in response.data


class TestDashboard:
    """Test dashboard functionality."""
    
    def test_dashboard_loads(self, logged_in_client):
        """Test that dashboard loads."""
        response = logged_in_client.get('/')
        assert response.status_code == 200
        assert b'Dashboard' in response.data

    def test_dashboard_lists_tasks_due_today(self, logged_in_client, app):
        with app.app_context():
            user = User.query.filter_by(email='loggedin_test@example.com').first()
            task = Task(
                user_id=user.id,
                title='Due today',
                deadline=datetime.utcnow().replace(hour=23, minute=59, second=0, microsecond=0)
            )
            db.session.add(task)
            db.session.commit()
        response = logged_in_client.get('/')
        assert response.status_code == 200
        assert b'Due today' in response.data
    
    def test_dashboard_shows_stats(self, logged_in_client, app, test_user):
        """Test that dashboard shows task statistics."""
        with app.app_context():
            # Re-query user to avoid DetachedInstanceError
            user = User.query.filter_by(email='test_user@example.com').first()
            # Create tasks
            for i in range(3):
                task = Task(
                    user_id=user.id,
                    title=f'Stat Test Task {i}',
                    priority='Medium',
                    status='Pending' if i < 2 else 'Completed'
                )
                db.session.add(task)
            db.session.commit()
            
            response = logged_in_client.get('/')
            assert response.status_code == 200
            # Should show completion stats
            assert b'Total Tasks' in response.data or b'total' in response.data.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
