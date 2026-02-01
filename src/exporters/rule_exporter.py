"""
Email rule exporters for Outlook and Gmail.

Per Phase 8 Track 8B.3 specification.
Exports approved categories as email rules that can be imported
into Outlook (XML) or Gmail (Atom XML format).
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from src.models.category import Category, CategorySource
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OutlookRuleExporter:
    """
    Export categories as Outlook rules XML.

    Generates XML compatible with Outlook rule import feature.
    Each category becomes a rule that moves emails to a folder
    named after the category.
    """

    def export(self, categories: list[Category]) -> str:
        """
        Export categories as Outlook rules XML string.

        Args:
            categories: List of Category objects to export

        Returns:
            XML string compatible with Outlook rule import
        """
        logger.info(f"Exporting {len(categories)} categories to Outlook rules")

        # Create root element
        root = ET.Element("rules")
        root.set("version", "1.0")

        for category in categories:
            rule_elem = self._create_rule(category)
            root.append(rule_elem)

        # Convert to string with proper formatting
        xml_str = self._pretty_print(root)

        logger.info("Outlook rules export complete")
        return xml_str

    def _create_rule(self, category: Category) -> ET.Element:
        """
        Create a rule element for a category.

        Args:
            category: Category to convert to rule

        Returns:
            XML Element representing the rule
        """
        rule = ET.Element("rule")
        rule.set("enabled", "true")

        # Rule name
        name = ET.SubElement(rule, "name")
        name.text = category.category_name

        # Rule description
        description = ET.SubElement(rule, "description")
        description.text = category.description or f"Auto-generated rule for {category.category_name}"

        # Conditions
        conditions = ET.SubElement(rule, "conditions")
        self._add_conditions(conditions, category)

        # Actions
        actions = ET.SubElement(rule, "actions")
        self._add_actions(actions, category)

        return rule

    def _add_conditions(self, conditions: ET.Element, category: Category) -> None:
        """
        Add conditions to a rule based on category source.

        Args:
            conditions: Parent conditions element
            category: Category to derive conditions from
        """
        # Add conditions based on source and distinguishing features
        if category.source == CategorySource.SENDER:
            # Sender-based: match sender addresses/domains
            if category.distinguishing_features:
                for feature in category.distinguishing_features:
                    if "@" in feature:
                        # Email address
                        condition = ET.SubElement(conditions, "fromAddress")
                        condition.set("contains", feature)
                    else:
                        # Domain
                        condition = ET.SubElement(conditions, "fromDomain")
                        condition.set("contains", feature)
        elif category.source == CategorySource.CONTENT_CLUSTER:
            # Content-based: match subject keywords
            if category.distinguishing_features:
                for feature in category.distinguishing_features:
                    condition = ET.SubElement(conditions, "subjectContains")
                    condition.set("value", feature)
        else:
            # Default: use category name as keyword
            condition = ET.SubElement(conditions, "subjectOrBodyContains")
            condition.set("value", category.category_name)

    def _add_actions(self, actions: ET.Element, category: Category) -> None:
        """
        Add actions to a rule.

        Args:
            actions: Parent actions element
            category: Category to derive folder name from
        """
        # Move to folder action
        move_action = ET.SubElement(actions, "moveToFolder")
        move_action.set("name", category.category_name)

        # Mark as read (optional - can be removed if not desired)
        # mark_read = ET.SubElement(actions, "markAsRead")
        # mark_read.set("value", "true")

    def _pretty_print(self, element: ET.Element) -> str:
        """
        Convert element to pretty-printed XML string.

        Args:
            element: Root XML element

        Returns:
            Formatted XML string
        """
        rough_string = ET.tostring(element, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def export_to_file(
        self,
        categories: list[Category],
        output_path: Path | str
    ) -> Path:
        """
        Export categories to an Outlook rules XML file.

        Args:
            categories: List of Category objects to export
            output_path: Path for the output XML file

        Returns:
            Path to the created XML file
        """
        output_path = Path(output_path)
        xml_content = self.export(categories)

        output_path.write_text(xml_content, encoding="utf-8")
        logger.info(f"Outlook rules exported to: {output_path}")

        return output_path


class GmailFilterExporter:
    """
    Export categories as Gmail filter XML.

    Generates XML in Atom feed format compatible with Gmail filter import.
    Each category becomes a filter that applies a label named after
    the category.
    """

    # Gmail filter Atom namespace
    ATOM_NS = "http://www.w3.org/2005/Atom"
    APPS_NS = "http://schemas.google.com/apps/2006"

    def export(self, categories: list[Category]) -> str:
        """
        Export categories as Gmail filter XML string.

        Args:
            categories: List of Category objects to export

        Returns:
            Atom XML string compatible with Gmail filter import
        """
        logger.info(f"Exporting {len(categories)} categories to Gmail filters")

        # Create root feed element with namespaces
        root = ET.Element("feed")
        root.set("xmlns", self.ATOM_NS)
        root.set("xmlns:apps", self.APPS_NS)

        # Add feed metadata
        title = ET.SubElement(root, "title")
        title.text = "Email Category Filters"

        author = ET.SubElement(root, "author")
        author_name = ET.SubElement(author, "name")
        author_name.text = "Email Corpus Analyzer"

        # Add entry for each category
        for category in categories:
            entry_elem = self._create_entry(category)
            root.append(entry_elem)

        # Convert to string with proper formatting
        xml_str = self._pretty_print(root)

        logger.info("Gmail filters export complete")
        return xml_str

    def _create_entry(self, category: Category) -> ET.Element:
        """
        Create an entry element for a category.

        Args:
            category: Category to convert to filter entry

        Returns:
            XML Element representing the filter entry
        """
        entry = ET.Element("entry")

        # Entry title
        title = ET.SubElement(entry, "title")
        title.text = category.category_name

        # Filter properties
        self._add_filter_properties(entry, category)

        return entry

    def _add_filter_properties(self, entry: ET.Element, category: Category) -> None:
        """
        Add filter properties based on category.

        Args:
            entry: Parent entry element
            category: Category to derive filter properties from
        """
        # Condition based on source
        if category.source == CategorySource.SENDER:
            if category.distinguishing_features:
                # Use from: query
                from_addresses = " OR ".join(
                    f"from:{feature}" for feature in category.distinguishing_features
                )
                prop = ET.SubElement(entry, "apps:property")
                prop.set("name", "from")
                prop.set("value", from_addresses)
        elif category.source == CategorySource.CONTENT_CLUSTER:
            if category.distinguishing_features:
                # Use subject keywords
                keywords = " OR ".join(
                    f"subject:{feature}" for feature in category.distinguishing_features
                )
                prop = ET.SubElement(entry, "apps:property")
                prop.set("name", "hasTheWord")
                prop.set("value", keywords)
        else:
            # Default: match category name
            prop = ET.SubElement(entry, "apps:property")
            prop.set("name", "hasTheWord")
            prop.set("value", category.category_name)

        # Action: apply label
        label_prop = ET.SubElement(entry, "apps:property")
        label_prop.set("name", "label")
        label_prop.set("value", category.category_name)

    def _pretty_print(self, element: ET.Element) -> str:
        """
        Convert element to pretty-printed XML string.

        Args:
            element: Root XML element

        Returns:
            Formatted XML string
        """
        # Register namespaces to avoid ns0 prefixes
        ET.register_namespace("", self.ATOM_NS)
        ET.register_namespace("apps", self.APPS_NS)

        rough_string = ET.tostring(element, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

    def export_to_file(
        self,
        categories: list[Category],
        output_path: Path | str
    ) -> Path:
        """
        Export categories to a Gmail filter XML file.

        Args:
            categories: List of Category objects to export
            output_path: Path for the output XML file

        Returns:
            Path to the created XML file
        """
        output_path = Path(output_path)
        xml_content = self.export(categories)

        output_path.write_text(xml_content, encoding="utf-8")
        logger.info(f"Gmail filters exported to: {output_path}")

        return output_path
