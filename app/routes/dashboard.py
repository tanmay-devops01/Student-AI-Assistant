"""
Dashboard routes - Main dashboard with statistics and charts.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models.task import Task
from app.models.subject import Subject
from app.models.reminder import Reminder
from app.services.ai_service import ai_service
from app.services.summary_service import SummaryService

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    """Main dashboard page."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Get statistics
    total_tasks = Task.query.filter_by(user_id=current_user.id).count()
    completed_tasks = Task.query.filter_by(
        user_id=current_user.id,
        status='Completed'
    ).count()
    pending_tasks = Task.query.filter_by(user_id=current_user.id, status='Pending').count()
    
    # Tasks due today (regardless of when they were created).
    today_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.deadline >= today_start,
        Task.deadline < today_end
    ).all()
    
    today_task_count = len(today_tasks)
    today_completed = sum(1 for t in today_tasks if t.status == 'Completed')

    # Overdue tasks
    overdue_tasks = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.deadline.isnot(None),
        Task.deadline < now
    ).count()

    # Upcoming deadlines (next 7 days)
    upcoming_deadlines = Task.query.filter(
        Task.user_id == current_user.id,
        Task.status.in_(['Pending', 'In Progress']),
        Task.deadline.isnot(None),
        Task.deadline >= now,
        Task.deadline <= now + timedelta(days=7)
    ).order_by(Task.deadline).limit(5).all()

    # Subject-wise progress
    subjects = Subject.query.filter_by(user_id=current_user.id).all()
    subject_progress = []
    for subject in subjects:
        stats = subject.get_stats()
        subject_progress.append({
            'name': subject.name,
            'color': subject.color,
            'percentage': stats['completion_percentage'],
            'total': stats['total_tasks'],
            'completed': stats['completed_tasks']
        })

    # Weekly activity data for chart
    weekly_data = []
    for i in range(7):
        day_start = now - timedelta(days=6-i)
        day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        created = Task.query.filter(
            Task.user_id == current_user.id,
            Task.created_at >= day_start,
            Task.created_at < day_end
        ).count()
        
        completed = Task.query.filter(
            Task.user_id == current_user.id,
            Task.status == 'Completed',
            Task.completed_at >= day_start,
            Task.completed_at < day_end
        ).count()
        
        day_name = day_start.strftime('%a')
        weekly_data.append({
            'day': day_name,
            'created': created,
            'completed': completed
        })

    # Recent reminders
    recent_reminders = Reminder.query.filter_by(user_id=current_user.id)\
        .order_by(Reminder.sent_at.desc())\
        .limit(5)\
        .all()

    completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    return render_template(
        'dashboard/index.html',
        now=now,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        overdue_tasks=overdue_tasks,
        today_task_count=today_task_count,
        today_completed=today_completed,
        today_tasks=today_tasks,
        upcoming_deadlines=upcoming_deadlines,
        subject_progress=subject_progress,
        weekly_data=weekly_data,
        recent_reminders=recent_reminders,
        completion_percentage=completion_percentage,
        ai_available=ai_service.is_available()
    )


@dashboard_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    """Quick add a task from the dashboard."""
    title = request.form.get('title', '').strip()
    
    if not title:
        flash('Task title is required.', 'error')
        return redirect(url_for('dashboard.index'))
    
    try:
        task = Task(
            user_id=current_user.id,
            title=title,
            priority='Medium'
        )
        db.session.add(task)
        db.session.commit()
        flash('Task added quickly!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to add task: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.index'))
