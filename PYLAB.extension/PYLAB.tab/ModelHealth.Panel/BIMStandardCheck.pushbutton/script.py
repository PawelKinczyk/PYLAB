"""BIM Standard Compliance check — umbrella over D4 (naming), D5 (params), and sheets.

Loads naming_standards.json from NamingStandardSettings, required_parameters.json
from MissingParamCheck, and required_sheets.json from local folder.
"""

import clr
import os
import sys

from Autodesk.Revit.DB import (
    BuiltInCategory,
    Element,
    FilteredElementCollector,
    View,
    ViewSchedule,
    ViewSheet,
    ViewType,
)
from pyrevit import forms
from pyrevit import revit

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from health_report import HealthReport
from config_loader import load_json
from naming_engine import validate_name

doc = revit.doc
app = revit.app

# Paths to configs
NAMING_CONFIG_DIR = os.path.join(
    PANEL_DIR, "NamingStandardSettings.pushbutton"
)
NAMING_CONFIG_PATH = os.path.join(NAMING_CONFIG_DIR, "naming_standards.json")

MISSING_PARAM_DIR = os.path.join(
    PANEL_DIR, "MissingParamCheck.pushbutton"
)
MISSING_PARAM_PATH = os.path.join(MISSING_PARAM_DIR, "required_parameters.json")

SHEETS_CONFIG_PATH = os.path.join(SCRIPT_DIR, "required_sheets.json")


def check_naming(report):
    """Run naming convention check on views, sheets, schedules."""
    naming_config = load_json(NAMING_CONFIG_PATH, default={})
    if not naming_config:
        report.add_entry(report.add_section("Naming"), "warn", "Config", "No naming_standards.json configured")
        return

    # Views (by ViewType)
    views = FilteredElementCollector(doc).OfClass(View)
    for view in views:
        if view is None or view.IsTemplate:
            continue

        # Determine target key based on view type
        if isinstance(view, ViewSheet):
            target = "sheets"
        elif isinstance(view, ViewSchedule):
            target = "schedules"
        else:
            target = "views"

        ruleset = naming_config.get(target)
        if ruleset is None:
            continue

        name = view.Name if view.Name else ""
        violations = validate_name(name, ruleset)

        sec_idx = report.add_section("Naming — {}".format(target))

        if violations:
            report.add_entry(
                sec_idx, "fail", name,
                "; ".join(str(v) for v in violations),
            )
        else:
            report.add_entry(sec_idx, "pass", name, "")


def check_missing_params(report):
    """Check for missing/empty required parameters per D5 config."""
    param_config = load_json(MISSING_PARAM_PATH, default=[])
    if not param_config:
        report.add_entry(
            report.add_section("Required Parameters"), "warn",
            "Config", "No required_parameters.json configured",
        )
        return

    # Group by category
    cat_entries = {}
    for entry in param_config:
        cat_name = entry.get("category", "")
        if cat_name not in cat_entries:
            cat_entries[cat_name] = []
        cat_entries[cat_name].append(entry)

    for cat_name, entries in sorted(cat_entries.items()):
        sec_idx = report.add_section("Params — {}".format(cat_name))

        # Find BuiltInCategory
        builtin_cat = None
        all_cats = System.Enum.GetValues(clr.GetClrType(BuiltInCategory))
        for cat in all_cats:
            try:
                cat_obj = doc.Settings.Categories.get_Item(cat)
                if cat_obj is not None and cat_obj.Name == cat_name:
                    builtin_cat = cat
                    break
            except Exception:
                pass

        if builtin_cat is None:
            report.add_entry(sec_idx, "warn", cat_name, "Category not found")
            continue

        elements = FilteredElementCollector(doc).OfCategory(builtin_cat).OfClass(Element)
        element_count = 0
        missing_count = 0

        for elem in elements:
            if elem is None:
                continue
            element_count += 1
            missing = []

            for entry in entries:
                try:
                    import System
                    guid = System.Guid(entry["guid"])
                except Exception:
                    continue

                param = elem.get_Parameter(guid)
                label = entry.get("label", entry["guid"])
                if param is None:
                    missing.append(label + " — missing")
                elif not param.HasValue:
                    missing.append(label + " — empty")

            if missing:
                missing_count += 1
                report.add_entry(
                    sec_idx, "fail",
                    elem.Name if elem.Name else "Element {}".format(elem.Id.IntegerValue),
                    "; ".join(missing),
                )

        if element_count > 0 and missing_count == 0:
            report.add_entry(
                sec_idx, "pass",
                "All {} elements".format(element_count),
                "All required params present",
            )
        elif element_count == 0:
            report.add_entry(sec_idx, "pass", cat_name, "0 elements")


def check_sheet_completeness(report):
    """Check that required sheet numbers/prefixes exist."""
    sheets_config = load_json(SHEETS_CONFIG_PATH, default=[])
    if not sheets_config:
        report.add_entry(
            report.add_section("Sheet Completeness"), "warn",
            "Config", "No required_sheets.json configured. Shift-click to edit.",
        )
        return

    sec_idx = report.add_section("Sheet Completeness")

    # Get all sheet numbers
    all_sheets = FilteredElementCollector(doc).OfClass(ViewSheet)
    sheet_numbers = set()
    for sheet in all_sheets:
        if sheet is not None and sheet.SheetNumber:
            sheet_numbers.Add(sheet.SheetNumber)

    for req in sheets_config:
        prefix = req.get("prefix", "")
        description = req.get("description", req.get("prefix", "?"))

        found = False
        for sn in sheet_numbers:
            if sn.startswith(prefix):
                found = True
                break

        if found:
            report.add_entry(sec_idx, "pass", prefix, description)
        else:
            report.add_entry(sec_idx, "fail", prefix, "No sheet with prefix '{}' — {}".format(prefix, description))


def main():
    report = HealthReport("BIM Standard Compliance Check")

    check_naming(report)
    check_missing_params(report)
    check_sheet_completeness(report)

    report.print_report()


if __name__ == "__main__":
    main()
