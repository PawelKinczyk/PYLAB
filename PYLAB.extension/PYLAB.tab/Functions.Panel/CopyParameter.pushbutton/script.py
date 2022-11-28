## Imports
import Autodesk
import clr
import pyrevit
import rpw

from rpw import revit
from rpw import db
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
picked_el=collector
print(collector)
print(collector_cat_id)
type=collector.GetType()
print(type)
print("===")
collector=FilteredElementCollector(doc).OfClass(type).ToElements()
print(collector)
print("===")
## Get the elements of the same Family and Type
elements=[]
for i in collector:
    if Pargetstr(i, "Family and Type")==Pargetstr(picked_el, "Family and Type"):
        elements.append(i)
    else:
        pass
    
print(elements)
## Get parameters
parameters={}
parameters_editable={}
for i in elements[0].Parameters:
    parameters.update({i.Definition.Name:i})
    if  i.IsReadOnly == False and i.StorageType == StorageType.String:
        parameters_editable.update({i.Definition.Name:i})
print(parameters)


## Take parameter to be copied

print("=============")
print(parameters.keys())
parameters_list=parameters.keys()

selected_option = forms.CommandSwitchWindow.show(
    parameters_list,
     message='Take parameter to be copied:',recognize_access_key=False
)

## Take parameter to set

print("=============")
print(parameters.keys())
parameters_list_editable=parameters_editable.keys()

selected_option = forms.CommandSwitchWindow.show(
    parameters_list_editable,
     message='Take parameter to set:',recognize_access_key=False
)


## Choose parameter to overwrite value