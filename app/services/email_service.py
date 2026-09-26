"""
Email Service - Handles sending emails via SMTP.
Configured through environment variables.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from flask import current_app


class EmailService:
    """
    Email service for sending notifications, reminders, and summaries.
    Uses SMTP configuration from environment variables.
    """

    def __init__(self):
        self.server = os.environ.get('MAIL_SERVER', '')
        self.port = int(os.environ.get('MAIL_PORT', '587'))
        self.username = os.environ.get('MAIL_USERNAME', '')
        self.password = os.environ.get('MAIL_PASSWORD', '')
        self.use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        self.from_address = os.environ.get('MAIL_FROM', self.username)

    def is_configured(self) -> bool:
        """Check if email is properly configured."""
        return all([
            self.server,
            self.username,
            self.password,
            self.from_address
        ])

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            
        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.is_configured():
            current_app.logger.warning(
                f"Email not configured. Cannot send to {to_address}"
            )
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_address
            msg['To'] = to_address

            # Attach plain text
            msg.attach(MIMEText(body, 'plain'))

            # Attach HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, 'html'))

            # Connect and send
            if self.use_tls:
                server = smtplib.SMTP(self.server, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.server, self.port)

            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()

            current_app.logger.info(f"Email sent to {to_address}: {subject}")
            return True

        except Exception as e:
            current_app.logger.error(f"Failed to send email to {to_address}: {str(e)}")
            return False

    def send_deadline_reminder(
        self,
        user_email: str,
        user_name: str,
        task_title: str,
        deadline: str,
        hours_remaining: int
    ) -> bool:
        """Send an upcoming deadline reminder."""
        subject = f"📚 Upcoming Deadline: {task_title}"
        
        body = f"""Hi {user_name},

This is a reminder that you have an upcoming deadline:

Task: {task_title}
Deadline: {deadline}
Time remaining: {hours_remaining} hours

Please make sure to complete this on time!

Best regards,
Student AI Assistant
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
  <h2>📚 Upcoming Deadline</h2>
  <p>Hi {user_name},</p>
  <p>This is a reminder that you have an upcoming deadline:</p>
  <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
    <p><strong>Task:</strong> {task_title}</p>
    <p><strong>Deadline:</strong> {deadline}</p>
    <p><strong>Time remaining:</strong> {hours_remaining} hours</p>
  </div>
  <p>Please make sure to complete this on time!</p>
  <p>Best regards,<br>Student AI Assistant</p>
</body>
</html>
"""
        
        return self.send_email(user_email, subject, body, html_body)

    def send_overdue_notification(
        self,
        user_email: str,
        user_name: str,
        task_title: str,
        deadline: str
    ) -> bool:
        """Send an overdue task notification."""
        subject = f"⚠️ Overdue: {task_title}"
        
        body = f"""Hi {user_name},

This is a notification that the following task is now overdue:

Task: {task_title}
Deadline: {deadline}

Please address this as soon as possible.

Best regards,
Student AI Assistant
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
  <h2>⚠️ Overdue Task</h2>
  <p>Hi {user_name},</p>
  <p>This is a notification that the following task is now overdue:</p>
  <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0; border-left: 4px solid #ffc107;">
    <p><strong>Task:</strong> {task_title}</p>
    <p><strong>Deadline:</strong> {deadline}</p>
  </div>
  <p>Please address this as soon as possible.</p>
  <p>Best regards,<br>Student AI Assistant</p>
</body>
</html>
"""
        
        return self.send_email(user_email, subject, body, html_body)

    def send_daily_summary(
        self,
        user_email: str,
        user_name: str,
        summary: str,
        tasks_today: List[dict],
        completed_today: int,
        upcoming_deadlines: List[dict]
    ) -> bool:
        """Send a daily study summary."""
        subject = f"📊 Your Daily Study Summary - {self._get_today_date()}"
        
        tasks_list = "".join([
            f"<li>{task['title']} - {task.get('status', 'Pending')}</li>"
            for task in tasks_today
        ]) if tasks_today else "<li>No tasks scheduled for today</li>"

        deadlines_list = "".join([
            f"<li>{deadline['title']} - Due: {deadline['deadline']}</li>"
            for deadline in upcoming_deadlines[:3]
        ]) if upcoming_deadlines else "<li>No upcoming deadlines</li>"

        body = f"""Hi {user_name},

Here's your daily study summary:

{summary}

Today's Tasks:
{chr(10).join(['- ' + t['title'] + ' (' + t.get('status', 'Pending') + ')' for t in tasks_today]) or 'No tasks for today'}

Completed Today: {completed_today}

Upcoming Deadlines:
{chr(10).join(['- ' + d['title'] + ' - Due: ' + d['deadline'] for d in upcoming_deadlines[:3]]) or 'No upcoming deadlines'}

Keep up the good work!

Best regards,
Student AI Assistant
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
  <h2>📊 Daily Study Summary</h2>
  <p>Hi {user_name},</p>
  <p>{summary}</p>
  
  <div style="margin: 20px 0;">
    <h3>Today's Tasks ({len(tasks_today)})</h3>
    <ul>
      {tasks_list}
    </ul>
  </div>
  
  <div style="margin: 20px 0;">
    <h3>Completed Today: {completed_today}</h3>
  </div>
  
  <div style="margin: 20px 0;">
    <h3>Upcoming Deadlines</h3>
    <ul>
      {deadlines_list}
    </ul>
  </div>
  
  <p>Keep up the good work!</p>
  <p>Best regards,<br>Student AI Assistant</p>
</body>
</html>
"""
        
        return self.send_email(user_email, subject, body, html_body)

    def send_weekly_report(
        self,
        user_email: str,
        user_name: str,
        report_data: dict
    ) -> bool:
        """Send a weekly progress report."""
        subject = f"📈 Weekly Progress Report - {self._get_week_range()}"
        
        completion_rate = report_data.get('completion_percentage', 0)
        completed_this_week = report_data.get('completed_this_week', 0)
        created_this_week = report_data.get('created_this_week', 0)
        
        body = f"""Hi {user_name},

Here's your weekly progress report:

Completion Rate: {completion_rate:.1f}%
Tasks Completed This Week: {completed_this_week}
Tasks Created This Week: {created_this_week}

Great job staying on track!

Best regards,
Student AI Assistant
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
  <h2>📈 Weekly Progress Report</h2>
  <p>Hi {user_name},</p>
  
  <div style="background: #e7f3ff; padding: 20px; border-radius: 8px; margin: 20px 0;">
    <div style="display: flex; justify-content: space-around; text-align: center;">
      <div>
        <div style="font-size: 24px; font-weight: bold; color: #0d6efd;">{completion_rate:.1f}%</div>
        <div style="color: #666;">Completion Rate</div>
      </div>
      <div>
        <div style="font-size: 24px; font-weight: bold; color: #198754;">{completed_this_week}</div>
        <div style="color: #666;">Completed</div>
      </div>
      <div>
        <div style="font-size: 24px; font-weight: bold; color: #fd7e14;">{created_this_week}</div>
        <div style="color: #666;">Created</div>
      </div>
    </div>
  </div>
  
  <p>Great job staying on track!</p>
  <p>Best regards,<br>Student AI Assistant</p>
</body>
</html>
"""
        
        return self.send_email(user_email, subject, body, html_body)

    def _get_today_date(self) -> str:
        """Get today's date in readable format."""
        from datetime import datetime
        return datetime.now().strftime('%B %d, %Y')

    def _get_week_range(self) -> str:
        """Get current week range."""
        from datetime import datetime, timedelta
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"


# Singleton instance
email_service = EmailService()
