"""
AI Assistant routes - Study plan generation and task extraction.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.task import Task
from app.models.subject import Subject
from app.services.ai_service import ai_service

ai_bp = Blueprint('ai', __name__, url_prefix='/ai', static_folder=None, static_url_path=None)


@ai_bp.route('/')
@login_required
def index():
    """AI Assistant main page."""
    return render_template('ai/index.html', ai_available=ai_service.is_available())


@ai_bp.route('/study-plan', methods=['GET', 'POST'])
@login_required
def study_plan():
    """Generate a study plan using AI."""
    if request.method == 'POST':
        user_input = request.form.get('user_input', '').strip()
        
        if not user_input:
            flash('Please describe your study needs.', 'error')
            return render_template('ai/study_plan.html', ai_available=ai_service.is_available())
        
        # Get existing tasks for context
        tasks = Task.query.filter_by(user_id=current_user.id).limit(20).all()
        user_tasks = [{
            'title': t.title,
            'subject': t.subject.name if t.subject else 'General',
            'deadline': t.deadline.strftime('%Y-%m-%d') if t.deadline else 'No deadline',
            'priority': t.priority
        } for t in tasks]
        
        # Generate study plan
        result = ai_service.generate_study_plan(user_input, user_tasks)
        
        if result['success']:
            return render_template(
                'ai/study_plan_result.html',
                plan=result['plan'],
                confidence=result['confidence'],
                user_input=user_input,
                ai_available=ai_service.is_available()
            )
        else:
            flash(result.get('error', 'Failed to generate study plan.'), 'error')
            return render_template('ai/study_plan.html', ai_available=ai_service.is_available())
    
    return render_template('ai/study_plan.html', ai_available=ai_service.is_available())


@ai_bp.route('/study-plan/accept', methods=['POST'])
@login_required
def accept_plan():
    """Accept a study plan and create tasks from it."""
    plan_data = request.form.get('plan_data', '{}')
    
    try:
        import json
        plan = json.loads(plan_data)
    except (json.JSONDecodeError, TypeError):
        flash('Invalid plan data.', 'error')
        return redirect(url_for('ai.study_plan'))
    
    if not isinstance(plan, dict):
        flash('Invalid plan structure.', 'error')
        return redirect(url_for('ai.study_plan'))

    days = plan.get('days', [])
    
    if not isinstance(days, list):
        flash('Invalid plan structure.', 'error')
        return redirect(url_for('ai.study_plan'))
    
    created_count = 0
    
    for day in days:
        if not isinstance(day, dict):
            continue
        activities = day.get('activities', [])
        if not isinstance(activities, list):
            continue
        for activity in activities:
            if not isinstance(activity, dict):
                continue
            title = activity.get('task', '').strip() if isinstance(activity.get('task'), str) else ''
            if not title:
                continue
            title = title[:200]
            
            subject_name = activity.get('subject', 'General')
            if not isinstance(subject_name, str) or not subject_name.strip():
                subject_name = 'General'
            subject_name = subject_name.strip()[:100]
            try:
                duration = int(activity.get('duration_minutes', 60))
                if duration < 1 or duration > 1440:
                    duration = 60
            except (TypeError, ValueError):
                duration = 60
            
            # Find or create subject
            subject = Subject.query.filter_by(
                user_id=current_user.id,
                name=subject_name
            ).first()
            
            if not subject:
                subject = Subject(
                    user_id=current_user.id,
                    name=subject_name,
                    color='#0d6efd'
                )
                db.session.add(subject)
                db.session.flush()
            
            # Create task
            task = Task(
                user_id=current_user.id,
                subject_id=subject.id,
                title=title,
                priority='Medium',
                status='Pending',
                estimated_minutes=duration
            )
            db.session.add(task)
            created_count += 1
    
    db.session.commit()
    flash(f'Study plan accepted! Created {created_count} task(s).', 'success')
    return redirect(url_for('tasks.index'))


@ai_bp.route('/create-tasks', methods=['GET', 'POST'])
@login_required
def create_tasks():
    """Extract tasks from natural language using AI."""
    if request.method == 'POST':
        user_input = request.form.get('user_input', '').strip()
        
        if not user_input:
            flash('Please describe your tasks.', 'error')
            return render_template('ai/create_tasks.html', ai_available=ai_service.is_available())
        
        # Extract tasks using AI
        result = ai_service.extract_tasks_from_text(user_input)
        
        if result['success']:
            return render_template(
                'ai/tasks_extracted.html',
                tasks=result['tasks'],
                user_input=user_input,
                ai_available=ai_service.is_available()
            )
        else:
            flash(result.get('error', 'Failed to extract tasks.'), 'error')
            return render_template('ai/create_tasks.html', ai_available=ai_service.is_available())
    
    return render_template('ai/create_tasks.html', ai_available=ai_service.is_available())


@ai_bp.route('/tasks/confirm', methods=['POST'])
@login_required
def confirm_tasks():
    """Confirm extracted tasks and save them to the database."""
    tasks_data = request.form.get('tasks_data', '[]')
    action = request.form.get('action', 'cancel')
    
    try:
        import json
        tasks = json.loads(tasks_data)
    except (json.JSONDecodeError, TypeError):
        flash('Invalid task data.', 'error')
        return redirect(url_for('ai.create_tasks'))
    
    if action == 'cancel':
        flash('Task creation cancelled.', 'info')
        return redirect(url_for('ai.create_tasks'))

    if not isinstance(tasks, list):
        flash('Invalid task data.', 'error')
        return redirect(url_for('ai.create_tasks'))

    if not tasks:
        flash('No tasks to save.', 'warning')
        return redirect(url_for('ai.create_tasks'))

    created_count = 0
    rejected_count = 0
    included_ids = set(request.form.getlist('include_task'))

    for index, task_data in enumerate(tasks, start=1):
        if not isinstance(task_data, dict):
            continue
        task_id = str(index)
        if task_id not in included_ids:
            rejected_count += 1
            continue

        title = task_data.get('title', '')
        if not isinstance(title, str) or not title.strip():
            continue
        title = title.strip()
        if len(title) > 200:
            title = title[:200]

        subject_name = request.form.get(f'edit_subject_{task_id}', task_data.get('subject', 'General'))
        if not isinstance(subject_name, str) or not subject_name.strip():
            subject_name = 'General'
        subject_name = subject_name.strip()[:100]

        raw_priority = request.form.get(f'edit_priority_{task_id}', task_data.get('priority', 'medium'))
        priority_map = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
        priority = priority_map.get(str(raw_priority).lower(), 'Medium')

        estimated = request.form.get(f'edit_minutes_{task_id}', task_data.get('estimated_minutes', 60))
        try:
            estimated_minutes = int(estimated)
            if estimated_minutes < 1 or estimated_minutes > 1440:
                estimated_minutes = 60
        except (ValueError, TypeError):
            estimated_minutes = 60

        deadline_str = request.form.get(f'edit_deadline_{task_id}', task_data.get('deadline'))
        
        # Find or create subject
        subject = Subject.query.filter_by(
            user_id=current_user.id,
            name=subject_name
        ).first()
        
        if not subject:
            subject = Subject(
                user_id=current_user.id,
                name=subject_name,
                color='#0d6efd'
            )
            db.session.add(subject)
            db.session.flush()
        
        # Parse deadline
        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
            except ValueError:
                pass
        
        # Check if task was edited
        edited_title = request.form.get(f'edit_title_{task_id}', '').strip()
        if edited_title:
            title = edited_title[:200]
        
        # Create task
        task = Task(
            user_id=current_user.id,
            subject_id=subject.id,
            title=title,
            priority=priority,
            status='Pending',
            deadline=deadline,
            estimated_minutes=estimated_minutes
        )
        db.session.add(task)
        created_count += 1
    
    db.session.commit()
    flash(f'{created_count} task(s) created successfully!', 'success')
    return redirect(url_for('tasks.index'))


@ai_bp.route('/test')
@login_required
def test_ai():
    """Test AI connection page."""
    if ai_service.is_available():
        flash('AI service is configured and available.', 'success')
    else:
        flash('AI service is not configured. Please set AI_API_KEY in your .env file.', 'warning')
    
    return redirect(url_for('ai.index'))
