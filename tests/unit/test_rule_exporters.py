"""
Unit tests for Track 8B.3: Email Rule Exporters.

Tests the export functionality for:
- Outlook rules XML format
- Gmail filter XML format

Uses TDD approach - tests written first before implementation.
"""

import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.models.category import Category, CategorySource

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_categories() -> list[Category]:
    """Create sample categories for testing rule export."""
    return [
        Category(
            category_id="cat_001",
            category_name="Financial Alerts",
            description="Bank and payment notifications",
            confidence=0.85,
            email_count=150,
            source=CategorySource.SENDER,
            distinguishing_features=["bank.com", "paypal.com"],
        ),
        Category(
            category_id="cat_002",
            category_name="Shopping Orders",
            description="E-commerce order updates",
            confidence=0.72,
            email_count=89,
            source=CategorySource.CONTENT_CLUSTER,
            distinguishing_features=["order confirmation", "shipping update"],
        ),
        Category(
            category_id="cat_003",
            category_name="Newsletter Weekly",
            description="Weekly newsletters",
            confidence=0.65,
            email_count=45,
            source=CategorySource.SENDER,
            distinguishing_features=["newsletter@example.com"],
        ),
    ]


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# Track 8B.3: Outlook Rule Exporter Tests
# ============================================================================


class TestOutlookRuleExporter:
    """Tests for OutlookRuleExporter class."""

    def test_exporter_exists(self):
        """Test OutlookRuleExporter class exists."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        assert OutlookRuleExporter is not None

    def test_exporter_has_export_method(self):
        """Test exporter has export method."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        assert hasattr(exporter, "export")
        assert callable(exporter.export)

    def test_export_returns_string(self, sample_categories):
        """Test export method returns XML string."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        result = exporter.export(sample_categories)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_valid_xml(self, sample_categories):
        """Test exported content is valid XML."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        # Should not raise an exception
        root = ET.fromstring(xml_content)
        assert root is not None

    def test_export_has_rules_root(self, sample_categories):
        """Test exported XML has rules root element."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        assert root.tag == "rules"

    def test_export_creates_rule_per_category(self, sample_categories):
        """Test exported XML has one rule per category."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        rules = root.findall("rule")

        assert len(rules) == len(sample_categories)

    def test_rule_has_name(self, sample_categories):
        """Test each rule has name attribute from category."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        rule = root.find("rule")

        assert rule is not None
        name_elem = rule.find("name")
        assert name_elem is not None
        assert name_elem.text == "Financial Alerts"

    def test_rule_has_conditions(self, sample_categories):
        """Test each rule has conditions element."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        rule = root.find("rule")

        conditions = rule.find("conditions")
        assert conditions is not None

    def test_rule_has_actions(self, sample_categories):
        """Test each rule has actions element."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        rule = root.find("rule")

        actions = rule.find("actions")
        assert actions is not None

    def test_move_to_folder_action(self, sample_categories):
        """Test rules have move-to-folder action."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        rule = root.find("rule")
        actions = rule.find("actions")
        move_action = actions.find("moveToFolder")

        assert move_action is not None

    def test_export_to_file(self, sample_categories, temp_output_dir):
        """Test exporting rules to file."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        exporter = OutlookRuleExporter()
        output_path = temp_output_dir / "outlook_rules.xml"

        result = exporter.export_to_file(sample_categories, output_path)

        assert output_path.exists()
        assert result == output_path

    def test_export_handles_special_characters(self, temp_output_dir):
        """Test export escapes special XML characters."""
        from src.exporters.rule_exporter import OutlookRuleExporter

        categories = [
            Category(
                category_id="cat_special",
                category_name="Test & Research <Group>",
                description="Categories with & and < > characters",
                confidence=0.75,
                source=CategorySource.CUSTOM,
            ),
        ]

        exporter = OutlookRuleExporter()
        xml_content = exporter.export(categories)

        # Should be valid XML (special chars escaped)
        root = ET.fromstring(xml_content)
        rule = root.find("rule")
        name = rule.find("name")
        assert "Test & Research <Group>" in name.text or "&amp;" in xml_content


class TestGmailFilterExporter:
    """Tests for GmailFilterExporter class."""

    def test_exporter_exists(self):
        """Test GmailFilterExporter class exists."""
        from src.exporters.rule_exporter import GmailFilterExporter

        assert GmailFilterExporter is not None

    def test_exporter_has_export_method(self):
        """Test exporter has export method."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        assert hasattr(exporter, "export")
        assert callable(exporter.export)

    def test_export_returns_string(self, sample_categories):
        """Test export method returns XML string."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        result = exporter.export(sample_categories)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_export_valid_xml(self, sample_categories):
        """Test exported content is valid XML."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        xml_content = exporter.export(sample_categories)

        # Should not raise an exception
        root = ET.fromstring(xml_content)
        assert root is not None

    def test_export_has_feed_root(self, sample_categories):
        """Test exported XML has feed root element (Atom format)."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        # Gmail uses Atom feed format
        assert "feed" in root.tag.lower()

    def test_export_creates_entry_per_category(self, sample_categories):
        """Test exported XML has one entry per category."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        xml_content = exporter.export(sample_categories)

        root = ET.fromstring(xml_content)
        # Gmail uses 'entry' elements for each filter
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        assert len(entries) == len(sample_categories)

    def test_filter_has_label_action(self, sample_categories):
        """Test each filter has label action."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        xml_content = exporter.export(sample_categories)

        # Check that label property exists
        assert "label" in xml_content.lower()

    def test_export_to_file(self, sample_categories, temp_output_dir):
        """Test exporting filters to file."""
        from src.exporters.rule_exporter import GmailFilterExporter

        exporter = GmailFilterExporter()
        output_path = temp_output_dir / "gmail_filters.xml"

        result = exporter.export_to_file(sample_categories, output_path)

        assert output_path.exists()
        assert result == output_path


# ============================================================================
# Module Registration Tests
# ============================================================================


class TestRuleExporterModule:
    """Test rule exporter module registration."""

    def test_outlook_exporter_importable(self):
        """Test OutlookRuleExporter is importable from exporters."""
        from src.exporters import OutlookRuleExporter

        assert OutlookRuleExporter is not None

    def test_gmail_exporter_importable(self):
        """Test GmailFilterExporter is importable from exporters."""
        from src.exporters import GmailFilterExporter

        assert GmailFilterExporter is not None


# ============================================================================
# CLI Integration Tests
# ============================================================================


class TestCLIExportFormats:
    """Test CLI export command supports new formats."""

    def test_export_help_shows_outlook_format(self):
        """Test export --help shows outlook-rules format."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "export", "--help"],
            capture_output=True,
            text=True,
        )

        assert "outlook-rules" in result.stdout

    def test_export_help_shows_gmail_format(self):
        """Test export --help shows gmail-filters format."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "export", "--help"],
            capture_output=True,
            text=True,
        )

        assert "gmail-filters" in result.stdout
