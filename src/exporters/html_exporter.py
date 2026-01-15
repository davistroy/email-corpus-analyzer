"""
HTML exporter for category data (Task 5C.2).

Generates standalone HTML reports with:
- Category list with details (name, description, confidence, email count)
- Charts for confidence distribution and source breakdown
- Inline CSS (no external dependencies)
"""
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.category import Category
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Template directory path
TEMPLATE_DIR = Path(__file__).parent / "templates"


def export_categories_to_html(
    categories: list[Category],
    output_path: Path | str,
    title: str = "Category Report",
) -> Path:
    """
    Export categories to standalone HTML report.

    Args:
        categories: List of Category objects to export
        output_path: Path for the output HTML file
        title: Report title (default: "Category Report")

    Returns:
        Path to the created HTML file
    """
    output_path = Path(output_path)

    logger.info(f"Exporting {len(categories)} categories to HTML: {output_path}")

    # Set up Jinja2 environment with autoescape for all templates
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,  # Enable autoescape for all templates
    )

    template = env.get_template("report.html.j2")

    # Calculate statistics
    total_categories = len(categories)
    total_emails = sum(
        cat.email_count for cat in categories if cat.email_count is not None
    )
    avg_confidence = (
        round(sum(cat.confidence for cat in categories) / total_categories * 100)
        if total_categories > 0
        else 0
    )

    # Count categories by source
    source_counts = dict(Counter(cat.source.value for cat in categories))

    # Build parent name lookup
    parent_names = {cat.category_id: cat.category_name for cat in categories}

    # Render template
    html_content = template.render(
        title=title,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        categories=categories,
        total_categories=total_categories,
        total_emails=total_emails,
        avg_confidence=avg_confidence,
        source_counts=source_counts,
        parent_names=parent_names,
    )

    # Write output
    output_path.write_text(html_content, encoding="utf-8")

    logger.info(f"HTML export complete: {output_path}")
    return output_path
