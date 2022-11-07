import clr
import sys
import os

from rpw import revit
from rpw.ui.forms import TextInput
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import DB, forms

doc = revit.doc
uidoc = revit.uidoc

# pipes_insulation_type = revit.query.get_types_by_class(DB.Plumbing.PipeInsulationType)
# print(pipes_insulation_type)
class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, nom_categorie):
        self.nom_categorie = nom_categorie
    def AllowElement(self, e):
        if e.Category.Name == self.i:
            return True
        else:
            return False
    def AllowReference(self, ref, point):
        return true



with forms.WarningBar(title="Pick elements in model"):
    collector = uidoc.Selection.PickObjects(ObjectType.Element,CustomISelectionFilter(typeof("Pipe"),typeof("PipeFitting")))

filter1=ElementCategoryFilter(BuiltInCategory.OST_PipeInsulations)
ins_list=FilteredElementCollector(doc).OfClass(ElementType).WherePasses(filter1).ToElements()
ins_list_pins=[Element.Name.GetValue(i) for i in ins_list]

rops = forms.CommandSwitchWindow.show(ins_list_pins, message='Select Option',
recognize_access_key=False)
print(rops)
choosen_ins=ins_list[ins_list_pins.index(rops)]
print(choosen_ins)
# filter2=ElementCategoryFilter(BuiltInCategory.OST_Pipe)
# ins_list=FilteredElementCollector(doc).OfClass(ElementType).WherePasses(filter2).ToElements()
elements=[]
elements_type=[]
dict={}
for i in collector:
    el=doc.GetElement(i.ElementId)
    elements.append(el)
    elements_type.append(el.Name)
    print(el.Diameter*304.8)
    dict.update({el.Name + str(el.Diameter*304.8):0})
print(elements)
print(elements_type)
print(dict)

for key in dict:
    t=forms.ask_for_string(prompt='Select Pipe Insulation Thickness for {}'.format(key), title="Insulation")
    dict.update({key:t})

transaction = Transaction(doc, 'Transaction')
transaction.Start()

for i in elements:
    try:
        t=float(dict[i.Name + str(i.Diameter*304.8)])/304.8
        print(t)
        Plumbing.PipeInsulation.Create(doc,i.Id,choosen_ins.Id,t)
        
    except Exception as e: 
        print(e)
transaction.Commit()
# ins_list_p=[Element.Name.GetValue(i) for i in ins_list]
# print(ins_list_p)

# with forms.WarningBar(title="Pick elements in model"):
#          collector = uidoc.Selection.PickObjects(ObjectType.Element)
# ops = a
# forms.CommandSwitchWindow.show(ops, message='Select Option')
# value = TextInput('Title', default="3")


# Pick model elements and add insulation
# try:
#     with forms.WarningBar(title="Pick elements in model"):
#         collector = uidoc.Selection.PickObjects(ObjectType.Element)
    
    
#     for i in collector:
#         try:
#             transaction = Transaction(doc, 'Transaction')
#             transaction.Start()
#             Plumbing.PipeInsulation.Create(doc,i.ElementId,ElementId(599323),1)
#             transaction.Commit()
#         except Exception as e: 
#             print(e)
# except Exception as e: 
##     print(e)