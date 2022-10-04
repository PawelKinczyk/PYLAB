"""Get linked element id"""

from pyrevit.framework import List
from pyrevit import revit, DB, UI


selection = revit.get_selection()

try:
    selection_list = revit.PickObjects()