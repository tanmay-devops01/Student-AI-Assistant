"""
Task Management routes - CRUD operations for tasks.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app import db
from app.models.task import Task
from app.models.subject import Subject

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks', static_folder=None, static_url_path=None)


@tasks_bp.route('/')
@login_required
def index():
    """List all tasks with filtering and sorting."""
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    subject_filter = request.args.get('subject', '')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'created_at')
    sort_order = request.args.get('order', 'desc')

    query = Task.query.filter_by(user_id=current_user.id)

    if status_filter:
        query = query.filter(Task.status == status_filter)
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)
    if subject_filter:
        query = query.filter(Task.subject_id == subject_filter)
    if search_query:
        search = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Task.title.ilike(search),
                Task.description.ilike(search)
            )
        )

    # Apply sorting - handle priority specially
    if sort_by == 'deadline':
        sort_col = Task.deadline
        tasks = query.order_by(sort_col.desc() if sort_order == 'desc' else sort_col.asc()).all()
    elif sort_by == 'priority':
        tasks = query.all()
        # Sort in Python for custom priority ordering
        priority_order = {'High': 0, 'Medium': 1, 'Low': 2}
        tasks.sort(key=lambda t: (
            priority_order.get(t.priority, 3),
            t.deadline or datetime(2099, 12, 31)
        ))
        if sort_order == 'asc':
            tasks.reverse()
    elif sort_by == 'title':
        tasks = query.order_by(Task.title.asc() if sort_order == 'asc' else Task.title.desc()).all()
    else:
        tasks = query.order_by(Task.created_at.desc() if sort_order == 'desc' else Task.created_at.asc()).all()

    statuses = ['Pending', 'In Progress', 'Completed']
    priorities = ['Low', 'Medium', 'High']
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    stats = {
        'total': Task.query.filter_by(user_id=current_user.id).count(),
        'pending': Task.query.filter_by(user_id=current_user.id, status='Pending').count(),
        'in_progress': Task.query.filter_by(user_id=current_user.id, status='In Progress').count(),
        'completed': Task.query.filter_by(user_id=current_user.id, status='Completed').count(),
    }

    return render_template(
        'tasks/index.html',
        now=datetime.utcnow(),
        tasks=tasks,
        statuses=statuses,
        priorities=priorities,
        subjects=subjects,
        stats=stats,
        filters={
            'status': status_filter,
            'priority': priority_filter,
            'subject': subject_filter,
            'search': search_query,
            'sort': sort_by,
            'order': sort_order
        }
    )


@tasks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Create a new task."""
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id = request.form.get('subject_id', type=int)
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', 'Pending')
        deadline_str = request.form.get('deadline', '')
        estimated_minutes = request.form.get('estimated_minutes', type=int)

        if not title:
            flash('Task title is required.', 'error')
            return render_template('tasks/create.html', subjects=subjects)

        if priority not in ['Low', 'Medium', 'High']:
            priority = 'Medium'

        if status not in ['Pending', 'In Progress', 'Completed']:
            status = 'Pending'
        if subject_id and not Subject.query.filter_by(id=subject_id, user_id=current_user.id).first():
            flash('Please choose one of your own subjects.', 'error')
            return render_template('tasks/create.html', subjects=subjects)
        if estimated_minutes is not None and estimated_minutes < 0:
            flash('Estimated time cannot be negative.', 'error')
            return render_template('tasks/create.html', subjects=subjects)
        if estimated_minutes is not None and estimated_minutes > 1440:
            flash('Estimated time cannot exceed 24 hours.', 'error')
            return render_template('tasks/create.html', subjects=subjects)

        deadline = None
        if deadline_str:
            try:
                deadline = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                    except ValueError:
                        flash('Invalid deadline. Please choose a valid date and time.', 'error')
                        return render_template('tasks/create.html', subjects=subjects)

        try:
            task = Task(
                user_id=current_user.id,
                subject_id=subject_id,
                title=title,
                description=description,
                priority=priority,
                status=status,
                deadline=deadline,
                estimated_minutes=estimated_minutes,
                completed_at=datetime.utcnow() if status == 'Completed' else None
            )
            db.session.add(task)
            db.session.commit()
            flash('Task created successfully!', 'success')
            return redirect(url_for('tasks.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to create task: {str(e)}', 'error')
            return render_template('tasks/create.html', subjects=subjects)

    return render_template('tasks/create.html', subjects=subjects)


@tasks_bp.route('/<int:task_id>')
@login_required
def view(task_id):
    """View a specific task."""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    return render_template('tasks/view.html', task=task)


@tasks_bp.route('/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    """Edit a task."""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    subjects = Subject.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject_id = request.form.get('subject_id', type=int)
        priority = request.form.get('priority', 'Medium')
        status = request.form.get('status', task.status)
        deadline_str = request.form.get('deadline', '')
        estimated_minutes = request.form.get('estimated_minutes', type=int)

        if not title:
            flash('Task title is required.', 'error')
            return render_template('tasks/edit.html', task=task, subjects=subjects)

        if priority not in ['Low', 'Medium', 'High']:
            priority = 'Medium'
        if status not in ['Pending', 'In Progress', 'Completed']:
            status = 'Pending'
        if subject_id and not Subject.query.filter_by(id=subject_id, user_id=current_user.id).first():
            flash('Please choose one of your own subjects.', 'error')
            return render_template('tasks/edit.html', task=task, subjects=subjects)
        if estimated_minutes is not None and estimated_minutes < 0:
            flash('Estimated time cannot be negative.', 'error')
            return render_template('tasks/edit.html', task=task, subjects=subjects)
        if estimated_minutes is not None and estimated_minutes > 1440:
            flash('Estimated time cannot exceed 24 hours.', 'error')
            return render_template('tasks/edit.html', task=task, subjects=subjects)

        old_status = task.status
        task.title = title
        task.description = description
        task.subject_id = subject_id
        task.priority = priority
        task.estimated_minutes = estimated_minutes

        if deadline_str:
            try:
                task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
            except ValueError:
                try:
                    task.deadline = datetime.strptime(deadline_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    try:
                        task.deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                    except ValueError:
                        flash('Invalid deadline. Please choose a valid date and time.', 'error')
                        return render_template('tasks/edit.html', task=task, subjects=subjects)
        else:
            task.deadline = None

        if status == 'Completed' and old_status != 'Completed':
            task.mark_complete()
        elif status != 'Completed' and old_status == 'Completed':
            task.completed_at = None
        task.status = status

        try:
            db.session.commit()
            flash('Task updated successfully!', 'success')
            return redirect(url_for('tasks.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update task: {str(e)}', 'error')
            return render_template('tasks/edit.html', task=task, subjects=subjects)

    return render_template('tasks/edit.html', task=task, subjects=subjects)


@tasks_bp.route('/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_complete(task_id):
    """Toggle task completion status."""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    if task.status == 'Completed':
        task.mark_incomplete()
        flash('Task marked as pending.', 'info')
    else:
        task.mark_complete()
        flash('Task marked as completed!', 'success')

    db.session.commit()
    return redirect(url_for('tasks.index'))


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    """Delete a task."""
    task = Task.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete task: {str(e)}', 'error')

    return redirect(url_for('tasks.index'))


@tasks_bp.route('/api/tasks')
@login_required
def api_tasks():
    """API endpoint for getting tasks as JSON."""
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    return jsonify([task.to_dict() for task in tasks])


@tasks_bp.route('/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    """Delete multiple tasks at once."""
    task_ids = request.form.getlist('task_ids', type=int)

    if not task_ids:
        flash('No tasks selected.', 'warning')
        return redirect(url_for('tasks.index'))

    try:
        Task.query.filter(
            Task.id.in_(task_ids),
            Task.user_id == current_user.id
        ).delete(synchronize_session=False)
        db.session.commit()
        flash(f'{len(task_ids)} task(s) deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete tasks: {str(e)}', 'error')

    return redirect(url_for('tasks.index'))
