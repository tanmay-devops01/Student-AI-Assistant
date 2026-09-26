"""
AI Service Layer - Abstracts AI provider for easy swapping.
Supports structured outputs for task extraction and study plan generation.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional

from flask import current_app


class AIService:
    """
    AI Service that provides an abstraction layer for AI providers.
    Currently supports OpenAI, but designed to be easily extended.
    """

    def __init__(self):
        self.api_key = os.environ.get('AI_API_KEY', '')
        self.model = os.environ.get('AI_MODEL', 'gpt-4o-mini')
        self.provider = os.environ.get('AI_PROVIDER', 'openai')
        self.base_url = os.environ.get('AI_BASE_URL', '')

    def is_available(self) -> bool:
        """Check if AI service is configured and available."""
        return bool(self.api_key and self.api_key.strip())

    def _get_client(self):
        """Get the AI client based on provider."""
        if self.provider == 'openai':
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                if self.base_url:
                    client.base_url = self.base_url
                return client
            except ImportError:
                current_app.logger.error("OpenAI package not installed")
                return None
        return None

    def generate_study_plan(self, user_input: str, user_tasks: List[Dict]) -> Dict[str, Any]:
        """
        Generate a structured study plan based on user input and existing tasks.
        
        Args:
            user_input: Natural language description of study needs
            user_tasks: List of existing task dictionaries
            
        Returns:
            Structured study plan dictionary
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not configured. Please set AI_API_KEY in your environment.',
                'plan': None
            }

        client = self._get_client()
        if not client:
            return {
                'success': False,
                'error': 'Failed to initialize AI client',
                'plan': None
            }

        try:
            # Prepare context from existing tasks
            tasks_context = ""
            if user_tasks:
                tasks_context = "\n\nYour existing tasks:\n"
                for task in user_tasks[:10]:  # Limit to avoid token overflow
                    deadline = task.get('deadline', 'No deadline')
                    tasks_context += f"- {task['title']} ({task.get('subject', 'General')}) - Due: {deadline}\n"

            prompt = f"""
You are a helpful study planner assistant. Generate a structured study plan based on the user's request.

User request: {user_input}
{tasks_context}

Respond with a valid JSON object in this exact format:
{{
  "plan": {{
    "days": [
      {{
        "day": "Monday",
        "activities": [
          {{
            "task": "Activity description",
            "subject": "Subject name",
            "duration_minutes": 60,
            "focus": "study/practice/review"
          }}
        ]
      }}
    ],
    "total_hours": 10,
    "tips": ["Study tip 1", "Study tip 2"]
  }},
  "confidence": "high/medium/low"
}}

Rules:
- Create a realistic, actionable study plan
- Distribute work across days reasonably
- Include breaks between study sessions
- Focus on high-priority items first
- Estimate durations realistically
- The JSON must be valid and parseable
- Do not include any text outside the JSON object
"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a structured study plan generator. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            response_text = response.choices[0].message.content
            
            # Extract JSON from response (handle markdown code blocks)
            json_str = self._extract_json(response_text)
            
            if json_str:
                plan_data = json.loads(json_str)
                return {
                    'success': True,
                    'plan': plan_data.get('plan', {}),
                    'confidence': plan_data.get('confidence', 'medium'),
                    'raw_response': response_text
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to parse AI response as JSON',
                    'plan': None,
                    'raw_response': response_text
                }

        except Exception as e:
            current_app.logger.error(f"AI study plan generation error: {str(e)}")
            return {
                'success': False,
                'error': f'AI service error: {str(e)}',
                'plan': None
            }

    def extract_tasks_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract structured tasks from natural language text.
        
        Args:
            text: Natural language description of tasks
            
        Returns:
            Dictionary with extracted tasks
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not configured. Please set AI_API_KEY in your environment.',
                'tasks': []
            }

        client = self._get_client()
        if not client:
            return {
                'success': False,
                'error': 'Failed to initialize AI client',
                'tasks': []
            }

        try:
            prompt = f"""
Extract tasks from the following text. Identify task title, subject, priority, deadline, and estimated duration.

Text: {text}

Respond with a valid JSON object in this exact format:
{{
  "tasks": [
    {{
      "title": "Task title",
      "subject": "Subject name",
      "priority": "low/medium/high",
      "deadline": "YYYY-MM-DD or null",
      "estimated_minutes": 60
    }}
  ]
}}

Rules:
- Extract all identifiable tasks
- If no specific deadline is mentioned, set deadline to null
- Use reasonable duration estimates based on task type
- Priority: "high" for urgent/deadline tasks, "medium" for regular assignments, "low" for optional work
- The JSON must be valid and parseable
- Do not include any text outside the JSON object
- Do not add explanations
"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a task extraction assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1500
            )

            response_text = response.choices[0].message.content
            json_str = self._extract_json(response_text)
            
            if json_str:
                data = json.loads(json_str)
                tasks = data.get('tasks', [])
                
                # Validate each task
                validated_tasks = []
                for task in (tasks if isinstance(tasks, list) else []):
                    validated = self._validate_task(task)
                    if validated:
                        validated_tasks.append(validated)
                
                return {
                    'success': True,
                    'tasks': validated_tasks,
                    'raw_response': response_text
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to parse AI response as JSON',
                    'tasks': [],
                    'raw_response': response_text
                }

        except Exception as e:
            current_app.logger.error(f"Task extraction error: {str(e)}")
            return {
                'success': False,
                'error': f'AI service error: {str(e)}',
                'tasks': []
            }

    def analyze_document(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Analyze a document and extract key information.
        
        Args:
            text: Extracted text from the document
            filename: Original filename
            
        Returns:
            Dictionary with document analysis
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not configured',
                'summary': None,
                'requirements': [],
                'difficulty': 'Unknown',
                'estimated_minutes': None,
                'suggested_tasks': [],
                'recommendations': []
            }

        client = self._get_client()
        if not client:
            return {
                'success': False,
                'error': 'Failed to initialize AI client',
                'summary': None
            }

        try:
            # Limit text length to avoid token overflow
            text_for_analysis = text[:8000] if len(text) > 8000 else text
            
            prompt = f"""
Analyze this academic document and provide a structured analysis.

Document filename: {filename}

Document content:
{text_for_analysis}

Respond with a valid JSON object in this exact format:
{{
  "summary": "Brief 2-3 sentence summary of the document",
  "requirements": ["Requirement 1", "Requirement 2", "Requirement 3"],
  "difficulty": "easy/medium/hard",
  "estimated_minutes": 120,
  "suggested_tasks": [
    {{
      "title": "Suggested subtask",
      "priority": "medium",
      "estimated_minutes": 30
    }}
  ],
  "recommendations": ["Study tip 1", "Study tip 2"]
}}

Rules:
- Be concise but accurate
- difficulty should be based on content complexity
- suggested_tasks should be actionable subtasks
- Do not include any text outside the JSON object
"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a document analysis assistant. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=2000
            )

            response_text = response.choices[0].message.content
            json_str = self._extract_json(response_text)
            
            if json_str:
                return json.loads(json_str)
            else:
                return {
                    'success': False,
                    'error': 'Failed to parse AI response',
                    'raw_response': response_text
                }

        except Exception as e:
            current_app.logger.error(f"Document analysis error: {str(e)}")
            return {
                'success': False,
                'error': f'AI service error: {str(e)}',
                'summary': None
            }

    def generate_daily_summary(self, tasks: List[Dict], completed_today: int) -> Dict[str, Any]:
        """
        Generate a personalized daily study summary and recommendations.
        
        Args:
            tasks: List of task dictionaries for today
            completed_today: Number of tasks completed today
            
        Returns:
            Dictionary with summary and recommendations
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'AI service not configured',
                'summary': None,
                'recommendations': []
            }

        client = self._get_client()
        if not client:
            return {
                'success': False,
                'error': 'Failed to initialize AI client',
                'summary': None
            }

        try:
            tasks_summary = ""
            for task in tasks[:5]:
                status = task.get('status', 'Unknown')
                tasks_summary += f"- {task['title']} ({status})\n"

            prompt = f"""
Generate a brief, encouraging daily study summary and 2-3 actionable recommendations.

Today's tasks:
{tasks_summary}

Tasks completed today: {completed_today}

Respond with valid JSON:
{{
  "summary": "Encouraging 2-3 sentence summary of today's progress",
  "recommendations": ["Recommendation 1", "Recommendation 2", "Recommendation 3"]
}}
"""

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a supportive study coach. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            response_text = response.choices[0].message.content
            json_str = self._extract_json(response_text)
            
            if json_str:
                return json.loads(json_str)
            else:
                return {
                    'success': False,
                    'error': 'Failed to parse AI response',
                    'summary': f"You completed {completed_today} tasks today. Keep up the good work!",
                    'recommendations': ["Review your pending tasks", "Plan tomorrow's study session"]
                }

        except Exception as e:
            current_app.logger.error(f"Daily summary generation error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'summary': f"You completed {completed_today} tasks today.",
                'recommendations': []
            }

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text that may contain markdown or other formatting."""
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Try to find JSON object directly
        json_match = re.search(r'(\{.*"\w+"\s*:)', text)
        if json_match:
            # Find the complete JSON object
            start = json_match.start()
            brace_count = 0
            end = start
            for i in range(start, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            if end > start:
                return text[start:end]
        
        # Try parsing the whole response as JSON
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        
        return None

    def _validate_task(self, task: Dict) -> Optional[Dict]:
        """Validate and sanitize an AI-generated task."""
        if not isinstance(task, dict):
            return None
        # Required field
        if not task.get('title') or not isinstance(task['title'], str):
            return None
        
        # Sanitize title
        title = task['title'].strip()[:200]
        if not title:
            return None
        
        # Subject - default to 'General'
        subject = task.get('subject', 'General')
        if not isinstance(subject, str):
            subject = 'General'
        subject = subject.strip()[:100]
        
        # Priority - must be valid
        priority = task.get('priority', 'medium')
        priority = priority.lower() if isinstance(priority, str) else 'medium'
        if priority not in ['low', 'medium', 'high']:
            priority = 'medium'
        
        # Deadline - must be valid date or None
        deadline = task.get('deadline')
        if deadline and isinstance(deadline, str):
            # Validate date format
            try:
                from datetime import datetime
                datetime.strptime(deadline, '%Y-%m-%d')
            except ValueError:
                deadline = None
        else:
            deadline = None
        
        # Estimated minutes - must be positive integer
        estimated_minutes = task.get('estimated_minutes', 60)
        if not isinstance(estimated_minutes, (int, float)) or estimated_minutes <= 0 or estimated_minutes > 1440:
            estimated_minutes = 60
        estimated_minutes = int(estimated_minutes)
        
        return {
            'title': title,
            'subject': subject,
            'priority': priority,
            'deadline': deadline,
            'estimated_minutes': estimated_minutes
        }


# Singleton instance
ai_service = AIService()
