## Imports
import os
import sys

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
    # if  i.IsReadOnly == False and i.StorageType == StorageType.String:
    #     parameters_editable.update({i.Definition.Name:i})
print(parameters)

## Take parameter to be copied

print("=============")
print(parameters.keys())
parameters_list=parameters.keys()

selected_option_a = forms.CommandSwitchWindow.show(
    parameters_list,
     message='Take parameter to be copied:',recognize_access_key=False
)
print(selected_option_a)

## 
for i in elements[0].Parameters:
    if  i.IsReadOnly == False and i.StorageType == StorageType.String and i.Definition.Name != selected_option_a:
        parameters_editable.update({i.Definition.Name:i})
    elif i.IsReadOnly == False and parameters[selected_option_a].StorageType == i.StorageType and i.Definition.Name != selected_option_a and i.CanBeAssociatedWithGlobalParameters() ==True:
        parameters_editable.update({i.Definition.Name:i})
    else:
        pass

## Choose parameter to overwrite value

print("=============")
print(parameters_editable.keys())
parameters_list_editable=parameters_editable.keys()

selected_option_b = forms.CommandSwitchWindow.show(
    parameters_list_editable,
     message='Take parameter to set:',recognize_access_key=False
)
print(selected_option_b)

## Choose parameter to overwrite value
# try:
t = Transaction(doc, "Override parameter - PYLAB")
t.Start()
try:
    for i in elements:
        
        parameter_a = i.LookupParameter(selected_option_a)
        parameter_b = i.LookupParameter(selected_option_b)
        if parameter_a.StorageType == StorageType.String:
            parameter_b_overr=parameter_a.AsString
            print(parameter_b_overr)
            parameter_b.Set(str(parameter_b_overr))
        else:
            parameter_b_overr=parameter_a.AsValueString
            print(parameter_b_overr)
            parameter_b.Set(str(parameter_b_overr))
except Exception as e:
    print(e)
t.Commit()
# except Exception as e:
#     print(e)