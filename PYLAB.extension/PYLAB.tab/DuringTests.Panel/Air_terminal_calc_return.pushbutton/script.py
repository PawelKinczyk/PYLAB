from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms, script
from rpw import revit
import json
import os


doc = revit.doc
uidoc = revit.uidoc


class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, nom_categorie):
        self.nom_categorie = nom_categorie

    def AllowElement(self, e):
        if e.Category.Name in self.nom_categorie:
            # if self.nom_categorie.Contains(e.Category.Name):
            # if e.Category.Name == self.nom_categorie:
            return True
        else:
            return False

    def AllowReference(self, ref, point):
        return True


def pick_objects(title="Pick", filter=""):
    with forms.WarningBar(title=title):
        return uidoc.Selection.PickObjects(ObjectType.Element, CustomISelectionFilter(filter))


def open_json(name_of_file="", open_method="r"):
    with open(name_of_file, open_method) as file:
        data = json.load(file)
        return data


# Pick air terminal
try:
    air_terminal = pick_objects(
        title="Pick return air terminal", filter="Air Terminals")
except:
    forms.alert(title="Program Error",
                msg="You didn't pick any air terminal", exitscript=True)

# Write air flow
try:
    air_flow = forms.ask_for_string(
        prompt="Write air return", title="Air terminal air flow")
    air_flow = int(air_flow)
except:
    forms.alert(title="Program Error",
                msg="You didn't write anything", exitscript=True)

# Get air terminal sizes
os.chdir(os.path.dirname(os.path.abspath(__file__)))
try:
    dqj_list = open_json("air_terminals_return_settings.json", "r")
except:
    forms.alert(title="Program Error",
                msg="Didn't find settings", exitscript=True)

# Search for prefer family
correct_dqj = []
for dqj in dqj_list:
    dqj_min = int(dqj[0][0:4:])
    dqj_max = int(dqj[0][5:9:])
    if air_flow > dqj_min and air_flow < dqj_max:
        air_flow_avaible = ("{}-{}".format(dqj_min, dqj_max))
        new_dqj = tuple([air_flow_avaible])+tuple(dqj[1])
        correct_dqj.append(new_dqj)

# Select ait terminal type
try:
    selected_dqj = forms.SelectFromList.show(
        correct_dqj, title="Select air terminal which you want to pick", multiselect=False, button_name='Select DQJ', width=800)
    selected_dqj_size = selected_dqj[1]
except:
    forms.alert(title="Program Error",
                msg="You didn't pick any type", exitscript=True)    

transaction = Transaction(doc, 'Air terminal calculator - PYLAB')
transaction.Start()

# Change to new type
try:
    for element in air_terminal:
        element = doc.GetElement(element)

        if isinstance(element, FamilyInstance):
            family_instance = element
        else:
            family_instance = None


        types = family_instance.Symbol.GetSimilarTypes()
        for i in types:
            if selected_dqj_size in Element.Name.GetValue(doc.GetElement(i)):
                element.ChangeTypeId(i)
except Exception as e:
    forms.alert(title="Program Error", msg=e, exitscript=True)

transaction.Commit()
