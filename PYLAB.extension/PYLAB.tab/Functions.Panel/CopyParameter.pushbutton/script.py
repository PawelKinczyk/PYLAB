## Imports
import Autodesk
import clr
import pyrevit
import rpw

from rpw import revit
from pyrevit import forms
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *

## Revit doc
doc = revit.doc
uidoc = revit.uidoc

## Class and def
def Pargetstr(element, name):
    return (element.GetParameters(name))[0].AsValueString()

## Pick family of choosen element
try:
    with forms.WarningBar(title="Pick elements in model"):
        collector = uidoc.Selection.PickObject(ObjectType.Element)

except Exception as e:
    print("Nothing was picked")
collector=collector.ElementId
collector=doc.GetElement(collector)
collector_cat_id=collector.Category.Id
print(collector)
print(collector_cat_id)
type=collector.GetType()
print(type)
print("===")
# filter=
Shoes = [x for x in FilteredElementCollector(doc).OfClass(type).ToElements() if "Standard" in x.LookupParameter(Type).AsValueString]
# collector=FilteredElementCollector(doc).OfClass(type).WherePasses(filter).ToElements()
print(Shoes)
for i in collector:
    print(i.Name)
# collector_cat=collector.Category.GetType()
# print(collector_cat)

# all_elem=GetValidTypes(doc,collector.ElementId)
# all_elements_collector = FilteredElementCollector(doc).OfCategory(collector_cat).OfClass(FamilySymbol).WhereElementIsElementType().ToElements()

## Choose parameter to get value


## Choose parameter to overwrite value