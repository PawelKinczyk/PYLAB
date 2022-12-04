from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output

doc = revit.doc
uidoc = revit.uidoc


## Pick model element
try:
    with forms.WarningBar(title="Pick elements in model"):
        collector = uidoc.Selection.PickObject(ObjectType.Element)

except Exception as e:
    pass

## Get element's workset
el=doc.GetElement(collector.ElementId)
workset_id = el.WorksetId
transaction = Transaction(doc, 'Changed workset - PYLAB')

## Change active workset
transaction.Start()
doc.GetWorksetTable().SetActiveWorksetId(workset_id)
transaction.Commit()

output = output.get_output()
output.close()