"""Shared memory taxonomy constants."""

EPISODIC_MEMORY_CATEGORY = "Episodic Memory"
LEGACY_TIMELINE_CATEGORY = "Timeline"

BASE_CATEGORIES = [
    {
        "name": "Core Self",
        "description": "User's static profile, preferences, habits, core values, and long-term goals",
    },
    {
        "name": EPISODIC_MEMORY_CATEGORY,
        "description": (
            "Concrete situated memories tied to the conversation time, including "
            "when, who, where, what happened, concrete activities, and object-symbol facts"
        ),
    },
    {
        "name": "Knowledge Base",
        "description": "Timeless knowledge, insights, and assets without time attributes",
    },
    {
        "name": "Social Graph",
        "description": "Interpersonal connections and relationships with others",
    },
]

BASE_CATEGORY_ALIASES = {
    LEGACY_TIMELINE_CATEGORY: EPISODIC_MEMORY_CATEGORY,
}


def normalize_category_name(category_name: str) -> str:
    """Return the canonical category name while accepting legacy aliases."""
    cleaned = category_name.strip("[]")
    return BASE_CATEGORY_ALIASES.get(cleaned, cleaned)
