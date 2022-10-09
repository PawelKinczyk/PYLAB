import clr
import sys
import os

from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import DB, forms

doc = revit.doc
uidoc = revit.uidoc

# Pick model elements and add insulation
try:
    with forms.WarningBar(title="Pick elements in model"):
        collector = uidoc.Selection.PickObjects(ObjectType.Element)
        
    for i in collector:
        try:
            
            Plumbing.PipeInsulation.Create(doc,i.ElementId,599323,10)
        except Exception as e: 
            print(e)
except Exception as e: 
    print(e)

# Add insulation
# print("##########Cat##########")
# for i in doc.Settings.Categories:
#     print(i.Name)

# print("#########Cat fam id##########")
# for i in FilteredElementCollector(doc).OfClass(ElementType).ToElements():
#     print(i)
#     print(i.Id)

# print("#########Cat insul##########")
# filter=ElementCategoryFilter(BuiltInCategory.OST_PipeInsulations)
# for i in FilteredElementCollector(doc).OfClass(ElementType).WherePasses(filter):
#     print(i)
#     print(i.Id)
#     print(i.FamilyName)
#     print(Element.Name.GetValue(i))

# a = InsulationLiningBase.GetInsulationIds(uidoc)
# print(a)
# try:
#     Plumbing.PipeInsulation.Create(doc, collector.Id, )

        