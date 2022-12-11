import clr
from Autodesk.Revit.UI.Selection import *
from pyrevit import revit, forms

doc = revit.doc
uidoc = revit.uidoc


class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, category_name, document):
        self.category_name = category_name
        self.document = document

    def AllowElement(self, element):
        some_type = self.document.GetElement(element.GetTypeId())
        type_name = some_type.FamilyName

        if type_name == "Linked Revit Model":
            return True
        else:
            if element.Category.Name == self.category_name:
                return True
            else:
                return False

    def AllowReference(self, ref, point):
        element = self.document.GetElement(ref)
        some_type = revit.doc.GetElement(element.GetTypeId())
        type_name = some_type.FamilyName

        if type_name == "Linked Revit Model":
            li = clr.Convert(element, type(element))
            linked_document = li.GetLinkDocument()
            element = linked_document.GetElement(ref.LinkedElementId)

        if element.Category.Name == self.category_name:
            return True
        else:
            return False



# # Pick model elements
# try:
#     with forms.WarningBar(title="Pick elements in model"):
#         wall_collector = uidoc.Selection.PickObjects(ObjectType.Element, CustomISelectionFilter("Walls", doc))

# except:
#     print("No elements")

# Pick linked elements
try:
    with forms.WarningBar(title="Pick elements in linked model"):
        wall_collector_link = uidoc.Selection.PickObjects(ObjectType.LinkedElement, CustomISelectionFilter("Walls", doc))

except Exception as e:
    print(e)