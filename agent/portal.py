"""Mock payer portal. In production this would be a browser agent (or a voice
agent on the payer phone line). Here it returns canned, messy free text from
data/portal_pages.json so the parser has something realistic to work on.
"""
from .data import load_json


def fetch_portal_page(member_id: str) -> str | None:
    """Return the scraped benefits page text, or None if no page was found."""
    return load_json("portal_pages.json").get(member_id)
