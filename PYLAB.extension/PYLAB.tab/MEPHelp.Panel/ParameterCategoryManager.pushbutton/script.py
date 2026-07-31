"""Parameter Category Manager — matrix editor for shared parameter bindings.

Rows = shared parameters, columns = project categories (checkboxes).
Textbox filter for categories. "Apply" button diffs current vs selected state
and calls set_bound_categories only for changed parameters.
"""

import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from pyrevit import forms
from pyrevit import revit
from pyrevit import script

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
    CheckBox,
    DataGridView,
    DataGridViewAutoSizeColumnsMode,
    DataGridViewCheckBoxColumn,
    DataGridViewTextBoxColumn,
    DialogResult,
    Form,
    FormBorderStyle,
    FormStartPosition,
    Label,
    MessageBox,
    MessageBoxButtons,
    MessageBoxIcon,
    TextBox,
)

doc = revit.doc
output = script.get_output()

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from parameter_category_binding import (
    create_category_set,
    get_bound_categories,
    get_project_categories,
    list_shared_parameters,
    set_bound_categories,
)


class ParameterCategoryForm(Form):
    """WinForms DataGridView matrix for parameter ↔ category binding."""

    def __init__(self, params_list, categories_list):
        Form.__init__(self)
        self.Text = "Parameter Category Manager"
        self.Size = Size(1100, 700)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._params = params_list  # [{name, guid, group_name, definition}, ...]
        self._categories = categories_list  # [(BuiltInCategory, name), ...]

        # Precompute current bindings
        self._current_bindings = {}  # param_guid -> set of BuiltInCategory
        self._col_index = {}  # BuiltInCategory -> column index

        self._build_ui()

    def _build_ui(self):
        y = 12

        # Hint
        hint = Label()
        hint.Text = (
            "Rows = shared parameters  |  Columns = project categories  "
            "|  Check = bind parameter to category"
        )
        hint.Location = Point(12, y)
        hint.Size = Size(800, 20)
        self.Controls.Add(hint)
        y += 28

        # Category filter
        filter_label = Label()
        filter_label.Text = "Filter categories:"
        filter_label.Location = Point(12, y + 3)
        filter_label.Size = Size(100, 20)
        self.Controls.Add(filter_label)

        self._filter_box = TextBox()
        self._filter_box.Location = Point(115, y)
        self._filter_box.Size = Size(200, 23)
        self._filter_box.TextChanged += self._on_filter_changed
        self.Controls.Add(self._filter_box)
        y += 32

        # DataGridView
        self._grid = DataGridView()
        self._grid.Location = Point(12, y)
        self._grid.Size = Size(1060, 520)
        self._grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.AllCells
        self._grid.AllowUserToAddRows = False
        self._grid.AllowUserToDeleteRows = False
        self._grid.RowHeadersVisible = False
        self._grid.ColumnHeadersHeightSizeMode = (
            self._grid.ColumnHeadersHeightSizeMode.AutoSize
        )
        self.Controls.Add(self._grid)

        # Build columns
        # Column 0: parameter name
        col_name = DataGridViewTextBoxColumn()
        col_name.HeaderText = "Parameter"
        col_name.Name = "param_name"
        col_name.ReadOnly = True
        col_name.Frozen = True
        col_name.MinimumWidth = 180
        self._grid.Columns.Add(col_name)

        # Column 1: group
        col_group = DataGridViewTextBoxColumn()
        col_group.HeaderText = "Group"
        col_group.Name = "param_group"
        col_group.ReadOnly = True
        col_group.MinimumWidth = 120
        self._grid.Columns.Add(col_group)

        # Checkbox columns per category
        col_idx = 2
        for builtin_cat, cat_name in self._categories:
            col = DataGridViewCheckBoxColumn()
            col.HeaderText = cat_name
            col.Name = "cat_{}".format(builtin_cat.value__)
            col.Width = 30
            col.Visible = True
            self._grid.Columns.Add(col)
            self._col_index[builtin_cat] = col_idx
            col_idx += 1

        y += 530

        # Apply button
        apply_btn = Button()
        apply_btn.Text = "Apply"
        apply_btn.Location = Point(900, y)
        apply_btn.Size = Size(80, 30)
        apply_btn.Click += self._on_apply
        self.Controls.Add(apply_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(990, y)
        close_btn.Size = Size(80, 30)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

        # Populate rows
        self._populate_grid()

    def _populate_grid(self):
        self._grid.Rows.Clear()

        for p in self._params:
            row_idx = self._grid.Rows.Add()
            row = self._grid.Rows[row_idx]

            row.Cells["param_name"].Value = p["name"]
            row.Cells["param_group"].Value = p["group_name"]

            # Compute current bindings
            definition = p["definition"]
            bound_cats = get_bound_categories(definition)
            self._current_bindings[p["guid"]] = bound_cats

            # Set checkbox state
            for builtin_cat, cat_name in self._categories:
                col_name = "cat_{}".format(builtin_cat.value__)
                try:
                    cell = row.Cells[col_name]
                    cell.Value = builtin_cat in bound_cats
                except Exception:
                    pass

        self._apply_filter()

    def _apply_filter(self):
        filter_text = self._filter_box.Text.lower().strip()
        # Show/hide columns based on filter
        for builtin_cat, cat_name in self._categories:
            col_name = "cat_{}".format(builtin_cat.value__)
            try:
                col = self._grid.Columns[col_name]
                col.Visible = (
                    not filter_text or filter_text in cat_name.lower()
                )
            except Exception:
                pass

    def _on_filter_changed(self, sender, event_args):
        self._apply_filter()

    def _on_apply(self, sender, event_args):
        # Confirm
        result = MessageBox.Show(
            self,
            "Apply category binding changes?\n\n"
            "Changing bindings may hide or expose data in instances.\n"
            "This operation is not trivially reversible.",
            "Confirm",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Warning,
        )

        if result != DialogResult.Yes:
            return

        changes = 0
        errors = 0

        for row_idx in range(self._grid.Rows.Count):
            row = self._grid.Rows[row_idx]
            if row.IsNewRow:
                continue

            param_name = str(row.Cells["param_name"].Value or "")
            param_idx = row_idx
            if param_idx >= len(self._params):
                continue

            p = self._params[param_idx]
            definition = p["definition"]
            guid = p["guid"]

            # Read current checkbox state
            selected_cats = set()
            for builtin_cat, cat_name in self._categories:
                col_name = "cat_{}".format(builtin_cat.value__)
                try:
                    cell = row.Cells[col_name]
                    if cell.Value is not None and bool(cell.Value):
                        selected_cats.Add(builtin_cat)
                except Exception:
                    pass

            # Diff with saved state
            saved = self._current_bindings.get(guid, set())
            added = selected_cats - saved
            removed = saved - selected_cats

            if not added and not removed:
                continue

            # Apply new set (ReInsert with full set)
            if not selected_cats:
                # Remove all bindings
                try:
                    from parameter_category_binding import remove_binding

                    remove_binding(definition)
                    self._current_bindings[guid] = set()
                    changes += 1
                except Exception as exc:
                    errors += 1
                    output.print_md(
                        "- Error removing '{}': {}".format(param_name, exc)
                    )
            else:
                try:
                    set_bound_categories(definition, selected_cats)
                    self._current_bindings[guid] = selected_cats
                    changes += 1
                except Exception as exc:
                    errors += 1
                    output.print_md(
                        "- Error updating '{}': {}".format(param_name, exc)
                    )

        output.print_md("# Parameter Category Manager — Results")
        output.print_md(
            "**{} parameters updated** | {} errors".format(changes, errors)
        )
        self.Close()


def main():
    params = list_shared_parameters()
    if not params:
        forms.alert(
            "No shared parameter file found.\n"
            "Open a shared parameter file first (Manage > Shared Parameters).",
            title="Parameter Category Manager",
        )
        return

    categories = get_project_categories()
    if not categories:
        forms.alert(
            "No model categories found in this project.",
            title="Parameter Category Manager",
        )
        return

    form = ParameterCategoryForm(params, categories)
    form.ShowDialog()


if __name__ == "__main__":
    main()
