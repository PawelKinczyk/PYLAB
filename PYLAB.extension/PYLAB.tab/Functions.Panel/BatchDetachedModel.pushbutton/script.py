import os

from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output

## def / class


## Pick folder with models (input)

models_folder = forms.pick_folder(title="Pick folder where the models, to be detached, are")
print(models_folder)
models_folder_detached = forms.pick_folder(title="Pick folder where you want to save detached models")
models_paths =[]
for root, dirs, files in os.walk(models_folder):
	for revit_file in files:
		if ".rvt" in revit_file:
			models_paths.append(os.path.join(root, revit_file))
print(models_paths)

## Open doc options
open_options = OpenOptions()
open_options.DetachFromCentralOption = DetachFromCentralOption.DetachAndPreserveWorksets
open_options.AllowOpeningLocalByWrongUser = True

## Save as doc options
worksharing_options = WorksharingSaveAsOptions()
worksharing_options.SaveAsCentral = True

save_as_options = SaveAsOptions()
save_as_options.SetWorksharingOptions(worksharing_options)
save_as_options.MaximumBackups = 1
save_as_options.OverwriteExistingFile = True




try:
	for revit_model in models_paths:
		try:
			print(revit_model)
			revit_model_path = ModelPathUtils.ConvertUserVisiblePathToModelPath(revit_model)
			
			doc_det = __revit__.Application.OpenDocumentFile(revit_model_path, open_options)	
			
			doc_det.SaveAs(models_folder_detached, save_as_options)
			doc_det.Close(False)
		except Exception as e:
			print(e)
except Exception as e:
	print(e)


