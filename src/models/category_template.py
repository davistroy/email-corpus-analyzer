"""
CategoryTemplate data model.

Per data-model.md lines 389-411.
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CategoryTemplate(BaseModel):
    """Predefined category pattern for matching."""

    name: str = Field(..., min_length=1)
    keywords: list[str] = Field(..., min_length=1)
    domains: list[str] = Field(default_factory=list)
    description: str


def load_templates(path: Path | None = None) -> list[CategoryTemplate]:
    """Load category templates from JSON file.

    Args:
        path: Custom path to templates JSON. Defaults to bundled templates.

    Returns:
        List of validated CategoryTemplate objects.

    Raises:
        FileNotFoundError: If template file doesn't exist.
        ValueError: If template JSON is invalid.
    """
    if path is None:
        path = Path(__file__).parent.parent / "data" / "templates.json"

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid template JSON in {path}: {e}") from e

    return [CategoryTemplate(**item) for item in data]


# Predefined templates constant (FR-024)
# Loaded from bundled JSON file (Phase 3.2: externalized from hardcoded Python objects)
PREDEFINED_TEMPLATES = load_templates()
