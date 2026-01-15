"""
Category detail panel widget for the TUI application.

Displays detailed information about the selected category.
Task 5A.3: Enhanced confidence breakdown display with visual bars.
"""
from textual.reactive import reactive
from textual.widgets import Static

from src.models.category import Category
from src.ui.tui.theme import get_confidence_level
from src.ui.tui.widgets.category_table import format_source

# Component explanations for confidence breakdown
COMPONENT_EXPLANATIONS = {
    "cohesion": "How well-defined the category is (based on distinguishing features)",
    "volume": "Number of emails in this category (scaled to 100)",
    "source": "Reliability of the detection method (template > cluster > sender)",
    "percentage": "Proportion of your inbox this category represents",
    "name_quality": "Quality and clarity of the category name",
    "distinctiveness": "How unique this category is (low overlap with others)",
}


def get_component_explanation(component: str) -> str:
    """
    Get human-readable explanation for a confidence component.

    Args:
        component: Component name (cohesion, volume, source, etc.)

    Returns:
        Explanation string
    """
    return COMPONENT_EXPLANATIONS.get(component, "Score component")


def format_confidence_bar(score: float, width: int = 10) -> str:
    """
    Format a confidence score as a visual bar.

    Args:
        score: Score value 0.0-1.0
        width: Width of the bar in characters

    Returns:
        Visual bar string with markup
    """
    score = max(0.0, min(1.0, score))  # Clamp to [0, 1]
    filled = int(score * width)
    empty = width - filled

    # Use block characters for the bar
    filled_char = "█"
    empty_char = "░"

    # Color based on score level
    if score >= 0.7:
        color = "green"
    elif score >= 0.4:
        color = "yellow"
    else:
        color = "red"

    return f"[{color}]{filled_char * filled}[/{color}]{empty_char * empty}"


class DetailPanel(Static):
    """
    A panel widget for displaying category details.

    Shows selected category details including:
    - Category name and description
    - Confidence score with breakdown
    - Email count and percentage
    - Sample emails (sender, subject)
    - Distinguishing features

    Supports collapsing/expanding.
    """

    collapsed: reactive[bool] = reactive(False)

    def __init__(
        self,
        category: Category | None = None,
        email_lookup: dict | None = None,
        *args,
        **kwargs
    ):
        """
        Initialize the detail panel.

        Args:
            category: Initial category to display
            email_lookup: Dictionary mapping email IDs to Email objects
        """
        super().__init__(*args, **kwargs)
        self.category = category
        self.email_lookup = email_lookup or {}
        self._update_content()

    def update_category(self, category: Category | None) -> None:
        """
        Update the panel with a new category.

        Args:
            category: Category to display
        """
        self.category = category
        self._update_content()

    def clear(self) -> None:
        """Clear the panel content."""
        self.category = None
        self._update_content()

    def toggle_collapse(self) -> None:
        """Toggle the collapsed state."""
        self.collapsed = not self.collapsed
        self._update_content()

    def get_content_text(self) -> str:
        """
        Get the content text for the panel.

        Returns:
            Formatted content string
        """
        if self.category is None:
            return "No category selected"

        if self.collapsed:
            return f"[b]{self.category.category_name}[/b] (collapsed)"

        return self._format_category_details()

    def _format_category_details(self) -> str:
        """Format full category details."""
        cat = self.category
        if cat is None:
            return ""

        lines = []

        # Header
        lines.append(f"[b]{cat.category_name}[/b]")
        lines.append("")

        # Description
        lines.append("[dim]Description:[/dim]")
        lines.append(f"  {cat.description}")
        lines.append("")

        # Confidence
        confidence_pct = cat.confidence * 100
        confidence_level = get_confidence_level(cat.confidence)
        confidence_color = "green" if confidence_level == "high" else "yellow" if confidence_level == "medium" else "red"
        lines.append("[dim]Confidence:[/dim]")
        lines.append(f"  [{confidence_color}]{confidence_pct:.1f}%[/{confidence_color}] ({confidence_level})")
        lines.append("")

        # Confidence breakdown (if available)
        if cat.confidence_breakdown:
            lines.append("[dim]Confidence Breakdown:[/dim]")
            for component, score in cat.confidence_breakdown.items():
                bar = format_confidence_bar(score, width=8)
                score_pct = int(score * 100)
                # Capitalize component name for display
                display_name = component.replace("_", " ").title()
                lines.append(f"  {display_name:14} {bar} {score_pct}%")
            lines.append("")

        # Email count
        lines.append("[dim]Emails:[/dim]")
        email_str = str(cat.email_count) if cat.email_count is not None else "Unknown"
        pct_str = f" ({cat.percentage:.1f}%)" if cat.percentage else ""
        lines.append(f"  {email_str}{pct_str}")
        lines.append("")

        # Source
        lines.append("[dim]Source:[/dim]")
        lines.append(f"  {format_source(cat.source)}")
        lines.append("")

        # Sample emails
        if cat.example_email_ids and self.email_lookup:
            lines.append("[dim]Sample Emails:[/dim]")
            for email_id in cat.example_email_ids[:3]:
                if email_id in self.email_lookup:
                    email = self.email_lookup[email_id]
                    lines.append(f"  From: {email.sender_email}")
                    lines.append(f"  Subject: {email.subject[:50]}...")
                    lines.append("")
        elif cat.distinguishing_features:
            lines.append("[dim]Distinguishing Features:[/dim]")
            for feature in cat.distinguishing_features[:5]:
                truncated = feature[:70] + "..." if len(feature) > 70 else feature
                lines.append(f"  - {truncated}")
            lines.append("")

        # User modified flag
        if cat.user_modified:
            lines.append("[dim italic]Modified by user[/dim italic]")

        # Name quality warning
        if cat.needs_name_review:
            lines.append("[yellow]Name needs review[/yellow]")

        return "\n".join(lines)

    def _update_content(self) -> None:
        """Update the displayed content."""
        self.update(self.get_content_text())

    def watch_collapsed(self, collapsed: bool) -> None:
        """React to collapsed state changes."""
        self._update_content()

    def set_email_lookup(self, email_lookup: dict) -> None:
        """
        Set the email lookup dictionary.

        Args:
            email_lookup: Dictionary mapping email IDs to Email objects
        """
        self.email_lookup = email_lookup
        self._update_content()
