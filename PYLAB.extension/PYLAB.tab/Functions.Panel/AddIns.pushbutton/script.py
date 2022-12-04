from rpw import revit,db
from rpw.ui.forms import TextInput
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms

doc = revit.doc
uidoc = revit.uidoc

## Class and def
class CustomISelectionFilter(ISelectionFilter):
	def __init__(self, nom_categorie):
		self.nom_categorie = nom_categorie
	def AllowElement(self, e):
		if e.Category.Name in self.nom_categorie:
        # if self.nom_categorie.Contains(e.Category.Name):
		#if e.Category.Name == self.nom_categorie:
			return True
		else:
			return False
	def AllowReference(self, ref, point):
		return true

def Pargetstr(element, name):
    return (element.GetParameters(name))[0].AsValueString()

def Parget(element, name):
    return (element.GetParameters(name))[0].AsString()

## Picking elements
with forms.WarningBar(title="Pick elements in model[pipes/pipe fittings"):
    collector = uidoc.Selection.PickObjects(ObjectType.Element,CustomISelectionFilter("Pipes Pipe Fittings"))

filter1=ElementCategoryFilter(BuiltInCategory.OST_PipeInsulations)
ins_list=FilteredElementCollector(doc).OfClass(ElementType).WherePasses(filter1).ToElements()
ins_list_pins=[Element.Name.GetValue(i) for i in ins_list]

rops = forms.CommandSwitchWindow.show(ins_list_pins, message='Select Option',
recognize_access_key=False)
# print(rops)
choosen_ins=ins_list[ins_list_pins.index(rops)]
# print(choosen_ins)

## Get types of elements to ask for insulation thickness
elements=[]
elements_type=[]
dict={}
for i in collector:
    el=doc.GetElement(i.ElementId)
    elements.append(el)
    elements_type.append(el.Name)
    element_parameters=[]
    for p in el.Parameters:
        element_parameters.append(p.Definition.Name)

    # print("=======")
    # print(el.Category)
    # print(el.Category.Name)
    # print(el.Parameters)
    try:
        if el.Category.Name=="Pipes":
            
            dict.update({Pargetstr(el, "Family and Type") +" "
                        + str(el.Diameter*304.8):0})

        else:
            
            dict.update({Pargetstr(el, "Family and Type") +" "
                        + Parget(el, "Overall Size"):0})
    except Exception as e:    
        print(e)
    del element_parameters[:]
# print(element_parameters)
# print(elements)
# print(elements_type)
# print(dict)

## Ask for insulation thickness
for key in dict:
    t=forms.ask_for_string(prompt='Select Insulation Thickness for {}'.format(key), title="Insulation")
    dict.update({key:t})
# print(dict)
transaction = Transaction(doc, 'Add insulation - PYLAB')
transaction.Start()

## Set insulation to pipes
output = output.get_output()
output.print_html('<font size="6"><strong>Results:</strong></font>')
for el in elements:
    try:
        
        if el.Category.Name=="Pipes":
            t=float(dict[Pargetstr(el, "Family and Type") +" "
                    + str(el.Diameter*304.8)])/304.8
            Plumbing.PipeInsulation.Create(doc,el.Id,choosen_ins.Id,t)
            print("=====")
            print(Pargetstr(el, "Family and Type") +" "
                    + str(el.Diameter*304.8)+ " Id: " + str(el.Id))
            print("Insulation thicknes: {}").format(t*304.8)
        
        else:
            t=float(dict[Pargetstr(el, "Family and Type") +" "
                    + Parget(el, "Overall Size")])/304.8
            Plumbing.PipeInsulation.Create(doc,el.Id,choosen_ins.Id,t)
            print("=====")
            print(Pargetstr(el, "Family and Type") +" "
                + Parget(el, "Overall Size") + " Id: " + str(el.Id))
            print("Insulation thicknes: {}").format(t*304.8)
        
    except Exception as e: 
        print("=====")
        print(e)
        print("Error Element Id {}".format(el.Id))
transaction.Commit()
