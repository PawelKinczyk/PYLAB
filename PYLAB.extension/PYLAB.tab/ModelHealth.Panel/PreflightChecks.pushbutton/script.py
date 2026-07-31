"""Preflight checks: detail lines per view, view author, family size proxy.

Uses HealthReport from D-core for structured reporting.
"""

import os
import sys

from Autodesk.Revit.DB import (
    BuiltInCategory,
    CurveElement,
    Family,
    FilteredElementCollector,
    View,
    WorksharingUtils,
)
from pyrevit import revit

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from health_report import HealthReport

doc = revit.doc


def main():
    report = HealthReport("Preflight Checks")

    # ---- 1. Detail lines per view ----
    sec_lines = report.add_section("Detail Lines per View")
    views = FilteredElementCollector(doc).OfClass(View)
    for view in views:
        if view is None or view.IsTemplate:
            continue
        try:
            lines = (
                FilteredElementCollector(doc, view.Id)
                .OfClass(CurveElement)
                .OfCategory(BuiltInCategory.OST_Lines)
                .GetElementCount()
            )
            status = "warn" if lines > 1000 else "pass"
            detail = "{} detail lines".format(lines)
            if lines > 1000:
                detail += " — consider simplification"
            report.add_entry(sec_lines, status, view.Name, detail)
        except Exception:
            report.add_entry(sec_lines, "warn", view.Name if view.Name else "?", "Could not count lines")

    # ---- 2. View authors ----
    sec_authors = report.add_section("View Authors")
    if not doc.IsWorkshared:
        report.add_entry(sec_authors, "warn", "Document", "Not workshared — author check skipped")
    else:
        for view in views:
            if view is None or view.IsTemplate:
                continue
            try:
                info = WorksharingUtils.GetWorksharingTooltipInfo(doc, view.Id)
                if info is not None:
                    creator = "N/D"
                    last_by = "N/D"
                    try:
                        creator = info.Creator
                    except Exception:
                        pass
                    try:
                        last_by = info.LastChangedBy
                    except Exception:
                        pass
                    report.add_entry(
                        sec_authors, "pass", view.Name,
                        "Creator: {} | Last: {}".format(creator, last_by),
                    )
                else:
                    report.add_entry(sec_authors, "pass", view.Name, "No worksharing info")
            except Exception:
                report.add_entry(sec_authors, "warn", view.Name if view.Name else "?", "Error getting author info")

    # ---- 3. Family size proxy ----
    sec_families = report.add_section("Family Size Proxy")
    families = FilteredElementCollector(doc).OfClass(Family)
    for family in families:
        if family is None:
            continue
        try:
            symbols = family.GetFamilySymbolIds()
            symbol_count = 0 if symbols is None else symbols.Count
            try:
                param_count = len(list(family.Parameters))
            except Exception:
                param_count = 0

            status = "warn" if symbol_count > 50 else "pass"
            detail = "{} types, {} params".format(symbol_count, param_count)
            if symbol_count > 50:
                detail += " — many types"
            report.add_entry(sec_families, status, family.Name, detail)
        except Exception:
            pass

    report.print_report()


if __name__ == "__main__":
    main()
