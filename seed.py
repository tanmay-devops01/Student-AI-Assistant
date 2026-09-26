#!/usr/bin/env python3
"""
Seed script for Student AI Assistant.
Creates sample data for demonstration purposes.
"""

import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.subject import Subject
from app.models.task import Task


def seed_database():
    """Create sample data for demonstration."""
    app = create_app()
    
    with app.app_context():
        # Check if we already have data
        if User.query.first():
            print("Database already has data. Skipping seed.")
            return
        
        print("Seeding database with sample data...")

        # Create a demo user
        demo_user = User(
            name="Demo Student",
            email="demo@student.edu"
        )
        demo_user.set_password("demo123")
        db.session.add(demo_user)
        db.session.commit()  # Commit to get the user ID

        # Create subjects
        subjects_data = [
            {"name": "Python Programming", "description": "Introduction to Python programming language", "color": "#0d6efd"},
            {"name": "Database Management Systems", "description": "Relational databases and SQL", "color": "#198754"},
            {"name": "Computer Networks", "description": "Network protocols and architecture", "color": "#fd7e14"},
            {"name": "Artificial Intelligence", "description": "Machine learning and AI fundamentals", "color": "#dc3545"},
            {"name": "Data Structures", "description": "Algorithms and data structures", "color": "#6f42c1"},
        ]
        
        subjects = []
        for subj_data in subjects_data:
            subject = Subject(
                user_id=demo_user.id,
                name=subj_data["name"],
                description=subj_data["description"],
                color=subj_data["color"]
            )
            db.session.add(subject)
            subjects.append(subject)
        
        db.session.flush()  # Get subject IDs
        
        # Create tasks
        now = datetime.utcnow()
        tasks_data = [
            {
                "title": "Complete Python Assignment - Functions",
                "description": "Write functions for list operations and recursion problems",
                "subject": subjects[0],
                "priority": "High",
                "status": "Pending",
                "deadline": now + timedelta(days=3),
                "estimated_minutes": 180
            },
            {
                "title": "DBMS Normalization Exercise",
                "description": "Normalize the given schema to 3NF",
                "subject": subjects[1],
                "priority": "High",
                "status": "In Progress",
                "deadline": now + timedelta(days=2),
                "estimated_minutes": 120
            },
            {
                "title": "CN Unit Test Preparation",
                "description": "Study for Computer Networks unit test covering TCP/IP",
                "subject": subjects[2],
                "priority": "Medium",
                "status": "Pending",
                "deadline": now + timedelta(days=5),
                "estimated_minutes": 90
            },
            {
                "title": "AI Project - Neural Networks",
                "description": "Implement a simple neural network from scratch",
                "subject": subjects[3],
                "priority": "High",
                "status": "Pending",
                "deadline": now + timedelta(days=7),
                "estimated_minutes": 240
            },
            {
                "title": "Data Structures - Tree Implementation",
                "description": "Implement binary search tree with traversal methods",
                "subject": subjects[4],
                "priority": "Medium",
                "status": "Pending",
                "deadline": now + timedelta(days=4),
                "estimated_minutes": 150
            },
            {
                "title": "Review Python Basics",
                "description": "Review variables, loops, and functions",
                "subject": subjects[0],
                "priority": "Low",
                "status": "Completed",
                "deadline": now - timedelta(days=2),
                "estimated_minutes": 60,
                "completed_at": now - timedelta(days=1)
            },
            {
                "title": "SQL Practice Queries",
                "description": "Write complex SQL queries with joins and subqueries",
                "subject": subjects[1],
                "priority": "Medium",
                "status": "Completed",
                "deadline": now - timedelta(days=3),
                "estimated_minutes": 90,
                "completed_at": now - timedelta(days=2)
            },
            {
                "title": "Read Chapter 5 - AI Ethics",
                "description": "Read and take notes on AI ethics chapter",
                "subject": subjects[3],
                "priority": "Low",
                "status": "Pending",
                "deadline": now + timedelta(days=10),
                "estimated_minutes": 45
            },
        ]
        
        for task_data in tasks_data:
            task = Task(
                user_id=demo_user.id,
                subject_id=task_data["subject"].id,
                title=task_data["title"],
                description=task_data["description"],
                priority=task_data["priority"],
                status=task_data["status"],
                deadline=task_data["deadline"],
                estimated_minutes=task_data["estimated_minutes"],
                completed_at=task_data.get("completed_at")
            )
            db.session.add(task)
        
        db.session.commit()
        print("Sample data created successfully!")
        print(f"Created user: {demo_user.email}")
        print(f"Created {len(subjects)} subjects")
        print(f"Created {len(tasks_data)} tasks")
        print("\nLogin with: demo@student.edu / demo123")


if __name__ == "__main__":
    seed_database()
