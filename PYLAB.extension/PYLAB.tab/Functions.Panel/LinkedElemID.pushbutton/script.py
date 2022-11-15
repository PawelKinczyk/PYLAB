import clr
import sys
import os

from rpw import revit
from Autodesk.Revit.UI.Selection import *
from pyrevit import forms

doc = revit.doc
uidoc = revit.uidoc

def Pargetstr(element, name):
    return (element.GetParameters(name))[0].AsValueString()

# Pick model elements
try:
    with forms.WarningBar(title="Pick elements in model"):
        collector = uidoc.Selection.PickObjects(ObjectType.Element)

except Exception as e:
    pass
    # print(e)
    
# Pick linked elements
try:
    with forms.WarningBar(title="Pick elements in linked model"):
        collector_link = uidoc.Selection.PickObjects(ObjectType.LinkedElement)

except Exception as e:
    pass
    # print(e)

# Print Ids
try:
    for i in collector:
            print("====")
            print("Model element "+str(i.ElementId))
            el=doc.GetElement(i.ElementId)
            print((Pargetstr(el, "Family and Type")))
except:     
    print("No picked elements")
try:
    for i in collector_link:
            print("====")
            el=doc.GetElement(i.ElementId)
            linkdoc=el.GetLinkDocument()
            el=linkdoc.GetElement(i.LinkedElementId)
            print("Linked element "+str(i.ElementId))
            print((Pargetstr(el, "Family and Type")))
except Exception as e:
    print(e)
    print("No picked linked elements")