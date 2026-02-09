"""Utility functions for parsing."""
import re
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return domain.replace("www.", "")
    except:
        return ""


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(pattern, text)
    return list(set(emails))


def extract_phones(text: str) -> list[str]:
    """Extract phone numbers from text."""
    # Russian phone patterns
    patterns = [
        r'\+?7\s?\(?\d{3}\)?\s?\d{3}[- ]?\d{2}[- ]?\d{2}',
        r'\+?7\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}',
        r'8\s?\(?\d{3}\)?\s?\d{3}[- ]?\d{2}[- ]?\d{2}',
    ]
    phones = []
    for pattern in patterns:
        phones.extend(re.findall(pattern, text))
    return list(set(phones))


def extract_inn(text: str) -> str | None:
    """Extract INN from text."""
    # INN pattern: 10 or 12 digits
    pattern = r'\b\d{10}\b|\b\d{12}\b'
    matches = re.findall(pattern, text)
    for match in matches:
        if len(match) in [10, 12]:
            return match
    return None


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

