###Custom filter
###Thanks to Cyril Waechter https://pythoncvc.net/?p=116 custom ISelectionFilter
class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, nom_categorie):
        self.nom_categorie = nom_categorie
    def AllowElement(self, e):
        if e.Category.Name == self.nom_categorie:
        if self.nom_categorie.Contains(e.Category.Name):    
            return True
        else:
            return False
    def AllowReference(self, ref, point):
        return true
###

###Elements collector
familyinstance_collector = DB.FilteredElementCollector(revit.doc)\
                             .OfClass(DB.FamilyInstance)\
                             .WhereElementIsNotElementType()\
                             .ToElements()    

for i in familyinstance_collector:
    print(i.GetType)
###

###Multifilter
cat_list = [BuiltInCategory.OST_Rooms, BuiltInCategory.OST_Walls, BuiltInCategory.OST_Windows, BuiltInCategory.OST_Doors]
    typed_list = List[BuiltInCategory](cat_list)
    filter = ElementMulticategoryFilter(typed_list)
    output = FilteredElementCollector(doc).WherePasses(filter).ToElements()

###FilteredElementCollector
filter=ElementCategoryFilter(BuiltInCategory.OST_PipeInsulations)
for i in FilteredElementCollector(doc).OfClass(ElementType).WherePasses(filter).ToElements():
    print(i)
    print(i.Id)
    print(i.FamilyName)
    print(Element.Name.GetValue(i))
###

###Inheritance Hierarchy
https://www.revitapidocs.com/2019/a1acaed0-6a62-4c1d-94f5-4e27ce0923d3.htm
System Object
Autodesk.Revit.DB Element
Autodesk.Revit.DB ElementType
Autodesk.Revit.DB InsertableObject
Autodesk.Revit.DB FamilySymbol
Autodesk.Revit.DB AnnotationSymbolType
Autodesk.Revit.DB.Architecture RoomTagType
Autodesk.Revit.DB AreaTagType
Autodesk.Revit.DB.Mechanical SpaceTagType
Autodesk.Revit.DB MullionType
Autodesk.Revit.DB PanelType
Autodesk.Revit.DB.Structure TrussType 
###


###Simple imput widow from documentation
from pyrevit import forms
ops = ['option1', 'option2', 'option3', 'option4']
switches = ['switch1', 'switch2']
cfgs = {'option1': { 'background': '0xFF55FF'}}
rops, rswitches = forms.CommandSwitchWindow.show(ops,switches=switches, message='Select Option',config=cfgs,
recognize_access_key=False)
###