"""Export/import shared parameter category bindings via Microsoft Excel.

Reuses Excel COM interop pattern from PlaceInRoomsSpaces.
Reuses parameter_category_binding.py from B8 for all Revit API calls.

Two modes via CommandSwitchWindow:
- Export: reads current bindings, fills Excel matrix
- Import: reads Excel matrix, diffs against current state, applies changes
"""

import os
import sys

import clr

from pyrevit import forms
from pyrevit import revit
from pyrevit import script

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from parameter_category_binding import (
    get_bound_categories,
    get_project_categories,
    list_shared_parameters,
    set_bound_categories,
)

doc = revit.doc
output = script.get_output()


def open_excel():
    """Open Excel via COM interop. Returns (app, workbook) or (None, None)."""
    try:
        excel_type = clr.GetClrType(
            System.Type.GetTypeFromProgID("Excel.Application")
        )
        excel = System.Activator.CreateInstance(excel_type)
        excel.Visible = True

        # Get or create workbook
        try:
            wb = excel.ActiveWorkbook
            if wb is None:
                wb = excel.Workbooks.Add()
        except Exception:
            wb = excel.Workbooks.Add()

        return excel, wb
    except Exception as exc:
        output.print_md("**Error**: Cannot open Excel: {}".format(exc))
        return None, None


def export_bindings():
    """Export current parameter ↔ category bindings to Excel."""
    params = list_shared_parameters()
    if not params:
        forms.alert("No shared parameter file found.", title="Param Excel Export")
        return

    categories = get_project_categories()
    if not categories:
        forms.alert("No project categories found.", title="Param Excel Export")
        return

    excel, wb = open_excel()
    if excel is None:
        return

    ws = wb.ActiveSheet
    if ws is None:
        ws = wb.Worksheets.Add()

    # Header row
    ws.Cells(1, 1).Value = "Parameter Name"
    ws.Cells(1, 2).Value = "Parameter GUID"
    ws.Cells(1, 3).Value = "Group"

    col_offset = 4
    cat_name_to_col = {}
    for idx, (builtin_cat, cat_name) in enumerate(categories):
        col = col_offset + idx
        ws.Cells(1, col).Value = cat_name
        cat_name_to_col[builtin_cat] = col

    # Data rows
    row = 2
    for p in params:
        ws.Cells(row, 1).Value = p["name"]
        ws.Cells(row, 2).Value = p["guid"]
        ws.Cells(row, 3).Value = p["group_name"]

        definition = p["definition"]
        bound_cats = get_bound_categories(definition)

        for builtin_cat, col in cat_name_to_col.items():
            ws.Cells(row, col).Value = 1 if builtin_cat in bound_cats else 0

        row += 1

    # Hide GUID column
    ws.Columns(2).Hidden = True

    output.print_md("# Export Complete")
    output.print_md(
        "Exported **{} parameters** × **{} categories** to Excel.".format(
            len(params), len(categories)
        )
    )


def import_bindings():
    """Import parameter ↔ category bindings from Excel."""
    params = list_shared_parameters()
    if not params:
        forms.alert("No shared parameter file found.", title="Param Excel Import")
        return

    categories = get_project_categories()
    if not categories:
        forms.alert("No project categories found.", title="Param Excel Import")
        return

    excel, wb = open_excel()
    if excel is None:
        return

    ws = wb.ActiveSheet
    if ws is None:
        output.print_md("**Error**: No active sheet.")
        return

    # Build map: GUID -> {BuiltInCategory: value}
    guid_to_bindings = {}
    guid_to_name = {}

    # Read headers (row 1)
    col_offset = 4
    cat_idx_to_builtin = {}
    for idx, (builtin_cat, cat_name) in enumerate(categories):
        col_idx = col_offset + idx
        cat_idx_to_builtin[col_idx] = builtin_cat

    # Read data rows
    row = 2
    while True:
        param_name_cell = ws.Cells(row, 1).Value
        guid_cell = ws.Cells(row, 2).Value

        if param_name_cell is None or guid_cell is None:
            break

        param_name = str(param_name_cell)
        guid = str(guid_cell)

        bindings = {}
        for col_idx, builtin_cat in cat_idx_to_builtin.items():
            val = ws.Cells(row, col_idx).Value
            if val is not None and int(val) == 1:
                bindings[builtin_cat] = True

        guid_to_bindings[guid] = set(bindings.keys())
        guid_to_name[guid] = param_name
        row += 1

    # Build GUID -> definition map
    guid_to_def = {}
    for p in params:
        guid_to_def[p["guid"]] = p["definition"]

    # Apply changes (diff)
    changes = 0
    errors = 0

    for guid, selected_cats in guid_to_bindings.items():
        definition = guid_to_def.get(guid)
        if definition is None:
            errors += 1
            output.print_md("- Unknown GUID: {} ({})".format(guid, guid_to_name.get(guid, "?")))
            continue

        # Current state
        current = get_bound_categories(definition)

        # Diff
        if selected_cats == current:
            continue

        try:
            set_bound_categories(definition, selected_cats)
            changes += 1
        except Exception as exc:
            errors += 1
            output.print_md("- Error updating '{}': {}".format(
                guid_to_name.get(guid, guid), exc
            ))

    output.print_md("# Import Complete")
    output.print_md(
        "**{} parameters updated** | {} errors | {} unchanged".format(
            changes, errors,
            len(guid_to_bindings) - changes - errors,
        )
    )


def main():
    try:
        result = forms.CommandSwitchWindow.show(
            ["Export to Excel", "Import from Excel"],
            message="Parameter Category — Excel I/O",
        )
    except Exception:
        output.print_md("**Cancelled**")
        return

    if result == "Export to Excel":
        export_bindings()
    elif result == "Import from Excel":
        import_bindings()


if __name__ == "__main__":
    main()
