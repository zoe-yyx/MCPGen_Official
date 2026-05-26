"""AI tools: CV data extraction, qualification assessment, email generation.

Uses OpenAI GPT for all three AI-powered steps in the recruitment pipeline.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .utils.log_decorator import log_mcp_call

load_dotenv()


def _get_client() -> tuple[OpenAI, str]:
    """Create OpenAI client and return (client, model)."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "ENDPOINT_PLACEHOLDER")
    model = os.getenv("MODEL", "gpt-5.1")
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


@log_mcp_call("tool", "extract_cv_data")
def extract_cv_data(cv_text: str) -> str:
    """Extract structured data from CV text using GPT.

    Args:
        cv_text: Raw text content of the CV.

    Returns:
        JSON string with extracted fields: skills, education,
        years_experience, summary.
    """
    client, model = _get_client()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a CV parsing assistant. Extract structured information "
                    "from the CV text. Return ONLY valid JSON with these fields:\n"
                    '{"skills": ["skill1", "skill2", ...], '
                    '"education": "highest degree and institution", '
                    '"years_experience": number, '
                    '"summary": "2-3 sentence professional summary"}'
                ),
            },
            {"role": "user", "content": cv_text},
        ],
        max_tokens=500,
        temperature=0.2,
    )

    raw = response.choices[0].message.content or "{}"
    # Try to parse JSON from response
    try:
        # Strip markdown code block if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {
            "skills": [],
            "education": "Unknown",
            "years_experience": 0,
            "summary": raw,
        }

    return json.dumps(data)


@log_mcp_call("tool", "assess_qualification")
def assess_qualification(cv_data: str, job_requirements: str) -> str:
    """AI assessment of candidate qualification against job requirements.

    Args:
        cv_data: JSON string with extracted CV data (skills, education, etc.).
        job_requirements: JSON string with job requirements (Position, Required_Skills, etc.).

    Returns:
        JSON string with: match_score, status, strengths, gaps, recommendation, reasoning.
    """
    cv = json.loads(cv_data)
    job = json.loads(job_requirements)

    client, model = _get_client()

    prompt = (
        "You are a recruitment AI assistant. Analyze if this candidate matches the job requirements.\n\n"
        f"Candidate Profile:\n"
        f"Skills: {', '.join(cv.get('skills', []))}\n"
        f"Education: {cv.get('education', 'N/A')}\n"
        f"Years of Experience: {cv.get('years_experience', 0)}\n"
        f"Summary: {cv.get('summary', 'N/A')}\n\n"
        f"Job Requirements:\n"
        f"- Position: {job.get('Position', 'N/A')}\n"
        f"- Required Experience: {job.get('Required_Experience', 0)} years\n"
        f"- Required Skills: {job.get('Required_Skills', 'N/A')}\n"
        f"- Education Required: {job.get('Education_Required', 'N/A')}\n"
        f"- Nice to Have: {job.get('Nice_To_Have', 'N/A')}\n\n"
        "Provide:\n"
        "1. Match Score (0-100)\n"
        "2. Qualification Status (Highly Qualified / Qualified / Potentially Qualified / Not Qualified)\n"
        "3. Strengths (3 key points)\n"
        "4. Gaps (areas where candidate doesn't meet requirements)\n"
        "5. Recommendation (Interview / Phone Screen / Reject)\n\n"
        'Return ONLY valid JSON: {"match_score": number, "status": string, '
        '"strengths": ["str"], "gaps": ["str"], "recommendation": string, "reasoning": string}'
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert recruitment AI that provides objective, fair candidate assessments. Return ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
        temperature=0.3,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {
            "match_score": 50,
            "status": "Potentially Qualified",
            "strengths": ["Unable to parse AI response"],
            "gaps": ["Assessment parsing error"],
            "recommendation": "Phone Screen",
            "reasoning": raw,
        }

    return json.dumps(data)


@log_mcp_call("tool", "generate_recruitment_email")
def generate_recruitment_email(
    candidate_name: str,
    position: str,
    match_score: int,
    status: str,
    recommendation: str,
    strengths: str,
) -> str:
    """Generate a personalized recruitment email for the candidate using GPT.

    Args:
        candidate_name: Full name of the candidate.
        position: Position applied for.
        match_score: AI match score.
        status: Qualification status.
        recommendation: Interview / Phone Screen.
        strengths: Comma-separated key strengths.

    Returns:
        JSON string with 'subject' and 'body' fields.
    """
    next_step = (
        "Invite them for a formal interview"
        if recommendation == "Interview"
        else "Suggest a preliminary phone screening"
    )

    client, model = _get_client()

    prompt = (
        f"Generate a personalized recruitment email for this candidate.\n\n"
        f"Candidate: {candidate_name}\n"
        f"Position: {position}\n"
        f"Match Score: {match_score}\n"
        f"Status: {status}\n"
        f"Recommendation: {recommendation}\n\n"
        f"Key Strengths:\n{strengths}\n\n"
        f"Email should:\n"
        f"- Be professional and warm\n"
        f"- Congratulate them on their application\n"
        f"- Mention 1-2 specific strengths that stood out\n"
        f"- {next_step}\n"
        f"- Include next steps\n"
        f"- Be concise (150-200 words)\n\n"
        f'Return ONLY valid JSON: {{"subject": "email subject", "body": "email body text"}}'
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a professional recruitment communications specialist. Write engaging, personalized emails. Return ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=500,
        temperature=0.7,
    )

    raw = response.choices[0].message.content or "{}"
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {"subject": f"Re: Your Application for {position}", "body": raw}

    return json.dumps(data)
