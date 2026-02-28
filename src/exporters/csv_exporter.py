"""
CSV exporter for category data (Task 5C.1).

Exports categories to CSV format with:
- Configurable delimiter (comma or semicolon for Excel in some locales)
- UTF-8 with BOM for Excel compatibility
- Parent name resolution for hierarchical categories
"""

import csv
from pathlib import Path

from src.models.category import Category
from src.utils.logger import get_logger

logger = get_logger(__name__)

# CSV columns in order
CSV_COLUMNS = [
    "name",
    "description",
    "confidence",
    "email_count",
    "source",
    "level",
    "parent_name",
]


def export_categories_to_csv(
    categories: list[Category],
    output_path: Path | str,
    delimiter: str = ",",
) -> Path:
    """
    Export categories to CSV format.

    Args:
        categories: List of Category objects to export
        output_path: Path for the output CSV file
        delimiter: CSV delimiter (default: comma, use semicolon for some Excel locales)

    Returns:
        Path to the created CSV file
    """
    output_path = Path(output_path)

    # Build lookup for parent name resolution
    category_lookup = {cat.category_id: cat.category_name for cat in categories}

    logger.info(f"Exporting {len(categories)} categories to CSV: {output_path}")

    # Write CSV with UTF-8 BOM for Excel compatibility
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=delimiter)
        writer.writeheader()

        for category in categories:
            # Resolve parent name from parent_category_id
            parent_name = ""
            if category.parent_category_id:
                parent_name = category_lookup.get(category.parent_category_id, "")

            row = {
                "name": category.category_name,
                "description": category.description,
                "confidence": str(category.confidence),
                "email_count": str(category.email_count)
                if category.email_count is not None
                else "",
                "source": category.source.value,
                "level": str(category.level),
                "parent_name": parent_name,
            }
            writer.writerow(row)

    logger.info(f"CSV export complete: {output_path}")
    return output_path
