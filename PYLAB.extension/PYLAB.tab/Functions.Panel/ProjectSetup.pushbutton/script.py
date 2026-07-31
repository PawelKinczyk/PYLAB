"""Project Setup Wizard — batch-create worksets, coordination views, and filters.

All operations run inside a single TransactionGroup (all-or-nothing).
Shift-click opens template editor for project_setup_templates.json.
"""

import json
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from Autodesk.Revit.DB import (
    BuiltInCategory,
    ElementId,
    FilteredElementCollector,
    Level,
    ParameterFilterElement,
    TransactionGroup,
    View,
    ViewFamily,
    ViewFamilyType,
    ViewPlan,
    Workset,
    WorksetKind,
)
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

from System.Drawing import Font, Point, Size
from System.Windows.Forms import (
    Application,
    Button,
    CheckBox,
    CheckedListBox,
    ComboBox,
    ComboBoxStyle,
    DataGridView,
    DataGridViewAutoSizeColumnsMode,
    DataGridViewTextBoxColumn,
    DialogResult,
    DockStyle,
    Form,
    FormBorderStyle,
    FormStartPosition,
    GroupBox,
    Label,
    MessageBox,
    MessageBoxButtons,
    MessageBoxIcon,
    ScrollBars,
    TabControl,
    TabPage,
    TextBox,
)

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

SCRIPT_DIR = os.path.dirname(__file__)
TEMPLATES_PATH = os.path.join(SCRIPT_DIR, "project_setup_templates.json")

DEFAULT_TEMPLATES = {
    "MEP": {
        "worksets": [
            "MEP-Wod-Kan",
            "MEP-Wentylacja",
            "MEP-Elektryka",
            "MEP-Grzewcze",
        ],
        "views": [],
        "filters": [],
    },
    "ARC": {
        "worksets": [
            "ARC-Sciany",
            "ARC-Stropy",
            "ARC-Dach",
        ],
        "views": [],
        "filters": [],
    },
    "STR": {
        "worksets": [
            "STR-Slupy",
            "STR-Belki",
            "STR-Stropy",
        ],
        "views": [],
        "filters": [],
    },
}


def load_templates():
    """Load project setup templates from JSON."""
    if os.path.isfile(TEMPLATES_PATH):
        try:
            with open(TEMPLATES_PATH, "r") as fh:
                return json.load(fh)
        except Exception:
            pass
    return DEFAULT_TEMPLATES


def save_templates(data):
    """Save project setup templates to JSON."""
    try:
        with open(TEMPLATES_PATH, "w") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
    except Exception as exc:
        MessageBox.Show(
            Form.ActiveForm,
            "Failed to save: {}".format(exc),
            "Error",
            MessageBoxButtons.OK,
            MessageBoxIcon.Error,
        )


def get_levels():
    """Get all building levels sorted by elevation."""
    levels = FilteredElementCollector(doc).OfClass(Level)
    result = []
    for level in levels:
        if level is not None:
            result.append((level.Id, level.Name, level.Elevation))
    return sorted(result, key=lambda x: x[2])


def get_view_templates():
    """Get all view templates."""
    templates = FilteredElementCollector(doc).OfClass(View)
    result = []
    for v in templates:
        if v is not None and v.IsTemplate:
            result.append((v.Id, v.Name))
    return sorted(result, key=lambda x: x[1].lower())


def get_plan_view_family_types():
    """Get ViewFamilyTypes for FloorPlan and CeilingPlan."""
    vft_collector = FilteredElementCollector(doc).OfClass(ViewFamilyType)
    result = []
    for vft in vft_collector:
        if vft.ViewFamily in (
            ViewFamily.FloorPlan,
            ViewFamily.CeilingPlan,
        ):
            result.append((vft.Id, vft.ViewFamily.ToString(), vft))
    return result


def create_worksets(workset_names):
    """Create worksets. Returns (created, errors)."""
    created = []
    errors = []

    if not doc.IsWorkshared:
        return [], ["Document is not workshared. Enable worksharing first."]

    existing = set()
    try:
        for ws in FilteredElementCollector(doc).OfClass(Workset):
            try:
                existing.Add(ws.Name)
            except Exception:
                pass
    except Exception:
        pass

    for name in workset_names:
        if name in existing:
            continue
        try:
            ws = Workset.Create(doc, name)
            created.append(name)
            existing.Add(name)
        except Exception as exc:
            errors.append("Workset '{}': {}".format(name, exc))

    return created, errors


def create_coordination_views(view_defs):
    """Create coordination views per level. Returns (created, errors)."""
    created = []
    errors = []

    vft_list = get_plan_view_family_types()
    if not vft_list:
        return [], ["No FloorPlan ViewFamilyType found."]

    vft_id = vft_list[0][0]

    levels = get_levels()
    level_map = {}
    for lid, name, elev in levels:
        level_map[name] = lid

    for view_def in view_defs:
        level_name = view_def.get("level", "")
        template_name = view_def.get("template", "")
        view_name = view_def.get("name", "{} - Coordination".format(level_name))

        level_id = level_map.get(level_name)
        if level_id is None:
            errors.append(
                "View '{}': level '{}' not found.".format(
                    view_name, level_name
                )
            )
            continue

        try:
            view = ViewPlan.Create(doc, vft_id, level_id)
            view.Name = view_name

            # Assign view template
            if template_name:
                for vt_id, vt_name in get_view_templates():
                    if vt_name == template_name:
                        view.ViewTemplateId = vt_id
                        break

            created.append(view_name)
        except Exception as exc:
            errors.append("View '{}': {}".format(view_name, exc))

    return created, errors


def create_filters(filter_defs):
    """Create ParameterFilterElement instances. Returns (created, errors)."""
    created = []
    errors = []

    for filter_def in filter_defs:
        name = filter_def.get("name", "")
        if not name:
            continue

        try:
            # Use the simpler Create overload: by category set
            categories = filter_def.get("categories", [])
            cat_ids = []
            for cat_name in categories:
                try:
                    # Find category by name
                    for builtin_cat in System.Enum.GetValues(
                        clr.GetClrType(BuiltInCategory)
                    ):
                        if builtin_cat.ToString() == cat_name:
                            category = doc.Settings.Categories.get_Item(
                                builtin_cat
                            )
                            if category is not None:
                                cat_ids.append(category.Id)
                            break
                except Exception:
                    pass

            if not cat_ids:
                errors.append(
                    "Filter '{}': no valid categories found.".format(name)
                )
                continue

            # Create filter with empty rules (placeholder — rules need
            # ParameterFilterElement.Create overload that supports rules)
            # For v1: just create the filter shell. Rules are configured
            # separately via the filter's UI.
            from System.Collections.Generic import List

            cat_id_list = List[ElementId]()
            for cid in cat_ids:
                cat_id_list.Add(cid)

            try:
                # Try rule-based creation
                filter_elem = ParameterFilterElement.Create(
                    doc, name, cat_id_list
                )
                if filter_elem is not None:
                    created.append(name)
                else:
                    errors.append("Filter '{}': creation returned None.".format(name))
            except Exception as exc:
                errors.append("Filter '{}': {}".format(name, exc))

        except Exception as exc:
            errors.append("Filter '{}': {}".format(name, exc))

    return created, errors


class ProjectSetupForm(Form):
    """WinForms wizard for project setup."""

    def __init__(self, templates):
        Form.__init__(self)
        self.Text = "Project Setup Wizard"
        self.Size = Size(640, 550)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._templates = templates

        self._build_ui()

    def _build_ui(self):
        y = 12

        # Steps to run
        step_group = GroupBox()
        step_group.Text = "Steps to run"
        step_group.Location = Point(12, y)
        step_group.Size = Size(200, 130)
        self.Controls.Add(step_group)

        self._step_worksets = CheckBox()
        self._step_worksets.Text = "Worksets"
        self._step_worksets.Location = Point(15, 25)
        self._step_worksets.Size = Size(170, 23)
        self._step_worksets.Checked = True
        self._step_worksets.CheckedChanged += self._on_step_changed
        step_group.Controls.Add(self._step_worksets)

        self._step_views = CheckBox()
        self._step_views.Text = "Coordination views"
        self._step_views.Location = Point(15, 55)
        self._step_views.Size = Size(170, 23)
        self._step_views.Checked = True
        self._step_views.CheckedChanged += self._on_step_changed
        step_group.Controls.Add(self._step_views)

        self._step_filters = CheckBox()
        self._step_filters.Text = "Filters & parameters"
        self._step_filters.Location = Point(15, 85)
        self._step_filters.Size = Size(170, 23)
        step_group.Controls.Add(self._step_filters)

        # Project type
        type_label = Label()
        type_label.Text = "Project type:"
        type_label.Location = Point(230, y + 3)
        type_label.Size = Size(80, 20)
        self.Controls.Add(type_label)

        self._type_combo = ComboBox()
        self._type_combo.Location = Point(310, y)
        self._type_combo.Size = Size(100, 23)
        self._type_combo.DropDownStyle = ComboBoxStyle.DropDownList
        for key in sorted(self._templates.keys()):
            self._type_combo.Items.Add(key)
        if self._type_combo.Items.Count > 0:
            self._type_combo.SelectedIndex = 0
        self._type_combo.SelectedIndexChanged += self._on_type_changed
        self.Controls.Add(self._type_combo)
        y += 35

        # Preview
        preview_label = Label()
        preview_label.Text = "Preview (read-only):"
        preview_label.Location = Point(230, y)
        preview_label.Size = Size(200, 20)
        self.Controls.Add(preview_label)
        y += 22

        self._preview_box = TextBox()
        self._preview_box.Location = Point(230, y)
        self._preview_box.Size = Size(380, 220)
        self._preview_box.Multiline = True
        self._preview_box.ScrollBars = ScrollBars.Vertical
        self._preview_box.ReadOnly = True
        self._preview_box.Font = Font("Consolas", 9)
        self.Controls.Add(self._preview_box)
        y += 230

        # Run / Close buttons
        run_btn = Button()
        run_btn.Text = "Run"
        run_btn.Location = Point(440, y + 10)
        run_btn.Size = Size(80, 30)
        run_btn.Click += self._on_run
        self.Controls.Add(run_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(530, y + 10)
        close_btn.Size = Size(80, 30)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

        self._update_preview()

    def _get_selected_type(self):
        idx = self._type_combo.SelectedIndex
        if idx < 0 or idx >= self._type_combo.Items.Count:
            return None
        return self._type_combo.Items[idx]

    def _on_type_changed(self, sender, event_args):
        self._update_preview()

    def _on_step_changed(self, sender, event_args):
        self._update_preview()

    def _update_preview(self):
        proj_type = self._get_selected_type()
        if proj_type is None:
            return

        template = self._templates.get(proj_type, {})
        lines = []

        if self._step_worksets.Checked:
            ws = template.get("worksets", [])
            lines.append("--- WORKSETS ---")
            if ws:
                for w in ws:
                    lines.append("  + {}".format(w))
            else:
                lines.append("  (none defined)")
            lines.append("")

        if self._step_views.Checked:
            views = template.get("views", [])
            lines.append("--- COORDINATION VIEWS ---")
            if views:
                for v in views:
                    lines.append(
                        "  + {} (level: {}, template: {})".format(
                            v.get("name", "?"),
                            v.get("level", "?"),
                            v.get("template", "none"),
                        )
                    )
            else:
                lines.append("  (none defined)")
            lines.append("")

        if self._step_filters.Checked:
            filters = template.get("filters", [])
            lines.append("--- FILTERS ---")
            if filters:
                for f in filters:
                    lines.append(
                        "  + {} (categories: {})".format(
                            f.get("name", "?"),
                            ", ".join(f.get("categories", [])),
                        )
                    )
            else:
                lines.append("  (none defined)")

        self._preview_box.Text = "\n".join(lines)

    def _on_run(self, sender, event_args):
        proj_type = self._get_selected_type()
        if proj_type is None:
            MessageBox.Show(
                self,
                "Select a project type.",
                "No type selected",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        template = self._templates.get(proj_type, {})

        run_worksets = self._step_worksets.Checked
        run_views = self._step_views.Checked
        run_filters = self._step_filters.Checked

        if not (run_worksets or run_views or run_filters):
            MessageBox.Show(
                self,
                "Select at least one step to run.",
                "No steps selected",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        # Confirm
        result = MessageBox.Show(
            self,
            "Run project setup for '{}'?\n\n".format(proj_type)
            + "This will modify the document. Ensure you have a backup.",
            "Confirm",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Question,
        )
        if result != DialogResult.Yes:
            return

        # Execute in TransactionGroup
        total_created = 0
        total_errors = 0
        report_lines = ["# Project Setup — {} Configuration".format(proj_type)]

        with TransactionGroup(doc, "Project Setup Wizard") as tg:
            tg.Start()

            if run_worksets:
                ws, errors = create_worksets(template.get("worksets", []))
                total_created += len(ws)
                total_errors += len(errors)
                report_lines.append("## Worksets")
                for w in ws:
                    report_lines.append("- Created: **{}**".format(w))
                for e in errors:
                    report_lines.append("- Error: {}".format(e))

            if run_views:
                vw, errors = create_coordination_views(template.get("views", []))
                total_created += len(vw)
                total_errors += len(errors)
                report_lines.append("## Coordination Views")
                for v in vw:
                    report_lines.append("- Created: **{}**".format(v))
                for e in errors:
                    report_lines.append("- Error: {}".format(e))

            if run_filters:
                fl, errors = create_filters(template.get("filters", []))
                total_created += len(fl)
                total_errors += len(errors)
                report_lines.append("## Filters")
                for f in fl:
                    report_lines.append("- Created: **{}**".format(f))
                for e in errors:
                    report_lines.append("- Error: {}".format(e))

            if total_errors > 0:
                tg.RollBack()
                report_lines.append("---")
                report_lines.append(
                    "**ROLLED BACK** — {} errors occurred. No changes were applied.".format(
                        total_errors
                    )
                )
            else:
                tg.Assimilate()
                report_lines.append("---")
                report_lines.append(
                    "**DONE** — {} items created successfully.".format(total_created)
                )

        output.print_md("\n".join(report_lines))
        self.Close()


class TemplateEditorForm(Form):
    """WinForms editor for project_setup_templates.json."""

    def __init__(self, templates):
        Form.__init__(self)
        self.Text = "Project Setup — Template Editor"
        self.Size = Size(700, 500)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._templates = templates
        self._current_type = "MEP" if "MEP" in templates else sorted(templates.keys())[0]
        self._build_ui()

    def _build_ui(self):
        # Type selector
        type_label = Label()
        type_label.Text = "Project type:"
        type_label.Location = Point(12, 15)
        type_label.Size = Size(80, 23)
        self.Controls.Add(type_label)

        self._type_combo = ComboBox()
        self._type_combo.Location = Point(95, 12)
        self._type_combo.Size = Size(100, 23)
        self._type_combo.DropDownStyle = ComboBoxStyle.DropDownList
        for key in sorted(self._templates.keys()):
            self._type_combo.Items.Add(key)
        if self._current_type in self._templates:
            self._type_combo.SelectedItem = self._current_type
        self._type_combo.SelectedIndexChanged += self._on_type_changed
        self.Controls.Add(self._type_combo)

        # TabControl for worksets / views / filters
        self._tabs = TabControl()
        self._tabs.Location = Point(12, 45)
        self._tabs.Size = Size(660, 360)
        self.Controls.Add(self._tabs)

        # Worksets tab
        ws_page = TabPage()
        ws_page.Text = "Worksets"
        self._ws_grid = DataGridView()
        self._ws_grid.Dock = DockStyle.Fill
        self._ws_grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self._ws_grid.AllowUserToAddRows = True
        self._ws_grid.AllowUserToDeleteRows = True
        self._ws_grid.RowHeadersVisible = False
        col_ws = DataGridViewTextBoxColumn()
        col_ws.HeaderText = "Workset Name"
        col_ws.Name = "name"
        self._ws_grid.Columns.Add(col_ws)
        ws_page.Controls.Add(self._ws_grid)
        self._tabs.TabPages.Add(ws_page)

        # Views tab
        vw_page = TabPage()
        vw_page.Text = "Views"
        self._vw_grid = DataGridView()
        self._vw_grid.Dock = DockStyle.Fill
        self._vw_grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self._vw_grid.AllowUserToAddRows = True
        self._vw_grid.AllowUserToDeleteRows = True
        self._vw_grid.RowHeadersVisible = False
        for hdr in ["View Name", "Level", "Template"]:
            col = DataGridViewTextBoxColumn()
            col.HeaderText = hdr
            col.Name = hdr.lower().replace(" ", "_")
            self._vw_grid.Columns.Add(col)
        vw_page.Controls.Add(self._vw_grid)
        self._tabs.TabPages.Add(vw_page)

        # Filters tab
        fl_page = TabPage()
        fl_page.Text = "Filters"
        self._fl_grid = DataGridView()
        self._fl_grid.Dock = DockStyle.Fill
        self._fl_grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
        self._fl_grid.AllowUserToAddRows = True
        self._fl_grid.AllowUserToDeleteRows = True
        self._fl_grid.RowHeadersVisible = False
        for hdr in ["Filter Name", "Categories (comma)"]:
            col = DataGridViewTextBoxColumn()
            col.HeaderText = hdr
            col.Name = hdr.lower().replace(" ", "_")
            self._fl_grid.Columns.Add(col)
        fl_page.Controls.Add(self._fl_grid)
        self._tabs.TabPages.Add(fl_page)

        # Save / Close
        save_btn = Button()
        save_btn.Text = "Save"
        save_btn.Location = Point(520, 418)
        save_btn.Size = Size(75, 28)
        save_btn.Click += self._on_save
        self.Controls.Add(save_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(600, 418)
        close_btn.Size = Size(75, 28)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

        self._load_current_type()

    def _on_type_changed(self, sender, event_args):
        self._save_current_type()
        self._current_type = self._type_combo.SelectedItem
        self._load_current_type()

    def _load_current_type(self):
        tmpl = self._templates.get(self._current_type, {})

        # Worksets
        self._ws_grid.Rows.Clear()
        for name in tmpl.get("worksets", []):
            idx = self._ws_grid.Rows.Add()
            self._ws_grid.Rows[idx].Cells["name"].Value = name

        # Views
        self._vw_grid.Rows.Clear()
        for v in tmpl.get("views", []):
            idx = self._vw_grid.Rows.Add()
            row = self._vw_grid.Rows[idx]
            row.Cells["view_name"].Value = v.get("name", "")
            row.Cells["level"].Value = v.get("level", "")
            row.Cells["template"].Value = v.get("template", "")

        # Filters
        self._fl_grid.Rows.Clear()
        for f in tmpl.get("filters", []):
            idx = self._fl_grid.Rows.Add()
            row = self._fl_grid.Rows[idx]
            row.Cells["filter_name"].Value = f.get("name", "")
            row.Cells["categories_(comma)"].Value = ", ".join(
                f.get("categories", [])
            )

    def _save_current_type(self):
        if self._current_type is None:
            return

        # Worksets
        worksets = []
        for row in self._ws_grid.Rows:
            if row.IsNewRow:
                continue
            val = str(row.Cells["name"].Value or "").strip()
            if val:
                worksets.append(val)

        # Views
        views = []
        for row in self._vw_grid.Rows:
            if row.IsNewRow:
                continue
            name = str(row.Cells["view_name"].Value or "").strip()
            level = str(row.Cells["level"].Value or "").strip()
            template = str(row.Cells["template"].Value or "").strip()
            if name:
                vdef = {"name": name}
                if level:
                    vdef["level"] = level
                if template:
                    vdef["template"] = template
                views.append(vdef)

        # Filters
        filters = []
        for row in self._fl_grid.Rows:
            if row.IsNewRow:
                continue
            name = str(row.Cells["filter_name"].Value or "").strip()
            cats = str(row.Cells["categories_(comma)"].Value or "").strip()
            if name:
                cat_list = [
                    c.strip() for c in cats.split(",") if c.strip()
                ]
                filters.append({"name": name, "categories": cat_list})

        self._templates[self._current_type] = {
            "worksets": worksets,
            "views": views,
            "filters": filters,
        }

    def _on_save(self, sender, event_args):
        self._save_current_type()
        save_templates(self._templates)
        MessageBox.Show(
            self,
            "Templates saved.",
            "Saved",
            MessageBoxButtons.OK,
            MessageBoxIcon.Information,
        )


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def main():
    if get_shiftclick_state():
        templates = load_templates()
        form = TemplateEditorForm(templates)
        form.ShowDialog()
    else:
        templates = load_templates()
        form = ProjectSetupForm(templates)
        form.ShowDialog()


if __name__ == "__main__":
    main()
