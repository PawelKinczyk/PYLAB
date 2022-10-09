from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import *
from Autodesk.Revit.DB.Analysis import *

import clr
import System.Windows
import rpw

uidoc =rpw.uidoc #__revit__.ActiveUIDocument
doc = rpw.doc#__revit__.ActiveUIDocument.Document

from Autodesk.Revit.UI import *


def alert(msg):
    TaskDialog.Show('Pawel Kinczyk', msg)

def quit():
    __widow__.Close

def get_selected_elements(doc):
    """API change in Revit 2016 makes old method throw an error"""
    try:
        # Revit 2016
        return [doc.GetElement(id)
                for id in __revit__.ActiveUIDocument.Selection.GetElementIds()]
    except:
        # old method
        return list(__revit__.ActiveUIDocument.Selection.Elements)

el=get_selected_elements(doc)

for x in el:
    print(x.Id)