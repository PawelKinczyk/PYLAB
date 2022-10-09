from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import *
from Autodesk.Revit.DB.Analysis import *

import clr
import System.Windows
import rpw
from rpw import revit, DB
from rpw.db.element import Element

uidoc =rpw.uidoc
doc = rpw.doc

from Autodesk.Revit.UI import *


def alert(msg):
    TaskDialog.Show('xxx', msg)

def quit():
    __widow__.Close

el = [rpw.uidoc.Selection.pick_element(multiple=True)]
ellink =[rpw.uidoc.Selection.pick_linked_element(multiple=True)]

for x in el:
    print("Elements in model"+x._revit_object.ElementId)

for x in ellink:
    print("Elements in linked model"+x._revit_object.LinkedElementId)
