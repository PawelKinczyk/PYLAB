import clr
import sys
import os

from rpw import revit
from Autodesk.Revit.UI.Selection import *
from pyrevit import forms

doc = revit.doc
uidoc = revit.uidoc

# Pick model elements
try:
    with forms.WarningBar(title="Pick elements in model"):
        wall_collector = uidoc.Selection.PickObjects(ObjectType.Element)

except:
    print("")
    
# Pick linked elements
try:
    with forms.WarningBar(title="Pick elements in linked model"):
        wall_collector_link = uidoc.Selection.PickObjects(ObjectType.LinkedElement)

except:
    print("")

# Print Ids
try:
    for i in wall_collector:
            print("Model element "+str(i.ElementId))
except:
    print("No linked elements")
try:
    for i in wall_collector_link:
            print("Linked element "+str(i.ElementId))
except:
    print("No linked elements")