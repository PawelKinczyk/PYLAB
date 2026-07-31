"""Workset check: audit workset names and find elements on default workset.

Uses FilteredWorksetCollector for workset enumeration and ElementWorksetFilter
to efficiently find elements still on Workset1/default.
"""

import os
import sys

from Autodesk.Revit.DB import (
    Element,
    ElementWorksetFilter,
    FilteredElementCollector,
    FilteredWorksetCollector,
    WorksetKind,
)
from pyrevit import revit

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from health_report import HealthReport

doc = revit.doc


def main():
    report = HealthReport("Workset Check")

    # ---- 1. List all user worksets ----
    sec_list = report.add_section("User Worksets")
    if not doc.IsWorkshared:
        report.add_entry(sec_list, "warn", "Document", "Not workshared — workset check skipped")
        report.print_report()
        return

    worksets = FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset)
    ws_count = 0
    for ws in worksets:
        if ws is None:
            continue
        try:
            report.add_entry(sec_list, "pass", ws.Name, "Kind: {}".format(ws.Kind.ToString()))
            ws_count += 1
        except Exception:
            pass

    # ---- 2. Elements on default workset (Workset1 / id=0) ----
    sec_default = report.add_section("Elements on Default Workset")
    default_workset_id = None

    for ws in FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset):
        try:
            if ws.Name == "Workset1":
                default_workset_id = ws.Id
                break
        except Exception:
            pass

    if default_workset_id is not None:
        try:
            default_filter = ElementWorksetFilter(default_workset_id, False)  # False = match elements ON this workset
            elements_on_default = FilteredElementCollector(doc).WherePasses(default_filter)
            count = elements_on_default.GetElementCount()
            if count > 0:
                report.add_entry(
                    sec_default, "fail",
                    "Workset1 (default)",
                    "{} elements still on default workset — review required".format(count),
                )
            else:
                report.add_entry(
                    sec_default, "pass",
                    "Workset1",
                    "0 elements on default workset",
                )
        except Exception as exc:
            report.add_entry(sec_default, "warn", "Workset1", "Error checking: {}".format(exc))
    else:
        report.add_entry(sec_default, "pass", "Workset1", "No Workset1 found — already cleaned up")

    # ---- 3. Elements per workset summary ----
    sec_summary = report.add_section("Elements per Workset")
    all_elements = FilteredElementCollector(doc).OfClass(Element)
    ws_element_counts = {}

    for elem in all_elements:
        if elem is None:
            continue
        try:
            ws = elem.WorksetId
            if ws.IntegerValue not in ws_element_counts:
                ws_element_counts[ws.IntegerValue] = {"count": 0, "name": ""}
            ws_element_counts[ws.IntegerValue]["count"] += 1
        except Exception:
            pass

    # Resolve workset names
    for ws in FilteredWorksetCollector(doc).OfKind(WorksetKind.UserWorkset):
        try:
            ws_id = ws.Id.IntegerValue
            if ws_id in ws_element_counts:
                ws_element_counts[ws_id]["name"] = ws.Name
        except Exception:
            pass

    for ws_id, info in sorted(ws_element_counts.items()):
        name = info["name"] if info["name"] else "Workset {}".format(ws_id)
        report.add_entry(sec_summary, "pass", name, "{} elements".format(info["count"]))

    report.print_report()


if __name__ == "__main__":
    main()
