"""
Rule editor TUI dialog for editing category rule conditions (Phase 3, Item 3.5).

Modal dialog for viewing and editing a CategoryRule's conditions with:
- Condition list display
- Add/remove conditions
- AND/OR logic toggle
- Live match count against the corpus
- Accept/Cancel actions
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Select, Static

from src.models.category import Category
from src.models.email import Email
from src.models.rule import (
    CategoryRule,
    ConditionField,
    ConditionLogic,
    ConditionOperator,
    RuleAction,
    RuleActionType,
    RuleCondition,
)
from src.rules.engine import RuleEngine

logger = logging.getLogger(__name__)

# Fields and operators exposed to the user for condition building
_AVAILABLE_FIELDS: list[ConditionField] = [
    ConditionField.SENDER_EMAIL,
    ConditionField.SENDER_DOMAIN,
    ConditionField.SENDER_NAME,
    ConditionField.SUBJECT,
    ConditionField.BODY,
    ConditionField.HAS_ATTACHMENT,
    ConditionField.RECIPIENT_EMAIL,
]

_AVAILABLE_OPERATORS: list[ConditionOperator] = [
    ConditionOperator.CONTAINS,
    ConditionOperator.EQUALS,
    ConditionOperator.STARTS_WITH,
    ConditionOperator.ENDS_WITH,
    ConditionOperator.MATCHES_REGEX,
    ConditionOperator.IN_LIST,
    ConditionOperator.NOT_CONTAINS,
    ConditionOperator.NOT_EQUALS,
]


class RuleEditorDialog(ModalScreen[CategoryRule | None]):
    """
    Modal dialog for editing a category rule's conditions.

    Features:
    - Shows current conditions in a table
    - Add new conditions (field, operator, value)
    - Remove conditions by index
    - Toggle AND/OR logic
    - Live match count: "Matches N of M emails"
    - Accept (save) / Cancel
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "accept", "Save"),
    ]

    CSS = """
    #rule-editor-dialog {
        align: center middle;
        width: 85%;
        min-width: 70;
        max-width: 120;
        height: auto;
        max-height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #rule-editor-dialog .dialog-title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    #rule-editor-dialog .dialog-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    #rule-editor-dialog .dialog-hint {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }

    #rule-editor-dialog .match-count {
        text-style: bold;
        text-align: center;
        margin-top: 1;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    #rule-editor-dialog .logic-section {
        margin-bottom: 1;
    }

    #rule-editor-dialog .add-condition-section {
        border: solid $secondary;
        padding: 1;
        margin-top: 1;
    }

    #rule-editor-dialog .add-section-title {
        color: $text-muted;
        text-style: italic;
        margin-bottom: 1;
    }

    #rule-editor-dialog DataTable {
        height: auto;
        max-height: 10;
    }

    #rule-editor-dialog Select {
        width: 100%;
        margin-bottom: 1;
    }

    #rule-editor-dialog Input {
        width: 100%;
        margin-bottom: 1;
    }

    #rule-editor-dialog .button-row {
        align: center middle;
        margin-top: 1;
    }
    """

    condition_selected_index: reactive[int] = reactive(0)

    def __init__(
        self,
        rule: CategoryRule | None,
        category: Category,
        corpus: list[Email],
        *args,
        **kwargs,
    ):
        """
        Initialize the rule editor dialog.

        Args:
            rule: Existing CategoryRule to edit, or None for new rule creation.
            category: The category this rule belongs to.
            corpus: List of emails for live match count calculation.
        """
        super().__init__(*args, **kwargs)
        self.rule = rule
        self.category = category
        self.corpus = list(corpus)
        self._engine = RuleEngine()

        # Working state: editable copies of conditions and logic
        if rule is not None:
            self.working_conditions: list[RuleCondition] = list(rule.conditions)
            self.working_logic: ConditionLogic = rule.logic
        else:
            self.working_conditions = []
            self.working_logic = ConditionLogic.OR

    # -------------------------------------------------------------------------
    # Compose
    # -------------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the dialog content."""
        title = "Edit Rule" if self.rule else "Create Rule"
        yield Container(
            Static(f"{title}: {self.category.category_name}", classes="dialog-title"),
            Static(self._logic_label(), id="logic-label", classes="logic-section"),
            DataTable(id="conditions-table", cursor_type="row"),
            Static(self.get_match_text(), id="match-count", classes="match-count"),
            Vertical(
                Static("Add Condition:", classes="add-section-title"),
                Select(
                    [(f.value, f.value) for f in _AVAILABLE_FIELDS],
                    prompt="Select field",
                    id="field-select",
                ),
                Select(
                    [(o.value, o.value) for o in _AVAILABLE_OPERATORS],
                    prompt="Select operator",
                    id="operator-select",
                ),
                Input(placeholder="Enter value", id="value-input"),
                classes="add-condition-section",
            ),
            Static(
                "[Ctrl+S] Save  [Escape] Cancel  [Enter] Add condition  "
                "[Delete/Backspace] Remove  [Tab] Toggle AND/OR",
                classes="dialog-hint",
            ),
            id="rule-editor-dialog",
        )

    def on_mount(self) -> None:
        """Set up the conditions table when dialog opens."""
        self._rebuild_conditions_table()

    # -------------------------------------------------------------------------
    # Condition management
    # -------------------------------------------------------------------------

    def add_condition(self, condition: RuleCondition) -> None:
        """Add a new condition to the working list.

        Args:
            condition: The RuleCondition to add.
        """
        self.working_conditions.append(condition)
        self._rebuild_conditions_table()
        self._update_match_count()

    def remove_condition(self, index: int) -> None:
        """Remove a condition by its index.

        Does nothing if the index is out of range.

        Args:
            index: Zero-based index of the condition to remove.
        """
        if index < 0 or index >= len(self.working_conditions):
            return
        self.working_conditions.pop(index)
        self._rebuild_conditions_table()
        self._update_match_count()

    def toggle_logic(self) -> None:
        """Toggle between AND and OR condition logic."""
        if self.working_logic == ConditionLogic.AND:
            self.working_logic = ConditionLogic.OR
        else:
            self.working_logic = ConditionLogic.AND
        self._update_logic_label()
        self._update_match_count()

    # -------------------------------------------------------------------------
    # Match count
    # -------------------------------------------------------------------------

    def compute_match_count(self) -> int:
        """Compute the number of corpus emails matching the current conditions.

        Uses the RuleEngine for evaluation. If there are no conditions,
        returns 0 (a rule with no conditions matches nothing).

        Returns:
            Number of matching emails.
        """
        if not self.working_conditions:
            return 0

        # Build a temporary rule from working state for evaluation
        temp_rule = CategoryRule(
            rule_id="__temp__",
            name="__temp__",
            conditions=self.working_conditions,
            action=RuleAction(
                action_type=RuleActionType.CATEGORIZE,
                target="__temp__",
            ),
            logic=self.working_logic,
            enabled=True,
        )

        count = 0
        for email in self.corpus:
            if self._engine.evaluate_rule(temp_rule, email):
                count += 1
        return count

    def get_match_text(self) -> str:
        """Get human-readable match count text.

        Returns:
            String like "Matches 3 of 100 emails" or "Matches 1 of 5 email".
        """
        count = self.compute_match_count()
        total = len(self.corpus)
        word = "email" if count == 1 else "emails"
        return f"Matches {count} of {total} {word}"

    # -------------------------------------------------------------------------
    # Condition display formatting
    # -------------------------------------------------------------------------

    @staticmethod
    def format_condition(condition: RuleCondition) -> str:
        """Format a condition as a human-readable string.

        Args:
            condition: The condition to format.

        Returns:
            String like "sender_domain equals 'example.com'"
        """
        return f"{condition.field.value} {condition.operator.value} '{condition.value}'"

    # -------------------------------------------------------------------------
    # Available fields/operators for UI selectors
    # -------------------------------------------------------------------------

    @staticmethod
    def get_available_fields() -> list[ConditionField]:
        """Return the list of available condition fields."""
        return list(_AVAILABLE_FIELDS)

    @staticmethod
    def get_available_operators() -> list[ConditionOperator]:
        """Return the list of available condition operators."""
        return list(_AVAILABLE_OPERATORS)

    # -------------------------------------------------------------------------
    # Build result
    # -------------------------------------------------------------------------

    def build_rule(self) -> CategoryRule | None:
        """Build a CategoryRule from the current working state.

        Returns:
            A CategoryRule if there are conditions, or None if empty.
        """
        if not self.working_conditions:
            return None

        now = datetime.now(timezone.utc)

        if self.rule is not None:
            # Update existing rule: preserve metadata
            return CategoryRule(
                rule_id=self.rule.rule_id,
                name=self.rule.name,
                description=self.rule.description,
                conditions=list(self.working_conditions),
                action=self.rule.action,
                logic=self.working_logic,
                priority=self.rule.priority,
                enabled=self.rule.enabled,
                category_id=self.rule.category_id,
                created_date=self.rule.created_date,
                last_modified=now,
            )

        # Create new rule
        cat_id = self.category.category_id
        return CategoryRule(
            rule_id=f"rule_{cat_id}",
            name=f"Rule: {self.category.category_name}",
            description=f"User-created rule for '{self.category.category_name}'",
            conditions=list(self.working_conditions),
            action=RuleAction(
                action_type=RuleActionType.CATEGORIZE,
                target=self.category.category_name,
                target_category_id=cat_id,
            ),
            logic=self.working_logic,
            priority=50,
            enabled=True,
            category_id=cat_id,
            created_date=now,
            last_modified=now,
        )

    # -------------------------------------------------------------------------
    # UI update helpers
    # -------------------------------------------------------------------------

    def _rebuild_conditions_table(self) -> None:
        """Rebuild the conditions DataTable from working_conditions."""
        try:
            table = self.query_one("#conditions-table", DataTable)
            table.clear(columns=True)
            table.add_column("#", key="index", width=4)
            table.add_column("Field", key="field", width=16)
            table.add_column("Operator", key="operator", width=14)
            table.add_column("Value", key="value", width=30)

            for idx, cond in enumerate(self.working_conditions):
                table.add_row(
                    str(idx + 1),
                    cond.field.value,
                    cond.operator.value,
                    cond.value,
                    key=f"cond_{idx}",
                )
        except NoMatches:
            logger.debug("Conditions table not mounted yet, skipping rebuild")

    def _update_match_count(self) -> None:
        """Update the match count display."""
        try:
            widget = self.query_one("#match-count", Static)
            widget.update(self.get_match_text())
        except NoMatches:
            logger.debug("Match count widget not mounted yet, skipping update")

    def _update_logic_label(self) -> None:
        """Update the logic label display."""
        try:
            widget = self.query_one("#logic-label", Static)
            widget.update(self._logic_label())
        except NoMatches:
            logger.debug("Logic label widget not mounted yet, skipping update")

    def _logic_label(self) -> str:
        """Get the label text for the current logic setting."""
        logic_str = self.working_logic.value.upper()
        return f"Condition Logic: {logic_str} (press Tab to toggle)"

    # -------------------------------------------------------------------------
    # Textual action handlers
    # -------------------------------------------------------------------------

    def action_cancel(self) -> None:
        """Cancel and dismiss with None."""
        self.dismiss(None)

    def action_accept(self) -> None:
        """Accept: build the rule and dismiss with it."""
        result = self.build_rule()
        self.dismiss(result)

    def action_add_condition(self) -> None:
        """Add a condition from the current field/operator/value selections."""
        try:
            field_select = self.query_one("#field-select", Select)
            op_select = self.query_one("#operator-select", Select)
            value_input = self.query_one("#value-input", Input)
        except NoMatches:
            logger.debug("Add condition widgets not mounted yet")
            return

        field_val = field_select.value
        op_val = op_select.value

        if field_val is Select.BLANK or op_val is Select.BLANK:
            self.notify("Please select a field and operator", severity="warning")
            return

        value = value_input.value.strip()
        if not value:
            self.notify("Please enter a value", severity="warning")
            return

        try:
            field = ConditionField(field_val)
            operator = ConditionOperator(op_val)
        except ValueError:
            self.notify("Invalid field or operator selection", severity="error")
            return

        condition = RuleCondition(
            field=field,
            operator=operator,
            value=value,
            case_sensitive=False,
        )
        self.add_condition(condition)
        value_input.value = ""
        self.notify(f"Added: {self.format_condition(condition)}")

    def action_remove_condition(self) -> None:
        """Remove the currently selected condition from the table."""
        if not self.working_conditions:
            return

        try:
            table = self.query_one("#conditions-table", DataTable)
            cursor_row = table.cursor_row
            if cursor_row is not None and 0 <= cursor_row < len(self.working_conditions):
                removed = self.working_conditions[cursor_row]
                self.remove_condition(cursor_row)
                self.notify(f"Removed: {self.format_condition(removed)}")
        except NoMatches:
            logger.debug("Conditions table not mounted, cannot remove condition")

    def action_toggle_logic(self) -> None:
        """Toggle AND/OR logic via action binding."""
        self.toggle_logic()
        self.notify(f"Logic: {self.working_logic.value.upper()}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in the value input to add a condition."""
        if event.input.id == "value-input":
            self.action_add_condition()

    def on_key(self, event) -> None:
        """Handle key events for delete and tab."""
        if event.key in ("delete", "backspace"):
            self.action_remove_condition()
            event.prevent_default()
        elif event.key == "tab":
            self.action_toggle_logic()
            event.prevent_default()
