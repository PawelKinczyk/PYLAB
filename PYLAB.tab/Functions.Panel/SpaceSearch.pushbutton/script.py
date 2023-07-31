## Imports

import sys
from rpw import revit as rv
from pyrevit import forms
from pyrevit import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *

## Revit doc

doc = rv.doc
uidoc = rv.uidoc

## Get name of room/space

room_name=forms.ask_for_string(prompt="Type room name which you search", title="Room number")

## Get spaces in model

collector=FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_MEPSpaces)

## Pick room
selection = revit.get_selection()

for i in collector:
    try:
        if i.Number == room_name:
            selection.set_to(i.Id)
            break
        else:
            pass
    except Exception as e:
        print("Error:")
        print(e)  
