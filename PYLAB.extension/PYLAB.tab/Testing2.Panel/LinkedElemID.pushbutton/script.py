import clr
import sys
import os

from rpw import revit
from Autodesk.Revit.UI.Selection import *
from pyrevit import forms


doc = revit.doc
uidoc = revit.uidoc


###Thanks to Cyril Waechter https://pythoncvc.net/?p=116 custom ISelectionFilter
class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, nom_categorie):
        self.nom_categorie = nom_categorie
    def AllowElement(self, e):
        if e.Category.Name == self.nom_categorie:
            return True
        else:
            return False
    def AllowReference(self, ref, point):
        return true
###




# Pick model elements
try:
    with forms.WarningBar(title="Pick elements in model"):
        wall_collector = uidoc.Selection.PickObjects(ObjectType.Element, CustomISelectionFilter("Walls"))

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