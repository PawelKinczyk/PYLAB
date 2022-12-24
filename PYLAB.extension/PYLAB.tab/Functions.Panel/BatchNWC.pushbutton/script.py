import System
import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output

doc = revit.doc
uidoc = revit.uidoc

## def / class
# from geniusloci

def ExportNWC(name, view, folder):
	options = NavisworksExportOptions()
	options.ViewId=view.Id
	#All,Elements, or None
	#options.NavisworksParameters = Enumeration
	options.ExportScope = NWCExportScope
	options.ExportLinks=Linksbool
	options.Coordinates=ChooseCoordinates
	options.ExportParts = False
	options.ExportElementIds = True
	options.ConvertElementProperties = True
	options.ExportRoomAsAttribute = True
	options.ExportRoomGeometry = False
	options.ExportUrls  = True
	options.DivideFileIntoLevels = False
	options.FindMissingMaterials = True
	result = doc.Export(folder, name, options)
	return result

## Navis coordinates

NWCExportScope = System.Enum.GetValues(NavisworksExportScope)[1]
ChooseCoordinates = System.Enum.GetValues(NavisworksCoordinates)[0]
Linksbool = False

## Pick folder with models (input)

models_folder = forms.pick_folder()
print(models_folder)
models_paths =[]
for root, dirs, files in os.walk(models_folder):
	for revit_file in files:
		if ".rvt" in revit_file:
			models_paths.append(os.path.join(root, revit_file))
print(models_paths)

## Ask for 3D view name to export

view_name_3D = forms.ask_for_string(
    default='write 3D view name',
    prompt='Enter 3D view name to generate NWC:',
    title='Batch NWC Export'
)
name=0
for revit_model in models_paths:
	doc_nwc = __revit__.Application.OpenDocumentFile(revit_model)	
	NWCExportScope = System.Enum.GetValues(NavisworksExportScope)[1]
	ChooseCoordinates = System.Enum.GetValues(NavisworksCoordinates)[0]
	Linksbool = False
	views = FilteredElementCollector(doc_nwc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()
	for view in views:
		if view.IsTemplate != True and str(view.Name)==view_name_3D:
			name+=1
			view_export = view
			ExportNWC(name, view_export, models_folder)
			print(view_export)
	print(name)
	doc_nwc.Close()

print(view_name_3D)
views = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()
for view in views:
            if view.IsTemplate != True and str(view.Name)==view_name_3D:
                view_export = view
                print(view_export)

## Set export options
# name="IFC"
# ExportNWC(name, view_export, models_folder)

## Ploting



## Results