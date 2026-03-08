"""pyRevit entrypoint for FamilyShortcut."""

import os
import sys

from pyrevit import forms
from pyrevit import revit


SCRIPT_DIR = os.path.dirname(__file__)
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from family_shortcut_manager import show_manager_window
from family_shortcut_revit import resolve_symbol, show_revit_warning, start_native_placement
from family_shortcut_runtime import prompt_for_assignment


TOOL_TITLE = "FamilyShortcut"


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def run_runtime_mode():
    assignment = prompt_for_assignment()
    if assignment is None:
        return

    symbol, error_message = resolve_symbol(revit.doc, assignment)
    if error_message:
        show_revit_warning(error_message)
        return

    start_native_placement(symbol)


def main():
    try:
        if get_shiftclick_state():
            show_manager_window()
        else:
            run_runtime_mode()
    except Exception as ex:
        forms.alert(
            "Unexpected error in {}:\n\n{}".format(TOOL_TITLE, ex),
            title=TOOL_TITLE,
            warn_icon=True,
            exitscript=False,
        )


if __name__ == "__main__":
    main()
