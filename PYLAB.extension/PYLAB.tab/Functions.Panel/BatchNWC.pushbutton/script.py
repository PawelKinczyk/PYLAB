import System
import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output


## def / class
# from geniusloci

def ExportNWC(name, view, folder, doc_n):
	options = NavisworksExportOptions()
	options.ViewId=view.Id
	#All,Elements, or None
	#options.NavisworksParameters = Enumeration
	options.ExportScope = NavisworksExportScope.View #NWCExportScope
	options.ExportLinks=Linksbool
	options.Coordinates=NavisworksCoordinates.Shared #ChooseCoordinates
	options.ExportParts = False
	options.ExportElementIds = True
	options.ConvertElementProperties = True
	options.ExportRoomAsAttribute = True
	options.ExportRoomGeometry = False
	options.ExportUrls  = True
	options.DivideFileIntoLevels = False
	options.FindMissingMaterials = True
	result = doc_n.Export(folder, name, options)
	return result

# ## Navis coordinates

# NWCExportScope = System.Enum.GetValues(NavisworksExportScope)[1]
# ChooseCoordinates = System.Enum.GetValues(NavisworksCoordinates)[0]
# Linksbool = False

## Pick folder with models (input)

models_folder = forms.pick_folder(title="Pick folder where the models, to export nwc, are")
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

open_options = OpenOptions()
open_options.DetachFromCentralOption = DetachFromCentralOption.DetachAndPreserveWorksets

name=0

for revit_model in models_paths:
	revit_model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(revit_model)
	doc_nwc = __revit__.Application.OpenDocumentFile(revit_model_path, open_options)	
	# NWCExportScope = System.Enum.GetValues(NavisworksExportScope)[1]
	# ChooseCoordinates = System.Enum.GetValues(NavisworksCoordinates)[0]
	Linksbool = False
	views = FilteredElementCollector(doc_nwc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()
	name=revit_model
	for view in views:
		if view.IsTemplate != True and str(view.Name)==view_name_3D:
			view_export = view
			
			ExportNWC(str(name), view_export, models_folder, doc_nwc)
			print(view_export)
	print(name)
	doc_nwc.Close(False)

print(view_name_3D)

