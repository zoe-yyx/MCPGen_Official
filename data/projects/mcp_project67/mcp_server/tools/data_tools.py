"""Data tools: webhook input, Airtable CRUD, CV download (all mocked).

Simulates Webhook, Airtable, and HTTP Request nodes from the n8n workflow.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from .utils.log_decorator import log_mcp_call

# Mock local storage for Airtable records
_CANDIDATES_DB: dict[str, dict] = {}

# Mock job requirements data
MOCK_JOB_REQUIREMENTS = {
    "Software Engineer": {
        "Position": "Software Engineer",
        "Required_Experience": 3,
        "Required_Skills": "Python, JavaScript, SQL, REST APIs, Git",
        "Education_Required": "Bachelor's in Computer Science or related field",
        "Nice_To_Have": "Docker, Kubernetes, AWS, CI/CD, system design experience",
        "Active": True,
    },
    "Data Scientist": {
        "Position": "Data Scientist",
        "Required_Experience": 2,
        "Required_Skills": "Python, Machine Learning, Statistics, SQL, TensorFlow/PyTorch",
        "Education_Required": "Master's in Data Science, Statistics, or related field",
        "Nice_To_Have": "NLP, Deep Learning, Spark, cloud ML platforms",
        "Active": True,
    },
    "Product Manager": {
        "Position": "Product Manager",
        "Required_Experience": 4,
        "Required_Skills": "Product strategy, Agile, user research, data analysis, roadmapping",
        "Education_Required": "Bachelor's degree in any field",
        "Nice_To_Have": "MBA, technical background, B2B SaaS experience",
        "Active": True,
    },
}

# Mock CV content
MOCK_CV_CONTENT = (
    "CURRICULUM VITAE\n\n"
    "Education: Master of Science in Computer Science, Stanford University (2020-2022)\n"
    "Bachelor of Science in Software Engineering, UC Berkeley (2016-2020)\n\n"
    "Experience:\n"
    "- Senior Software Engineer at TechCorp (2022-Present): Led backend team of 5, "
    "designed microservices architecture, improved API response time by 40%.\n"
    "- Software Engineer at StartupXYZ (2020-2022): Built RESTful APIs using Python/FastAPI, "
    "implemented CI/CD pipelines with GitHub Actions.\n\n"
    "Skills: Python, JavaScript, TypeScript, Go, SQL, PostgreSQL, Redis, Docker, "
    "Kubernetes, AWS, GCP, REST APIs, GraphQL, Git, CI/CD, System Design\n\n"
    "Certifications: AWS Solutions Architect Associate, Kubernetes Administrator"
)


@log_mcp_call("tool", "receive_cv")
def receive_cv(name: str, email: str, phone: str, cv_url: str, position: str) -> str:
    """Simulate receiving a CV submission via webhook (POST).

    Args:
        name: Candidate full name.
        email: Candidate email address.
        phone: Candidate phone number.
        cv_url: URL to the candidate's CV document.
        position: Position the candidate is applying for.

    Returns:
        JSON string with the webhook body data.
    """
    return json.dumps({
        "body": {
            "name": name,
            "email": email,
            "phone": phone,
            "cv_url": cv_url,
            "position": position,
        }
    })


@log_mcp_call("tool", "store_candidate")
def store_candidate(name: str, email: str, phone: str, cv_url: str, position: str) -> str:
    """Store candidate record in Airtable (mocked to local dict).

    Args:
        name: Candidate full name.
        email: Candidate email address.
        phone: Candidate phone number.
        cv_url: URL to the CV.
        position: Position applied for.

    Returns:
        JSON string with the created Airtable record including generated ID.
    """
    record_id = f"rec{uuid.uuid4().hex[:12]}"
    record = {
        "id": record_id,
        "Name": name,
        "Email": email,
        "Phone": phone,
        "CV_URL": cv_url,
        "Status": "New Application",
        "Application_Date": datetime.now(timezone.utc).isoformat(),
        "Position_Applied": position,
    }
    _CANDIDATES_DB[record_id] = record
    return json.dumps(record)


@log_mcp_call("tool", "get_job_requirements")
def get_job_requirements(position: str) -> str:
    """Fetch job requirements from Airtable by position name (mocked).

    Args:
        position: The job position to look up requirements for.

    Returns:
        JSON string with job requirements fields.
    """
    req = MOCK_JOB_REQUIREMENTS.get(position)
    if not req:
        # Default fallback
        req = MOCK_JOB_REQUIREMENTS.get("Software Engineer", {})
    return json.dumps(req)


@log_mcp_call("tool", "download_cv")
def download_cv(cv_url: str) -> str:
    """Download CV content from URL (mocked with sample CV text).

    Args:
        cv_url: URL to the CV document.

    Returns:
        JSON string with 'text' field containing CV content.
    """
    return json.dumps({"text": MOCK_CV_CONTENT, "source_url": cv_url})


@log_mcp_call("tool", "update_assessment")
def update_assessment(
    candidate_id: str,
    match_score: int,
    status: str,
    recommendation: str,
    strengths: str,
    gaps: str,
    reasoning: str,
    skills: str,
    education: str,
    years_experience: int,
) -> str:
    """Update candidate record in Airtable with AI assessment results (mocked).

    Args:
        candidate_id: Airtable record ID of the candidate.
        match_score: AI-computed match score (0-100).
        status: Qualification status.
        recommendation: Interview / Phone Screen / Reject.
        strengths: Comma-separated key strengths.
        gaps: Comma-separated gaps.
        reasoning: AI reasoning text.
        skills: Extracted skills from CV.
        education: Extracted education from CV.
        years_experience: Extracted years of experience.

    Returns:
        JSON string with the updated record.
    """
    if candidate_id in _CANDIDATES_DB:
        _CANDIDATES_DB[candidate_id].update({
            "Match_Score": match_score,
            "Qualification_Status": status,
            "AI_Recommendation": recommendation,
            "AI_Strengths": strengths,
            "AI_Gaps": gaps,
            "AI_Reasoning": reasoning,
            "Skills": skills,
            "Education": education,
            "Years_Experience": years_experience,
            "Status": "Rejected" if recommendation == "Reject" else "Qualified",
        })
        return json.dumps(_CANDIDATES_DB[candidate_id])

    # If not found, return a mock update confirmation
    return json.dumps({
        "id": candidate_id,
        "Match_Score": match_score,
        "Status": "Rejected" if recommendation == "Reject" else "Qualified",
        "AI_Recommendation": recommendation,
        "updated": True,
    })


@log_mcp_call("tool", "update_interview_details")
def update_interview_details(
    candidate_id: str,
    interview_scheduled: str,
    interview_link: str,
    calendar_event_id: str,
) -> str:
    """Update candidate record with interview scheduling details (mocked).

    Args:
        candidate_id: Airtable record ID.
        interview_scheduled: Interview date/time ISO string.
        interview_link: Google Meet/Hangout link.
        calendar_event_id: Google Calendar event ID.

    Returns:
        JSON string with the updated record.
    """
    if candidate_id in _CANDIDATES_DB:
        _CANDIDATES_DB[candidate_id].update({
            "Status": "Interview Scheduled",
            "Interview_Scheduled": interview_scheduled,
            "Interview_Link": interview_link,
            "Calendar_Event_ID": calendar_event_id,
        })
        return json.dumps(_CANDIDATES_DB[candidate_id])

    return json.dumps({
        "id": candidate_id,
        "Status": "Interview Scheduled",
        "Interview_Scheduled": interview_scheduled,
        "Interview_Link": interview_link,
        "updated": True,
    })
