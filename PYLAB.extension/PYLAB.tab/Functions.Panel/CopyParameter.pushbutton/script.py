## Imports
from rpw import revit as rv
from rpw import db
from pyrevit import forms
from pyrevit import output
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *

## Revit doc
doc = rv.doc
uidoc = rv.uidoc

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
# type=collector.Category.Id
print(type)
print("===")
collector=FilteredElementCollector(doc).OfClass(type).WhereElementIsNotElementType().ToElements()
# collector=FilteredElementCollector(doc).OfCategoryId(type).WhereElementIsNotElementType().ToElements()
print(collector)
for i in collector:
    print(">>>" + i.Name)
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
print(parameters)

## Take parameter to be copied

print("=============")
print(parameters.keys())
parameters_list=sorted(parameters.keys())

selected_option_a = forms.CommandSwitchWindow.show(
    parameters_list,
     message='Take parameter to be copied:',recognize_access_key=False
)
print(selected_option_a)

## Collecting parameters by storage type
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
parameters_list_editable=sorted(parameters_editable.keys())

selected_option_b = forms.CommandSwitchWindow.show(
    parameters_list_editable,
     message='Take parameter to set:',recognize_access_key=False
)
print(selected_option_b)

## Choose parameter to overwrite value
output = output.get_output()
output.print_html('<font size="6"><strong>Results:</strong></font>')
t = Transaction(doc, "Override parameter - PYLAB")
t.Start()
try:
    
    for i in elements:
        
        parameter_a = i.LookupParameter(selected_option_a)
        parameter_b = i.LookupParameter(selected_option_b)
        
        if parameter_a.StorageType == StorageType.String and parameter_b.StorageType == StorageType.String:
            parameter_b_overr=parameter_a.AsString()
            print("Element Id: " + str(i.Id))            
            print("Overritten value " + str(parameter_b_overr))
            parameter_b.Set(parameter_b_overr)
        
        elif parameter_a.StorageType == StorageType.Double and parameter_b.StorageType == StorageType.Double:
            parameter_b_overr=parameter_a.AsDouble()
            print("Element Id: " + str(i.Id))
            print("Overritten value " + str(parameter_b_overr))
            parameter_b.Set(parameter_b_overr)
        elif parameter_a.StorageType == StorageType.Integer and parameter_b.StorageType == StorageType.Integer:
            parameter_b_overr=parameter_a.AsInteger()
            print("Element Id: " + str(i.Id))
            print("Overritten value " + str(parameter_b_overr))
            parameter_b.Set(parameter_b_overr)
        else:
            parameter_b_overr=parameter_a.AsValueString()
            print("Element Id: " + str(i.Id))
            print("Overritten value " + str(parameter_b_overr))
            parameter_b.Set(parameter_b_overr)
except Exception as e:
    print(e)
t.Commit()
