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

def pick_objects(title="Pick", filter=""):
    with forms.WarningBar(title):
        collector = uidoc.Selection.PickObjects(
            ObjectType.Element, CustomISelectionFilter(filter))