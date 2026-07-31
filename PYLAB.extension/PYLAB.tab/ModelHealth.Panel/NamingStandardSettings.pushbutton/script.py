"""Naming standard editor — DataGridView for team naming convention config.

Shift-click: opens this editor (management mode).
Default click: reserved for D4 naming check (to be implemented).
"""

import json
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
    ComboBox,
    ComboBoxStyle,
    DataGridView,
    DataGridViewAutoSizeColumnsMode,
    DataGridViewCellStyle,
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
    TextBox,
)

from pyrevit import forms
from pyrevit import revit

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from config_loader import load_json, save_json

CONFIG_PATH = os.path.join(SCRIPT_DIR, "naming_standards.json")
TARGET_KEYS = ["views", "sheets", "families", "filters", "schedules"]


class NamingStandardEditor(Form):
    """WinForms dialog for editing naming convention rules."""

    def __init__(self):
        Form.__init__(self)
        self.Text = "Naming Standard Editor"
        self.Size = Size(900, 560)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        # Load config
        self._config = load_json(CONFIG_PATH)
        self._current_target = "views"

        self._build_ui()

    def _build_ui(self):
        # Target selector (dropdown)
        target_label = Label()
        target_label.Text = "Element type:"
        target_label.Location = Point(12, 15)
        target_label.Size = Size(80, 23)
        self.Controls.Add(target_label)

        self._target_combo = ComboBox()
        self._target_combo.Location = Point(95, 12)
        self._target_combo.Size = Size(130, 23)
        self._target_combo.DropDownStyle = ComboBoxStyle.DropDownList
        self._target_combo.Items.AddRange(TARGET_KEYS)
        self._target_combo.SelectedIndex = 0
        self._target_combo.SelectedIndexChanged += self._on_target_changed
        self.Controls.Add(self._target_combo)

        # DataGridView for segment rules
        self._grid = DataGridView()
        self._grid.Location = Point(12, 45)
        self._grid.Size = Size(860, 400)
        self._grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self._grid.AllowUserToAddRows = True
        self._grid.AllowUserToDeleteRows = True
        self._grid.RowHeadersVisible = False
        self._grid.SelectionMode = self._grid.SelectionMode.CellSelect

        # Columns: name, type, variants, min_len, max_len
        col_name = DataGridViewTextBoxColumn()
        col_name.HeaderText = "Segment Name"
        col_name.Name = "name"
        col_name.FillWeight = 20
        self._grid.Columns.Add(col_name)

        col_type = DataGridViewComboBoxColumn()
        col_type.HeaderText = "Type"
        col_type.Name = "type"
        col_type.Items.AddRange("closed", "freetext")
        col_type.FillWeight = 10
        self._grid.Columns.Add(col_type)

        col_variants = DataGridViewTextBoxColumn()
        col_variants.HeaderText = "Variants (comma)"
        col_variants.Name = "variants"
        col_variants.FillWeight = 30
        self._grid.Columns.Add(col_variants)

        col_min = DataGridViewTextBoxColumn()
        col_min.HeaderText = "Min Length"
        col_min.Name = "min_len"
        col_min.FillWeight = 10
        self._grid.Columns.Add(col_min)

        col_max = DataGridViewTextBoxColumn()
        col_max.HeaderText = "Max Length"
        col_max.Name = "max_len"
        col_max.FillWeight = 10
        self._grid.Columns.Add(col_max)

        self.Controls.Add(self._grid)

        # Delimiter
        delim_label = Label()
        delim_label.Text = "Delimiter:"
        delim_label.Location = Point(12, 455)
        delim_label.Size = Size(60, 23)
        self.Controls.Add(delim_label)

        self._delim_text = TextBox()
        self._delim_text.Location = Point(75, 452)
        self._delim_text.Size = Size(40, 23)
        self._delim_text.Text = "_"
        self._delim_text.TextChanged += self._on_delimiter_changed
        self.Controls.Add(self._delim_text)

        # Save button
        save_btn = Button()
        save_btn.Text = "Save"
        save_btn.Location = Point(720, 450)
        save_btn.Size = Size(75, 28)
        save_btn.Click += self._on_save
        self.Controls.Add(save_btn)

        # Cancel button
        cancel_btn = Button()
        cancel_btn.Text = "Cancel"
        cancel_btn.Location = Point(797, 450)
        cancel_btn.Size = Size(75, 28)
        cancel_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(cancel_btn)

        # Load initial data
        self._load_target("views")

    def _load_target(self, target):
        """Populate grid from config for given target."""
        self._current_target = target
        self._grid.Rows.Clear()

        ruleset = self._config.get(target, {})
        self._delim_text.Text = ruleset.get("delimiter", "_")

        for seg in ruleset.get("segments", []):
            row_idx = self._grid.Rows.Add()
            row = self._grid.Rows[row_idx]
            row.Cells["name"].Value = seg.get("name", "")
            row.Cells["type"].Value = seg.get("type", "freetext")
            variants = seg.get("variants", [])
            row.Cells["variants"].Value = ", ".join(variants) if variants else ""
            row.Cells["min_len"].Value = str(seg.get("min_len", ""))
            row.Cells["max_len"].Value = str(seg.get("max_len", ""))

    def _save_target(self, target):
        """Write grid data back to config for current target."""
        segments = []
        for row in self._grid.Rows:
            if row.IsNewRow:
                continue
            name_val = str(row.Cells["name"].Value or "").strip()
            if not name_val:
                continue

            seg = {"name": name_val}

            seg_type = str(row.Cells["type"].Value or "freetext").strip()
            seg["type"] = seg_type if seg_type in ("closed", "freetext") else "freetext"

            if seg["type"] == "closed":
                variants_raw = str(row.Cells["variants"].Value or "")
                seg["variants"] = [
                    v.strip() for v in variants_raw.split(",") if v.strip()
                ]

            min_raw = str(row.Cells["min_len"].Value or "0").strip()
            if min_raw and min_raw.isdigit():
                seg["min_len"] = int(min_raw)

            max_raw = str(row.Cells["max_len"].Value or "").strip()
            if max_raw and max_raw.isdigit():
                seg["max_len"] = int(max_raw)

            segments.append(seg)

        self._config[target] = {
            "delimiter": self._delim_text.Text or "_",
            "segments": segments,
        }

    def _on_target_changed(self, sender, event_args):
        new_target = self._target_combo.SelectedItem
        if new_target != self._current_target:
            self._save_target(self._current_target)
            self._load_target(new_target)

    def _on_delimiter_changed(self, sender, event_args):
        pass  # saved together with target on switch/save

    def _on_save(self, sender, event_args):
        self._save_target(self._current_target)
        try:
            save_json(CONFIG_PATH, self._config)
            MessageBox.Show(
                self,
                "Naming standards saved.",
                "Saved",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information,
            )
        except Exception as exc:
            MessageBox.Show(
                self,
                "Failed to save: {}".format(exc),
                "Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error,
            )


def show_editor():
    form = NamingStandardEditor()
    form.ShowDialog()


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def main():
    if get_shiftclick_state():
        show_editor()
    else:
        forms.alert(
            "D4 naming check not yet implemented.\n"
            "Shift-click to open the naming standard editor.",
            title="Naming Standard",
        )


if __name__ == "__main__":
    main()
