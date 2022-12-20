import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from pyrevit import forms
from pyrevit import output

doc = revit.doc
uidoc = revit.uidoc

## Pick folder with models (input)
models_folder = forms.pick_folder()
print(target_folder)

## Ask for 3D view name to export

view_name_3D = forms.ask_for_string(
    default='write 3D view name',
    prompt='Enter 3D view name to generate NWC:',
    title='Batch NWC Export'
)
print(view_name_3D)
## Set export options

## Ploting

## Results