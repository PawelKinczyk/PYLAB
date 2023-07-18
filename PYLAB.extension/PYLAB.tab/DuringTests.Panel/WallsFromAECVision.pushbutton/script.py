import System
import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output
import csv

doc = __revit__.ActiveUIDocument.Document

## def / class

## Pick file with csv
csv_file_path = forms.pick_file(title="Pick file with exported csv")


## Ask for 3D view name to export

lenght_pixels = forms.ask_for_string(
    default='Write what is the lenght of measure object in pixels',
    prompt='Set value',
    title='Pixels lenght'
)

lenght_real_centimeters = forms.ask_for_string(
    default='Write what is the real lenght of measure object in centimeters',
    prompt='Set value',
    title='Real lenght'
)

## Calculate scale

scale = float(lenght_real_centimeters) / float(lenght_pixels)

## Create walls

### Import csv
data_file = []
with open(csv_file_path) as csvfile:
    data = csv.DictReader(csvfile, delimiter=',', quotechar='|')
    for row in data:
        data_file.append(row)

print(data_file)

## Create walls

### Collect levels and walls types
levels = FilteredElementCollector(doc).OfCategory(BuildInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()
walls = FilteredElementCollector(doc).OfCategory(BuildInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()

### Collect walls curves
curves_list = []
for dict in data_file:
    a = dict["xmax"] - dict["xmin"]
    b = dict["ymax"] - dict["ymin"]
    if a>b:
        x1 = dict["xmax"]

# open_options = OpenOptions()
# open_options.DetachFromCentralOption = DetachFromCentralOption.DetachAndPreserveWorksets

# name=0

# for revit_model in models_paths:
# 	revit_model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(revit_model)
# 	doc_nwc = __revit__.Application.OpenDocumentFile(revit_model_path, open_options)	
# 	# NWCExportScope = System.Enum.GetValues(NavisworksExportScope)[1]
# 	# ChooseCoordinates = System.Enum.GetValues(NavisworksCoordinates)[0]
# 	Linksbool = False
# 	views = FilteredElementCollector(doc_nwc).OfCategory(BuiltInCategory.OST_Views).WhereElementIsNotElementType().ToElements()
# 	name=revit_model
# 	for view in views:
# 		if view.IsTemplate != True and str(view.Name)==view_name_3D:
# 			view_export = view
			
# 			ExportNWC(str(name), view_export, models_folder, doc_nwc)
# 			print(view_export)
# 	print(name)
# 	doc_nwc.Close(False)

# print(view_name_3D)

