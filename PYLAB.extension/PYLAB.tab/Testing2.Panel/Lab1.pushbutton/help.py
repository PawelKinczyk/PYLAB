###Code from mepover
import clr

clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager
doc = DocumentManager.Instance.CurrentDBDocument

clr.AddReference("RevitAPI")
import Autodesk
from Autodesk.Revit.DB import *

clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)

dut = doc.GetUnits().GetFormatOptions(UnitType.UT_Length).DisplayUnits
bool = dut == DisplayUnitType.DUT_MILLIMETERS

if isinstance(IN[0], list):
	pipes = UnwrapElement(IN[0])
else:
	pipes = [UnwrapElement(IN[0])]
if isinstance(IN[1], list):
	insultype = UnwrapElement(IN[1])
else:
	insultype = [UnwrapElement(IN[1])]
li = len(insultype)
if isinstance(IN[2], list):
	size = IN[2]
else:
	size = [IN[2]]
ls = len(size)

size = map(lambda x:UnitUtils.Convert(x,DisplayUnitType.DUT_MILLIMETERS,DisplayUnitType.DUT_DECIMAL_FEET) if bool else x, size)

failed = []
succes = []

TransactionManager.Instance.EnsureInTransaction(doc)
for i,pipe in enumerate(pipes):
	s = i%ls
	l = i%li
	try:
		Plumbing.PipeInsulation.Create(doc,pipe.Id,insultype[l].Id,size[s])
		succes.append(pipe)
	except:
		try:
			Mechanical.DuctInsulation.Create(doc,pipe.Id,insultype[l].Id,size[s])
			succes.append(pipe)
		except:
			failed.append(pipe)

TransactionManager.Instance.TransactionTaskDone()


OUT = succes, failed