"""Email parsing and job application extraction."""

import html
import json
import logging
import os
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Optional

import requests

from .gmail_client import get_email_body, get_email_headers
from .models import JobApplication

logger = logging.getLogger(__name__)

# Common tech job titles for matching
TECH_JOB_TITLES = [
    # Engineering
    "Software Engineer",
    "Software Developer",
    "Frontend Engineer",
    "Frontend Developer",
    "Backend Engineer",
    "Backend Developer",
    "Full Stack Engineer",
    "Full Stack Developer",
    "Mobile Engineer",
    "Mobile Developer",
    "iOS Developer",
    "iOS Engineer",
    "Android Developer",
    "Android Engineer",
    "DevOps Engineer",
    "Site Reliability Engineer",
    "SRE",
    "Platform Engineer",
    "Infrastructure Engineer",
    "Cloud Engineer",
    "Systems Engineer",
    "Embedded Engineer",
    "Firmware Engineer",
    "Security Engineer",
    "Machine Learning Engineer",
    "ML Engineer",
    "AI Engineer",
    "Data Engineer",
    "QA Engineer",
    "Test Engineer",
    "SDET",
    "Solutions Engineer",
    "Sales Engineer",
    "Support Engineer",
    "Application Engineer",
    "Research Engineer",
    "Robotics Engineer",
    "Hardware Engineer",
    "Network Engineer",
    # Science & Analysis
    "Data Scientist",
    "Research Scientist",
    "Applied Scientist",
    "Machine Learning Scientist",
    "Data Analyst",
    "Business Analyst",
    "Product Analyst",
    "Quantitative Analyst",
    "Business Intelligence Analyst",
    # Product & Design
    "Product Manager",
    "Technical Product Manager",
    "Product Designer",
    "UX Designer",
    "UI Designer",
    "UX Researcher",
    "Graphic Designer",
    # Management
    "Engineering Manager",
    "Technical Program Manager",
    "Program Manager",
    "Project Manager",
    "Scrum Master",
    "Tech Lead",
    "Team Lead",
    "Director of Engineering",
    "VP of Engineering",
    "CTO",
    # Other
    "Technical Writer",
    "Developer Advocate",
    "Developer Relations",
    "IT Specialist",
    "System Administrator",
    "Database Administrator",
    "DBA",
    "Consultant",
    "Architect",
    "Solutions Architect",
    "Software Architect",
    "Enterprise Architect",
]

# Levels/modifiers that can appear with titles
JOB_LEVELS = [
    "Intern",
    "Internship",
    "Co-op",
    "Coop",
    "Junior",
    "Associate",
    "Entry Level",
    "Mid-Level",
    "Senior",
    "Staff",
    "Principal",
    "Lead",
    "Manager",
    "Director",
    "VP",
    "Head of",
    "Chief",
    "I",
    "II",
    "III",
    "IV",
    "V",
    "1",
    "2",
    "3",
    "4",
    "5",
]

# Teams/specializations
SPECIALIZATIONS = [
    "Frontend",
    "Backend",
    "Full Stack",
    "Fullstack",
    "Mobile",
    "iOS",
    "Android",
    "Web",
    "Cloud",
    "Infrastructure",
    "Platform",
    "Data",
    "ML",
    "AI",
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "Computer Vision",
    "Security",
    "DevOps",
    "SRE",
    "QA",
    "Test",
    "Automation",
    "Embedded",
    "Firmware",
    "Robotics",
    "Game",
    "Graphics",
    "Systems",
    "Distributed Systems",
    "Database",
    "Analytics",
    "Growth",
    "Payments",
    "Fintech",
]

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Phrases indicating rejection emails (check BEFORE confirmation)
REJECTION_INDICATORS = [
    "won't be moving forward",
    "will not be moving forward",
    "not be moving forward",
    "not moving forward",
    "decided not to proceed",
    "decided to move forward with other candidates",
    "moving forward with other candidates",
    "pursuing other candidates",
    "not be pursuing your",
    "unfortunately we have decided",
    "unfortunately, we have decided",
    "regret to inform",
    "not selected",
    "were not selected",
    "was not selected",
    "have not been selected",
    "has not been selected",
    "position has been filled",
    "role has been filled",
    "no longer considering",
    "will not be proceeding",
    "unable to offer you",
    "not able to offer you",
    "cannot offer you",
    "decided to pursue other",
    "chosen to pursue other",
    "after careful consideration",
    "not the right fit",
    "not a good fit",
    "wish you the best",
    "wish you every success",
    "good luck in your",
    "best of luck in your",
]

# Phrases indicating incomplete/started-but-not-submitted applications
INCOMPLETE_INDICATORS = [
    "incomplete",
    "not complete",
    "not yet complete",
    "finish your application",
    "complete your application",
    "resume your application",
    "continue your application",
    "started your application",
    "starting your application",
    "thanks for starting",
    "thank you for starting",
    "begin your application",
    "began your application",
    "application in progress",
    "application is pending",
    "draft application",
    "saved application",
    "unfinished application",
]


def strip_html(text: str) -> str:
    """Convert HTML to plain text."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()


def match_job_title(text: str) -> Optional[str]:
    """Try to match a known tech job title in the text."""
    text_lower = text.lower()

    # Build patterns combining levels, specializations, and base titles
    for base_title in TECH_JOB_TITLES:
        # Direct match
        pattern = r'\b' + re.escape(base_title) + r'\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Try to capture surrounding level/specialization
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 20)
            context = text[start:end]

            # Look for level prefix
            for level in JOB_LEVELS:
                level_pattern = rf'\b({re.escape(level)})\s+{re.escape(base_title)}\b'
                level_match = re.search(level_pattern, context, re.IGNORECASE)
                if level_match:
                    return f"{level} {base_title}"

            # Look for specialization prefix
            for spec in SPECIALIZATIONS:
                spec_pattern = rf'\b({re.escape(spec)})\s+{re.escape(base_title)}\b'
                spec_match = re.search(spec_pattern, context, re.IGNORECASE)
                if spec_match:
                    return f"{spec} {base_title}"

            return base_title

    # Try pattern: "[Level] [Specialization] [Role]"
    for level in JOB_LEVELS:
        for spec in SPECIALIZATIONS:
            pattern = rf'\b{re.escape(level)}\s+{re.escape(spec)}\s+(Engineer|Developer|Scientist|Analyst|Designer|Manager)\b'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"{level} {spec} {match.group(1)}"

    return None


def extract_company_from_email(text: str, headers: dict[str, str]) -> Optional[str]:
    """Extract company name using multiple strategies."""
    sender = headers.get("from", "")

    # Strategy 1: Common ATS patterns in sender
    ats_company_patterns = [
        r'"([^"]+)" via .+',  # "Company" via Greenhouse
        r'([A-Za-z0-9\s&.]+)\s+Careers?\s*<',
        r'([A-Za-z0-9\s&.]+)\s+Recruiting\s*<',
        r'([A-Za-z0-9\s&.]+)\s+Talent\s*<',
        r'([A-Za-z0-9\s&.]+)\s+Jobs?\s*<',
        r'([A-Za-z0-9\s&.]+)\s+HR\s*<',
    ]

    for pattern in ats_company_patterns:
        match = re.search(pattern, sender, re.IGNORECASE)
        if match:
            company = match.group(1).strip()
            if len(company) > 1 and len(company) < 50:
                return company

    # Strategy 2: Look for "at [Company]" or "to [Company]" patterns in text
    company_patterns = [
        r'(?:applying|applied|application)\s+(?:to|at|for(?:\s+a\s+position\s+at)?)\s+([A-Z][A-Za-z0-9\s&.\'-]+?)(?:\.|,|!|\s+for|\s+and|\s+as)',
        r'interest\s+in\s+(?:joining\s+)?([A-Z][A-Za-z0-9\s&.\'-]+?)(?:\.|,|!|\s+and)',
        r'Thank\s+you\s+for\s+applying\s+to\s+([A-Z][A-Za-z0-9\s&.\'-]+)',
        r'at\s+([A-Z][A-Za-z0-9\s&.\'-]+?)\s+for\s+the',
        r'with\s+([A-Z][A-Za-z0-9\s&.\'-]+?)\s+for\s+(?:the|our)',
    ]

    for pattern in company_patterns:
        match = re.search(pattern, text)
        if match:
            company = match.group(1).strip()
            # Filter out generic words
            if company.lower() not in ('the', 'our', 'a', 'an', 'this', 'your'):
                if len(company) > 1 and len(company) < 50:
                    return company

    # Strategy 3: Extract from sender name (fallback)
    sender_match = re.search(r'^([^<]+)<', sender)
    if sender_match:
        sender_name = sender_match.group(1).strip().strip('"')
        # Remove common suffixes
        sender_name = re.sub(r'\s+(Careers?|Recruiting|Talent|Jobs?|HR|Team|via\s+.+)$', '', sender_name, flags=re.IGNORECASE)
        if sender_name and len(sender_name) > 1 and sender_name.lower() not in (
            'jobs', 'careers', 'recruiting', 'hr', 'talent', 'no-reply', 'noreply', 'notifications'
        ):
            return sender_name

    # Strategy 4: Extract from email domain
    domain_match = re.search(r'@([a-zA-Z0-9.-]+)', sender)
    if domain_match:
        domain = domain_match.group(1)
        parts = domain.split('.')
        if len(parts) >= 2:
            company_part = parts[0]
            if company_part not in ('mail', 'email', 'jobs', 'careers', 'notifications', 'noreply', 'no-reply', 'talent'):
                return company_part.replace('-', ' ').title()

    return None


def extract_with_llm(text: str, subject: str, sender: str) -> Optional[dict]:
    """Use OpenRouter LLM to extract job application details."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.debug("OPENROUTER_API_KEY not set, skipping LLM extraction")
        return None

    # Truncate text to avoid token limits
    truncated_text = text[:3000] if len(text) > 3000 else text

    prompt = f"""Extract job application details from this confirmation email. Return ONLY valid JSON.

Rules:
- company: The actual company you applied to (NOT "LinkedIn" or "Indeed" - those are job platforms, extract the real company name)
- position: The job title (e.g. "Software Engineer Intern", "Data Analyst"). Look in the subject line and body.
- If this is NOT a job application confirmation (e.g. just a notification, newsletter, or job recommendation), return {{"company": null, "position": null}}

Email subject: {subject}
From: {sender}

Email body:
{truncated_text}

Return valid JSON only:
{{"company": "Company Name", "position": "Job Title"}}"""

    try:
        response = requests.post(
            OPENROUTER_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0,
            },
            timeout=10,
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON from response
        # Handle potential markdown code blocks
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()

        data = json.loads(content)

        # Handle case where LLM returns a list (multiple jobs in one email)
        if isinstance(data, list) and len(data) > 0:
            data = data[0]  # Take the first one

        logger.info(f"LLM extracted: {data}")
        return data

    except requests.RequestException as e:
        logger.warning(f"LLM API request failed: {e}")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")

    return None


def extract_date(text: str, headers: dict[str, str]) -> tuple[date, float]:
    """Extract application date from email."""
    date_patterns = [
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})",
        r"(\d{4}-\d{2}-\d{2})",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"):
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.date(), 0.8
                except ValueError:
                    continue

    # Fall back to email date header
    email_date = headers.get("date", "")
    if email_date:
        try:
            parsed = parsedate_to_datetime(email_date)
            return parsed.date(), 0.6
        except Exception:
            pass

    return date.today(), 0.3


def extract_source(headers: dict[str, str]) -> Optional[str]:
    """Extract ATS source from email headers."""
    sender = headers.get("from", "")
    domain_match = re.search(r"@([a-zA-Z0-9.-]+)", sender)
    if domain_match:
        return domain_match.group(1)
    return None


def is_rejection_email(text: str, subject: str) -> bool:
    """Check if the email is a rejection (not a confirmation)."""
    combined = (text + " " + subject).lower()
    for indicator in REJECTION_INDICATORS:
        if indicator in combined:
            return True
    return False


def is_incomplete_application(text: str, subject: str) -> bool:
    """Check if the email indicates an incomplete/started application."""
    combined = (text + " " + subject).lower()
    for indicator in INCOMPLETE_INDICATORS:
        if indicator in combined:
            return True
    return False


def parse_email(message: dict[str, Any]) -> Optional[JobApplication]:
    """Parse an email message and extract job application details."""
    message_id = message.get("id", "")
    headers = get_email_headers(message)
    body = get_email_body(message)
    text = strip_html(body)
    subject = headers.get("subject", "")
    sender = headers.get("from", "")

    logger.debug(f"Parsing email {message_id}: {subject[:50]}...")

    # Skip rejection emails (check first before confirmation logic)
    if is_rejection_email(text, subject):
        logger.info(f"Skipping rejection email: {subject[:50]}...")
        return None

    # Skip incomplete/started applications
    if is_incomplete_application(text, subject):
        logger.info(f"Skipping incomplete application email: {subject[:50]}...")
        return None

    # Try regex-based extraction first
    regex_company = extract_company_from_email(text, headers)
    regex_position = match_job_title(text) or match_job_title(subject)
    date_applied, date_conf = extract_date(text, headers)
    source = extract_source(headers)

    # Always try LLM for best results
    llm_result = extract_with_llm(text, subject, sender)

    # Prefer LLM results when available, fall back to regex
    company = None
    position = None
    company_conf = 0.0
    position_conf = 0.0

    if llm_result:
        if llm_result.get("company"):
            company = llm_result["company"]
            company_conf = 0.9
        if llm_result.get("position"):
            position = llm_result["position"]
            position_conf = 0.9

    # Fall back to regex if LLM didn't find something
    if not company and regex_company:
        company = regex_company
        company_conf = 0.7
    if not position and regex_position:
        position = regex_position
        position_conf = 0.8

    if company is None:
        logger.warning(f"Could not extract company from email {message_id}")
        return None

    if position is None:
        position = "N/A"
        position_conf = 0.5  # Still valid, just no position listed

    overall_confidence = (company_conf + position_conf + date_conf) / 3

    job = JobApplication(
        company=company,
        position=position,
        date_applied=date_applied,
        source_email_id=message_id,
        confidence=round(overall_confidence, 2),
        source=source,
        notes=f"Subject: {subject[:100]}" if subject else None,
    )

    logger.info(f"Parsed application: {job.company} - {job.position} (confidence: {job.confidence})")
    return job
