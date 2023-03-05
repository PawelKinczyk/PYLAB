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


# dir = script.get_script_path()
# print(dir)
# Pick schacko element
air_terminal = pick_objects(title="Pick schacko DQJ", filter="Air Terminals")

# Write air flow
air_flow = forms.ask_for_string(prompt="Write air supply", title="Insulation")
air_flow = round(float(air_flow), -1)
air_flow = int(air_flow)
print(air_flow)

# Get DQJ sizes
# dir = os.path.dirname(os.path.realpath(__file__))
# dir = os.path.join(dir, "schacko_DQJ_sq_supply.json")
# dir = str(script.get_script_path() + "\schacko_DQJ_sq_supply.json")
# print(dir)
os.chdir(os.path.dirname(os.path.abspath(__file__)))
with open("schacko_DQJ_sq_supply.json", "r") as file:
    dqj_dict = json.load(file)
    # print(dqj_dict[str(air_flow)])


selected_dqj = forms.SelectFromList.show(dqj_dict[str(
    air_flow)], title="Select DQJ which you want to pick", multiselect=False, button_name='Select DQJ')
selected_dqj_size = selected_dqj[0][3::]
print(selected_dqj_size)

transaction = Transaction(doc, 'Schacko DQJ - PYLAB')
transaction.Start()

# Change type of picked dqj
for element in air_terminal:
    element = doc.GetElement(element)

    print(element.GetTypeId())
    if isinstance(element, FamilyInstance):
        family_instance = element
    else:
        family_instance = None
	
    print(family_instance.Symbol)
    print(Element.Name.GetValue(family_instance.Symbol))
    print(element.LookupParameter("Family").AsString())
    
    types = family_instance.Symbol.GetSimilarTypes()
    for i in types:
        print(i)
        if Element.Name.GetValue(doc.GetElement(i)) == "DQJ-Q-SQ-Z-400-PS-B-VM-SAK-Z-DK":
            element.ChangeTypeId(i)
    # element.ChangeType()

transaction.Commit()