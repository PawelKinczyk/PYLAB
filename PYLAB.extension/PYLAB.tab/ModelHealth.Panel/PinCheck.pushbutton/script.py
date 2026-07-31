"""Pin check: verify grids, levels, and linked models are pinned.

Flags any unpinned element of these critical types.
"""

import os
import sys

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    Grid,
    Level,
    RevitLinkInstance,
)
from pyrevit import revit

SCRIPT_DIR = os.path.dirname(__file__)
PANEL_DIR = os.path.dirname(SCRIPT_DIR)
if PANEL_DIR not in sys.path:
    sys.path.append(PANEL_DIR)

from health_report import HealthReport

doc = revit.doc


def check_type(collector_class, label, section_index, report):
    """Check all elements of a given type for pin status."""
    elements = FilteredElementCollector(doc).OfClass(collector_class)
    pinned = 0
    unpinned = 0

    for elem in elements:
        if elem is None:
            continue
        try:
            if elem.Pinned:
                pinned += 1
            else:
                unpinned += 1
                report.add_entry(section_index, "fail", elem.Name, "Not pinned")
        except Exception:
            unpinned += 1
            try:
                name = elem.Name
            except Exception:
                name = "?"
            report.add_entry(section_index, "fail", name, "Not pinned (or error checking)")

    return pinned, unpinned


def main():
    report = HealthReport("Pin Check")

    # Grids
    sec_grids = report.add_section("Grids")
    g_pinned, g_unpinned = check_type(Grid, "Grid", sec_grids, report)
    if g_unpinned == 0 and g_pinned > 0:
        report.add_entry(sec_grids, "pass", "All grids", "{} of {} pinned".format(g_pinned, g_pinned + g_unpinned))
    elif g_pinned + g_unpinned == 0:
        report.add_entry(sec_grids, "pass", "Grids", "None in model")

    # Levels
    sec_levels = report.add_section("Levels")
    l_pinned, l_unpinned = check_type(Level, "Level", sec_levels, report)
    if l_unpinned == 0 and l_pinned > 0:
        report.add_entry(sec_levels, "pass", "All levels", "{} of {} pinned".format(l_pinned, l_pinned + l_unpinned))
    elif l_pinned + l_unpinned == 0:
        report.add_entry(sec_levels, "pass", "Levels", "None in model")

    # Linked models
    sec_links = report.add_section("Linked Models")
    r_pinned, r_unpinned = check_type(RevitLinkInstance, "Link", sec_links, report)
    if r_unpinned == 0 and r_pinned > 0:
        report.add_entry(sec_links, "pass", "All links", "{} of {} pinned".format(r_pinned, r_pinned + r_unpinned))
    elif r_pinned + r_unpinned == 0:
        report.add_entry(sec_links, "pass", "Linked models", "None in model")

    report.print_report()


if __name__ == "__main__":
    main()
