from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from rpw import revit


# Get revit model
doc = revit.doc
uidoc = revit.uidoc


# Class and def
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


def get_dict_of_elements(build_in_category):
    elements = FilteredElementCollector(doc).OfCategory(
        build_in_category).WhereElementIsElementType().ToElements()
    return {Element.Name.GetValue(e): e for e in elements}


# Picking elements
with forms.WarningBar(title="Pick elements in model[pipes/pipe fittings]"):
    collector = uidoc.Selection.PickObjects(
        ObjectType.Element, CustomISelectionFilter("Pipes Pipe Fittings"))

# Get pipe types
pipe_types_dict = get_dict_of_elements(BuiltInCategory.OST_PipeCurves)

# Chose pipe type you want to change
pipe_type_name = forms.CommandSwitchWindow.show(pipe_types_dict.keys(), message='Select pipe type',
                                                recognize_access_key=False)

# Get routing preference
if pipe_type_name == None:
    forms.alert("You didn't pick any pipe type", exitscript=True)
    raise Exception("You didn't pick any pipe type")

pipe_type = pipe_types_dict[pipe_type_name]
rpm = pipe_type.RoutingPreferenceManager
rc = RoutingConditions(RoutingPreferenceErrorLevel.None)

# Clear unuse elements
del pipe_types_dict

# Sort elements pipe fittings/pipes
collector_fittings = []
collector_pipes = []
for element in collector:
    element_category = doc.GetElement(
        element).LookupParameter("Category").AsValueString()
    if element_category == "Pipes":
        collector_pipes.append(element)
    else:
        collector_fittings.append(element)


# Clear unuse elements
del collector

transaction = Transaction(doc, 'Batch change pipe - PYLAB')
transaction.Start()

# for loop through picked elements
for element in collector_pipes:

    try:
        print('it is a Pipe')
        element = doc.GetElement(element)
        element.ChangeTypeId(pipe_type.Id)
    except Exception as e:
        print("Pipe error")
        print(e)


for element in collector_fittings:
    refs = []
    try:
        element = doc.GetElement(element)
        fitting = element
        element = element.MEPModel

        # Get info about connected elements
        connectors = element.ConnectorManager.Connectors

        size_fit = float(0)
        for c in connectors:
            for r in c.AllRefs:
                c_size = float(r.Owner.LookupParameter("Size").AsString()[0:3])
                print(c_size)
                if size_fit <= c_size:
                    size_fit = c_size

        rc.AppendCondition(RoutingCondition(size_fit))

        pipe_fitting = element.PartType

        # Get routing preference MEPPartId
        if pipe_fitting == PartType.Elbow:
            print('it is an Elbow')
            new_fitting_id = rpm.GetMEPPartId(
                RoutingPreferenceRuleGroupType.Elbows,
                rc)
            part_fitting_id = rpm.GetRule(
                RoutingPreferenceRuleGroupType.Elbows,
                0)
            part_fitting_id = part_fitting_id.MEPPartId

        elif pipe_fitting == PartType.Tee:
            print('it is a Tee')
            new_fitting_id = rpm.GetMEPPartId(
                RoutingPreferenceRuleGroupType.Junctions, rc)
        elif pipe_fitting == PartType.Cross:
            print('it is a Cross')
            new_fitting_id = rpm.GetMEPPartId(
                RoutingPreferenceRuleGroupType.Crosses, rc)
        elif pipe_fitting == PartType.Transition:
            print('it is a Transition')
            new_fitting_id = rpm.GetMEPPartId(
                RoutingPreferenceRuleGroupType.Transitions, rc)
        else:
            new_fitting_id = None
            print('current fitting id: {}'.format(fitting.GetTypeId()))

        if (new_fitting_id
                and fitting.Id != new_fitting_id
                and new_fitting_id.IntegerValue != -1):
            fitting.ChangeTypeId(new_fitting_id)
    except Exception as e:
        print("Fitting error")
        print(e)

transaction.Commit()
