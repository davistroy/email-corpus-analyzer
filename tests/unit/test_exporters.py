"""
Unit tests for the exporters module (Track 5C: Export & Polish).

Tests cover:
- CSV export functionality with configurable delimiters
- HTML report generation with inline CSS
- UTF-8 BOM handling for Excel compatibility

Uses TDD approach - tests written first before implementation.
"""
import csv
import tempfile
from pathlib import Path

import pytest

from src.models.category import Category, CategorySource


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_categories() -> list[Category]:
    """Create sample categories for testing."""
    return [
        Category(
            category_id="cat_001",
            category_name="Financial Notifications",
            description="Bank and payment notifications",
            confidence=0.85,
            email_count=150,
            percentage=15.0,
            source=CategorySource.TEMPLATE,
            level=0,
            parent_category_id=None,
        ),
        Category(
            category_id="cat_002",
            category_name="Shopping Updates",
            description="E-commerce order and shipping updates",
            confidence=0.72,
            email_count=89,
            percentage=8.9,
            source=CategorySource.CONTENT_CLUSTER,
            level=0,
            parent_category_id=None,
        ),
        Category(
            category_id="cat_003",
            category_name="Bank Statements",
            description="Monthly bank statements",
            confidence=0.95,
            email_count=24,
            percentage=2.4,
            source=CategorySource.SENDER,
            level=1,
            parent_category_id="cat_001",
        ),
    ]


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Task 5C.1: CSV Export Tests
# ============================================================================


class TestCsvExporter:
    """Tests for export_categories_to_csv function."""

    def test_export_creates_csv_file(self, sample_categories, temp_output_dir):
        """Test that export_categories_to_csv creates a CSV file."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"

        export_categories_to_csv(sample_categories, output_path)

        assert output_path.exists()

    def test_export_csv_has_correct_columns(self, sample_categories, temp_output_dir):
        """Test CSV has required columns: name, description, confidence, email_count, source, level, parent_name."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        expected_columns = [
            "name",
            "description",
            "confidence",
            "email_count",
            "source",
            "level",
            "parent_name",
        ]
        assert fieldnames == expected_columns

    def test_export_csv_contains_all_categories(self, sample_categories, temp_output_dir):
        """Test CSV contains all categories from input."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["name"] == "Financial Notifications"
        assert rows[1]["name"] == "Shopping Updates"
        assert rows[2]["name"] == "Bank Statements"

    def test_export_csv_correct_values(self, sample_categories, temp_output_dir):
        """Test CSV values are correctly formatted."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Check first category
        assert rows[0]["description"] == "Bank and payment notifications"
        assert rows[0]["confidence"] == "0.85"
        assert rows[0]["email_count"] == "150"
        assert rows[0]["source"] == "template"
        assert rows[0]["level"] == "0"
        assert rows[0]["parent_name"] == ""

    def test_export_csv_parent_name_resolution(self, sample_categories, temp_output_dir):
        """Test that parent_name is resolved from parent_category_id."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Third category has parent_category_id="cat_001"
        assert rows[2]["parent_name"] == "Financial Notifications"

    def test_export_csv_semicolon_delimiter(self, sample_categories, temp_output_dir):
        """Test export with semicolon delimiter for Excel compatibility in some locales."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path, delimiter=";")

        with open(output_path, encoding="utf-8-sig") as f:
            content = f.read()

        # Should contain semicolons, not commas as separators
        assert ";" in content
        # Header should be semicolon-separated
        first_line = content.split("\n")[0]
        assert "name;description;confidence" in first_line

    def test_export_csv_utf8_with_bom(self, sample_categories, temp_output_dir):
        """Test CSV file has UTF-8 BOM for Excel compatibility."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(sample_categories, output_path)

        with open(output_path, "rb") as f:
            first_bytes = f.read(3)

        # UTF-8 BOM is EF BB BF
        assert first_bytes == b"\xef\xbb\xbf"

    def test_export_csv_handles_empty_list(self, temp_output_dir):
        """Test export handles empty category list gracefully."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv([], output_path)

        assert output_path.exists()

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 0

    def test_export_csv_handles_special_characters(self, temp_output_dir):
        """Test export handles special characters in category names/descriptions."""
        from src.exporters.csv_exporter import export_categories_to_csv

        categories = [
            Category(
                category_id="cat_special",
                category_name="Caf\u00e9 & Restaurant",
                description="Orders with \"quotes\" and commas, etc.",
                confidence=0.75,
                email_count=50,
                source=CategorySource.CUSTOM,
                level=0,
            ),
        ]

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["name"] == "Caf\u00e9 & Restaurant"
        assert rows[0]["description"] == 'Orders with "quotes" and commas, etc.'

    def test_export_csv_handles_none_email_count(self, temp_output_dir):
        """Test export handles None values for email_count."""
        from src.exporters.csv_exporter import export_categories_to_csv

        categories = [
            Category(
                category_id="cat_no_count",
                category_name="Test Category",
                description="Test description",
                confidence=0.5,
                email_count=None,
                source=CategorySource.CUSTOM,
                level=0,
            ),
        ]

        output_path = temp_output_dir / "categories.csv"
        export_categories_to_csv(categories, output_path)

        with open(output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["email_count"] == ""

    def test_export_csv_returns_output_path(self, sample_categories, temp_output_dir):
        """Test that export function returns the output path."""
        from src.exporters.csv_exporter import export_categories_to_csv

        output_path = temp_output_dir / "categories.csv"
        result = export_categories_to_csv(sample_categories, output_path)

        assert result == output_path


# ============================================================================
# Task 5C.2: HTML Export Tests
# ============================================================================


class TestHtmlExporter:
    """Tests for export_categories_to_html function."""

    def test_export_creates_html_file(self, sample_categories, temp_output_dir):
        """Test that export_categories_to_html creates an HTML file."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"

        export_categories_to_html(sample_categories, output_path)

        assert output_path.exists()

    def test_export_html_is_valid_html5(self, sample_categories, temp_output_dir):
        """Test output is valid HTML5 with doctype."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content

    def test_export_html_contains_title(self, sample_categories, temp_output_dir):
        """Test HTML contains the specified title."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(
            sample_categories, output_path, title="My Custom Report"
        )

        content = output_path.read_text(encoding="utf-8")

        assert "<title>My Custom Report</title>" in content
        assert "My Custom Report" in content  # Also in body

    def test_export_html_default_title(self, sample_categories, temp_output_dir):
        """Test HTML uses default title when none specified."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        assert "<title>Category Report</title>" in content

    def test_export_html_contains_categories(self, sample_categories, temp_output_dir):
        """Test HTML contains all category names."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        assert "Financial Notifications" in content
        assert "Shopping Updates" in content
        assert "Bank Statements" in content

    def test_export_html_contains_category_details(self, sample_categories, temp_output_dir):
        """Test HTML contains category details: description, confidence, email count."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        # Check descriptions are present
        assert "Bank and payment notifications" in content
        assert "E-commerce order and shipping updates" in content

        # Check confidence values are present (as percentages)
        assert "85" in content  # 0.85 -> 85%
        assert "72" in content  # 0.72 -> 72%

        # Check email counts
        assert "150" in content
        assert "89" in content

    def test_export_html_has_inline_css(self, sample_categories, temp_output_dir):
        """Test HTML has inline CSS styles (no external dependencies)."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        assert "<style>" in content
        assert "</style>" in content
        # Should not have external stylesheet links
        assert 'rel="stylesheet"' not in content

    def test_export_html_has_confidence_chart(self, sample_categories, temp_output_dir):
        """Test HTML contains confidence distribution visualization."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        # Should have some kind of chart/visualization
        # Can be SVG or CSS-based bar chart
        assert "chart" in content.lower() or "svg" in content.lower() or "bar" in content.lower()

    def test_export_html_has_source_breakdown(self, sample_categories, temp_output_dir):
        """Test HTML contains source breakdown (template, content_cluster, sender, etc.)."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        # Source types should be mentioned
        assert "template" in content.lower()
        assert "content_cluster" in content.lower() or "cluster" in content.lower()
        assert "sender" in content.lower()

    def test_export_html_standalone(self, sample_categories, temp_output_dir):
        """Test HTML is fully standalone (no external resources)."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(sample_categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        # Should not have external script or link tags
        assert "<script src=" not in content
        assert '<link rel="stylesheet" href=' not in content

    def test_export_html_handles_empty_list(self, temp_output_dir):
        """Test export handles empty category list gracefully."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        export_categories_to_html([], output_path)

        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        # Should show some message about no categories
        assert "no categories" in content.lower() or "0" in content

    def test_export_html_handles_special_characters(self, temp_output_dir):
        """Test HTML properly escapes special characters."""
        from src.exporters.html_exporter import export_categories_to_html

        categories = [
            Category(
                category_id="cat_special",
                category_name="Test <script>alert('xss')</script>",
                description="Description with <b>html</b> & special chars",
                confidence=0.75,
                email_count=50,
                source=CategorySource.CUSTOM,
                level=0,
            ),
        ]

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        # Should escape HTML special characters
        assert "<script>alert" not in content
        assert "&lt;" in content or "\\u003c" in content or "&#" in content

    def test_export_html_returns_output_path(self, sample_categories, temp_output_dir):
        """Test that export function returns the output path."""
        from src.exporters.html_exporter import export_categories_to_html

        output_path = temp_output_dir / "report.html"
        result = export_categories_to_html(sample_categories, output_path)

        assert result == output_path

    def test_export_html_utf8_encoding(self, temp_output_dir):
        """Test HTML is properly UTF-8 encoded."""
        from src.exporters.html_exporter import export_categories_to_html

        categories = [
            Category(
                category_id="cat_utf8",
                category_name="Caf\u00e9 Notifications",
                description="Commandes du caf\u00e9",
                confidence=0.8,
                email_count=25,
                source=CategorySource.CUSTOM,
                level=0,
            ),
        ]

        output_path = temp_output_dir / "report.html"
        export_categories_to_html(categories, output_path)

        content = output_path.read_text(encoding="utf-8")

        assert "Caf\u00e9 Notifications" in content
        assert 'charset="utf-8"' in content.lower() or "charset=utf-8" in content.lower()


# ============================================================================
# Exporter Module Tests
# ============================================================================


class TestExportersModule:
    """Tests for the exporters module __init__.py."""

    def test_module_exports_csv_exporter(self):
        """Test that export_categories_to_csv is importable from exporters module."""
        from src.exporters import export_categories_to_csv

        assert callable(export_categories_to_csv)

    def test_module_exports_html_exporter(self):
        """Test that export_categories_to_html is importable from exporters module."""
        from src.exporters import export_categories_to_html

        assert callable(export_categories_to_html)
