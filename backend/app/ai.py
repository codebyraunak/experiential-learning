import base64
import json
import logging
import os
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

CATEGORIES = (
    "Electrical",
    "Plumbing",
    "Furniture",
    "Network",
    "AV Equipment",
    "Washroom",
    "Other",
)
PRIORITIES = ("low", "medium", "high", "critical")
FALLBACK_SUGGESTION = {
    "category": "Other",
    "priority": "medium",
    "suggested_team": "General Maintenance",
    "summary": "Maintenance issue reported by a student.",
}
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash:generateContent"
)


class ComplaintSuggestion(BaseModel):
    category: str
    priority: str
    suggested_team: str
    summary: str


def _validate_suggestion(value: Any) -> dict[str, str]:
    suggestion = ComplaintSuggestion.model_validate(value)
    categories_by_name = {category.lower(): category for category in CATEGORIES}
    normalized_category = suggestion.category.strip().lower()
    if normalized_category not in categories_by_name:
        raise ValueError("Gemini returned an unsupported category")
    suggestion.category = categories_by_name[normalized_category]
    suggestion.priority = suggestion.priority.strip().lower()
    if suggestion.priority not in PRIORITIES:
        raise ValueError("Gemini returned an unsupported priority")
    suggestion.suggested_team = suggestion.suggested_team.strip()[:100] or "General Maintenance"
    suggestion.summary = suggestion.summary.strip()[:1000]
    return suggestion.model_dump()


def categorize_complaint(
    title: str,
    description: str,
    image: bytes | None = None,
    image_mime_type: str | None = None,
) -> dict[str, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not configured; using complaint categorization fallback")
        return FALLBACK_SUGGESTION.copy()

    content: list[dict[str, Any]] = [{
        "text": (
            "Categorize this campus maintenance complaint. Return only JSON with "
            "category, priority, suggested_team, summary. category must be one of "
            f"{', '.join(CATEGORIES)}; priority must be one of {', '.join(PRIORITIES)}. "
            "Use a concise, non-sensitive summary.\n"
            f"Title: {title}\nDescription: {description}"
        )
    }]
    if image is not None and image_mime_type is not None:
        content.append({
            "inline_data": {
                "mime_type": image_mime_type,
                "data": base64.b64encode(image).decode("ascii"),
            }
        })

    try:
        response = httpx.post(
            GEMINI_URL,
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{"parts": content}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=20.0,
        )
        response.raise_for_status()
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return _validate_suggestion(json.loads(text))
    except (
        httpx.HTTPError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        ValidationError,
        json.JSONDecodeError,
    ):
        logger.warning("Gemini categorization failed; using complaint fallback")
        return FALLBACK_SUGGESTION.copy()
