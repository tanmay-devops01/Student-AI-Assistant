"""
Document Upload and Analysis routes.
"""

import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from flask import current_app
from app.models.document import Document
from app.models.task import Task
from app.models.subject import Subject
from app.services.ai_service import ai_service
from app.services.email_service import email_service

documents_bp = Blueprint('documents', __name__, url_prefix='/documents', static_folder=None, static_url_path=None)


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def get_extracted_text(file_path):
    """Extract text from uploaded file."""
    ext = file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
    
    try:
        if ext == 'pdf':
            return extract_pdf_text(file_path)
        elif ext in ['txt']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        elif ext == 'docx':
            import zipfile
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(file_path) as archive:
                document_xml = archive.read('word/document.xml')
            root = ET.fromstring(document_xml)
            namespace = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            paragraphs = []
            for paragraph in root.findall('.//w:p', namespace):
                text = ''.join(node.text or '' for node in paragraph.findall('.//w:t', namespace))
                if text:
                    paragraphs.append(text)
            return '\n'.join(paragraphs).strip() or None
        else:
            return None
    except Exception as e:
        return None


def extract_pdf_text(file_path):
    """Extract text from PDF file."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip() if text else None
    except ImportError:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip() if text else None
        except ImportError:
            return None
    except Exception:
        return None


@documents_bp.route('/')
@login_required
def index():
    """List all uploaded documents."""
    documents = Document.query.filter_by(user_id=current_user.id)\
        .order_by(Document.uploaded_at.desc())\
        .all()
    return render_template('documents/index.html', documents=documents)


@documents_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload a document for analysis."""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected.', 'error')
            return render_template('documents/upload.html')
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return render_template('documents/upload.html')

        original_filename = secure_filename(file.filename)
        if not original_filename:
            flash('The selected file needs a valid filename.', 'error')
            return render_template('documents/upload.html')
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Allowed: PDF, TXT, DOC, DOCX.', 'error')
            return render_template('documents/upload.html')
        
        # Check file size (10MB max)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > 10 * 1024 * 1024:
            flash('File too large. Maximum size is 10MB.', 'error')
            return render_template('documents/upload.html')
        if file_size == 0:
            flash('The selected file is empty.', 'error')
            return render_template('documents/upload.html')
        
        # Generate secure filename
        unique_id = uuid.uuid4().hex[:12]
        filename = f"{unique_id}_{original_filename}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Save file
        try:
            file.save(file_path)
        except Exception as e:
            flash(f'Failed to save file: {str(e)}', 'error')
            return render_template('documents/upload.html')
        
        # Extract text
        extracted_text = get_extracted_text(file_path)
        file_ext = os.path.splitext(original_filename)[1].lower()
        
        # Create document record
        document = Document(
            user_id=current_user.id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            extracted_text=extracted_text
        )
        try:
            db.session.add(document)
            db.session.commit()
        except Exception:
            db.session.rollback()
            if os.path.exists(file_path):
                os.remove(file_path)
            current_app.logger.exception('Failed to save uploaded document record')
            flash('The document could not be saved. Please try again.', 'error')
            return render_template('documents/upload.html'), 500
        
        # If text was extracted, analyze with AI
        if extracted_text and ai_service.is_available():
            flash('Analyzing document with AI...', 'info')
            analysis_result = ai_service.analyze_document(extracted_text, original_filename)
            
            if isinstance(analysis_result, dict) and (analysis_result.get('success', False) or analysis_result.get('summary')):
                document.summary = analysis_result.get('summary')
                document.difficulty = analysis_result.get('difficulty', 'Unknown')
                document.estimated_minutes = analysis_result.get('estimated_minutes')
                
                # Save suggested tasks for user to review
                suggested_tasks = analysis_result.get('suggested_tasks', [])
                requirements = analysis_result.get('requirements', [])
                recommendations = analysis_result.get('recommendations', [])
                
                db.session.commit()
                
                return render_template(
                    'documents/analysis_result.html',
                    document=document,
                    analysis=analysis_result,
                    suggested_tasks=suggested_tasks,
                    requirements=requirements,
                    recommendations=recommendations
                )
            else:
                error_message = analysis_result.get('error', 'AI analysis failed.') if isinstance(analysis_result, dict) else 'AI analysis returned an invalid response.'
                flash(error_message, 'error')
        elif extracted_text:
            flash('File uploaded but AI analysis unavailable. Please configure AI_API_KEY.', 'warning')
        else:
            if file_ext == '.pdf':
                flash('Could not extract text from PDF. The PDF may be scanned/images only. OCR may be required.', 'warning')
            else:
                flash('Could not extract text from the file.', 'warning')
        
        return redirect(url_for('documents.view', document_id=document.id))
    
    return render_template('documents/upload.html')


@documents_bp.route('/<int:document_id>')
@login_required
def view(document_id):
    """View a specific document."""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    return render_template('documents/view.html', document=document)


@documents_bp.route('/<int:document_id>/download')
@login_required
def download(document_id):
    """Download an uploaded document."""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    
    if os.path.exists(document.file_path):
        return send_from_directory(
            current_app.config['UPLOAD_FOLDER'],
            document.filename,
            as_attachment=True,
            download_name=document.original_filename
        )
    
    flash('File not found.', 'error')
    return redirect(url_for('documents.index'))


@documents_bp.route('/<int:document_id>/delete', methods=['POST'])
@login_required
def delete(document_id):
    """Delete a document."""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    
    file_path = document.file_path
    try:
        db.session.delete(document)
        db.session.commit()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                current_app.logger.exception('Could not remove uploaded file %s', file_path)
        flash('Document deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to delete document: {str(e)}', 'error')
    
    return redirect(url_for('documents.index'))


@documents_bp.route('/<int:document_id>/create-tasks', methods=['POST'])
@login_required
def create_tasks_from_document(document_id):
    """Create tasks from a document's suggested tasks."""
    document = Document.query.filter_by(id=document_id, user_id=current_user.id).first_or_404()
    
    # Get suggested tasks from the analysis (stored temporarily)
    suggested_tasks = request.form.getlist('suggested_tasks')
    
    if not suggested_tasks:
        flash('No tasks to create.', 'warning')
        return redirect(url_for('documents.view', document_id=document_id))
    
    created_count = 0
    
    for task_data in suggested_tasks:
        try:
            import json
            task_info = json.loads(task_data)
        except (json.JSONDecodeError, TypeError):
            continue
        
        title = task_info.get('title', '').strip() if isinstance(task_info.get('title'), str) else ''
        if not title or len(title) > 200:
            continue

        # Validate and normalize priority
        raw_priority = task_info.get('priority', 'medium')
        priority_map = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}
        priority = priority_map.get(str(raw_priority).lower(), 'Medium')

        # Validate estimated_minutes
        estimated = task_info.get('estimated_minutes', 60)
        try:
            estimated_minutes = int(estimated)
            if estimated_minutes < 1 or estimated_minutes > 1440:
                estimated_minutes = 60
        except (ValueError, TypeError):
            estimated_minutes = 60
            
        # Find or create subject
        subject_name = task_info.get('subject', 'General')
        if not isinstance(subject_name, str) or not subject_name.strip():
            subject_name = 'General'
        subject_name = subject_name.strip()[:100]
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
        
        task = Task(
            user_id=current_user.id,
            subject_id=subject.id,
            title=title,
            priority=priority,
            status='Pending',
            estimated_minutes=estimated_minutes
        )
        db.session.add(task)
        created_count += 1
    
    db.session.commit()
    flash(f'{created_count} task(s) created from document analysis!', 'success')
    return redirect(url_for('tasks.index'))
