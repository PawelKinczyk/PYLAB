import clr
# Import DocumentManager and TransactionManager
clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager

# Import RevitAPI
clr.AddReference("RevitAPI")
import Autodesk
from Autodesk.Revit.DB import *

import sys
pyt_path = r'C:\Program Files (x86)\IronPython 2.7\Lib'
sys.path.append(pyt_path)

def ProcessList(_func, _list):
    return map( lambda x: ProcessList(_func, x) if type(x)==list else _func(x), _list )

def ProcessParallelLists(_func, *lists):
	return map( lambda *xs: ProcessParallelLists(_func, *xs) if all(type(x) is list for x in xs) else _func(*xs), *lists )

def Unwrap(item):
	return UnwrapElement(item)

if isinstance(IN[0], list) : inputdoc = ProcessList(Unwrap, IN[0])
else : inputdoc = [Unwrap(IN[0])]
#Inputdoc : Part of script by Andreas Dieckmann
if inputdoc[0] == None:
	doc = DocumentManager.Instance.CurrentDBDocument
elif inputdoc[0].GetType().ToString() == "Autodesk.Revit.DB.Document":
	doc = inputdoc[0]
else: doc = DocumentManager.Instance.CurrentDBDocument

folderpath = IN[1]

if isinstance(IN[2], list) : views = ProcessList(Unwrap, IN[2])
else : views = [Unwrap(IN[2])]

if isinstance(IN[3], list) : names = IN[3]
else : names = [IN[3]]

NWCExportScope = IN[4]
ChooseCoordinates = IN[5]
Linksbool = IN[6]
RunIt = IN[7]

def ExportNWC(name, view, folder = folderpath):
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

if RunIt:
	try:
		errorReport = None
		# run export
		ProcessParallelLists(ExportNWC, names, views)
		
	except:
		# if error accurs anywhere in the process catch it
		import traceback
		errorReport = traceback.format_exc()
else:
	errorReport = "Please set the RunIt to True!"

#Assign your output to the OUT variable
if errorReport == None:
	OUT = "Success",doc
else:
	OUT = errorReport