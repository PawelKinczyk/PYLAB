from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import *
from Autodesk.Revit.DB.Analysis import *

import clr
import System.Windows
import rpw

def alert(msg):
    TaskDialog.Show('Pawel Kinczyk', msg)

def quit():
    __widow__.Close