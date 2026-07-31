"""Check for missing/empty required parameters on elements by category.

Shared parameters are identified by GUID (not display name).
Shift-click opens the requirement editor.
"""

import json
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    FilteredElementCollector,
)
from pyrevit import forms
from pyrevit import revit

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
    ComboBox,
    ComboBoxStyle,
    DataGridView,
    DataGridViewAutoSizeColumnsMode,
    DataGridViewComboBoxColumn,
    DataGridViewTextBoxColumn,
    DialogResult,
    Form,
    FormBorderStyle,
    FormStartPosition,
    Label,
    MessageBox,
    MessageBoxButtons,
    MessageBoxIcon,
)

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from health_report import HealthReport
from config_loader import load_json, save_json

doc = revit.doc
app = revit.app

CONFIG_PATH = os.path.join(SCRIPT_DIR, "required_parameters.json")


def get_available_shared_parameters():
    """Get list of (name, guid) from shared parameter file."""
    results = []
    try:
        spf = app.OpenSharedParameterFile()
        if spf is not None:
            for group in spf.Groups:
                for definition in group.Definitions:
                    try:
                        results.append((
                            "{} ({})".format(definition.Name, group.Name),
                            definition.GUID.ToString(),
                        ))
                    except Exception:
                        pass
    except Exception:
        pass
    return sorted(results, key=lambda x: x[0].lower())


def get_model_categories():
    """Get list of model BuiltInCategory values with names."""
    results = []
    all_cats = System.Enum.GetValues(clr.GetClrType(BuiltInCategory))
    for cat in all_cats:
        try:
            cat_obj = doc.Settings.Categories.get_Item(cat)
            if cat_obj is not None and cat_obj.CategoryType.ToString() == "Model":
                results.append((cat, cat_obj.Name))
        except Exception:
            pass
    return sorted(results, key=lambda x: x[1].lower())


def run_check():
    """Check elements against required_parameters.json."""
    config = load_json(CONFIG_PATH, default=[])
    if not config:
        forms.alert(
            "No required parameters configured.\n"
            "Shift-click to open the editor and add requirements.",
            title="Missing Parameters",
        )
        return

    report = HealthReport("Missing Parameters Check")

    # Build GUID -> label map
    guid_label = {}
    for entry in config:
        guid_label[entry["guid"]] = entry.get("label", entry["guid"])

    # Group entries by category
    cat_entries = {}
    for entry in config:
        cat_name = entry.get("category", "")
        if cat_name not in cat_entries:
            cat_entries[cat_name] = []
        cat_entries[cat_name].append(entry)

    for cat_name, entries in sorted(cat_entries.items()):
        sec_idx = report.add_section(cat_name)

        # Find BuiltInCategory
        builtin_cat = None
        for cat, name in get_model_categories():
            if name == cat_name:
                builtin_cat = cat
                break

        if builtin_cat is None:
            report.add_entry(sec_idx, "warn", cat_name, "Category not found in model")
            continue

        elements = FilteredElementCollector(doc).OfCategory(builtin_cat).OfClass(Element)
        element_count = 0
        missing_count = 0

        for elem in elements:
            if elem is None:
                continue
            element_count += 1
            missing_params = []

            for entry in entries:
                guid_str = entry["guid"]
                label = entry.get("label", guid_str)
                try:
                    import System
                    guid = System.Guid(guid_str)
                except Exception:
                    missing_params.append(label + " (invalid GUID)")
                    continue

                param = elem.get_Parameter(guid)
                if param is None:
                    missing_params.append(label + " — missing")
                elif not param.HasValue:
                    missing_params.append(label + " — empty")

            if missing_params:
                missing_count += 1
                elem_name = elem.Name if elem.Name else "Element {}".format(
                    elem.Id.IntegerValue
                )
                report.add_entry(
                    sec_idx,
                    "fail",
                    elem_name,
                    "; ".join(missing_params),
                )

        if element_count > 0 and missing_count == 0:
            report.add_entry(
                sec_idx,
                "pass",
                "All {} elements".format(element_count),
                "All required parameters present",
            )
        elif element_count == 0:
            report.add_entry(sec_idx, "pass", cat_name, "No elements in category")

    report.print_report()


class RequirementEditor(Form):
    """DataGridView editor for required_parameters.json."""

    def __init__(self, config, available_params, categories):
        Form.__init__(self)
        self.Text = "Required Parameters Editor"
        self.Size = Size(800, 500)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._config = config
        self._available_params = available_params  # [(display, guid), ...]
        self._categories = categories  # [(BuiltInCategory, name), ...]
        self._build_ui()

    def _build_ui(self):
        self._grid = DataGridView()
        self._grid.Location = Point(12, 12)
        self._grid.Size = Size(760, 390)
        self._grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self._grid.AllowUserToAddRows = True
        self._grid.AllowUserToDeleteRows = True
        self._grid.RowHeadersVisible = False

        # Category column (combo)
        col_cat = DataGridViewComboBoxColumn()
        col_cat.HeaderText = "Category"
        col_cat.Name = "category"
        col_cat.FillWeight = 25
        cat_names = [c[1] for c in self._categories]
        col_cat.Items.AddRange(System.Array[System.String](cat_names))
        self._grid.Columns.Add(col_cat)

        # Parameter column (combo)
        col_param = DataGridViewComboBoxColumn()
        col_param.HeaderText = "Parameter"
        col_param.Name = "parameter"
        col_param.FillWeight = 40
        param_displays = [p[0] for p in self._available_params]
        col_param.Items.AddRange(System.Array[System.String](param_displays))
        self._grid.Columns.Add(col_param)

        # Label column (text)
        col_label = DataGridViewTextBoxColumn()
        col_label.HeaderText = "Label (optional)"
        col_label.Name = "label"
        col_label.FillWeight = 20
        self._grid.Columns.Add(col_label)

        self.Controls.Add(self._grid)

        # Buttons
        save_btn = Button()
        save_btn.Text = "Save"
        save_btn.Location = Point(610, 415)
        save_btn.Size = Size(80, 28)
        save_btn.Click += self._on_save
        self.Controls.Add(save_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(695, 415)
        close_btn.Size = Size(80, 28)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

        self._load_data()

    def _load_data(self):
        for entry in self._config:
            idx = self._grid.Rows.Add()
            row = self._grid.Rows[idx]
            row.Cells["category"].Value = entry.get("category", "")
            row.Cells["label"].Value = entry.get("label", "")

            # Find parameter display name from GUID
            guid_str = entry.get("guid", "")
            param_display = ""
            for display, guid in self._available_params:
                if guid == guid_str:
                    param_display = display
                    break
            row.Cells["parameter"].Value = param_display

    def _on_save(self, sender, event_args):
        new_config = []
        for row in self._grid.Rows:
            if row.IsNewRow:
                continue
            cat_name = str(row.Cells["category"].Value or "").strip()
            param_display = str(row.Cells["parameter"].Value or "").strip()
            label = str(row.Cells["label"].Value or "").strip()

            if not cat_name or not param_display:
                continue

            # Extract GUID from parameter display
            guid = ""
            for display, g in self._available_params:
                if display == param_display:
                    guid = g
                    break

            if not guid:
                continue

            new_config.append({
                "category": cat_name,
                "guid": guid,
                "label": label if label else param_display.split(" (")[0],
            })

        save_json(CONFIG_PATH, new_config)
        MessageBox.Show(
            self, "Saved {} requirements.".format(len(new_config)),
            "Saved", MessageBoxButtons.OK, MessageBoxIcon.Information,
        )


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def main():
    if get_shiftclick_state():
        params = get_available_shared_parameters()
        categories = get_model_categories()
        config = load_json(CONFIG_PATH, default=[])
        form = RequirementEditor(config, params, categories)
        form.ShowDialog()
    else:
        run_check()


if __name__ == "__main__":
    main()
