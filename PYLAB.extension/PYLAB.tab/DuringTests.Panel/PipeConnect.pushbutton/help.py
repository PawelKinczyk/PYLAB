# From dynamo MEPover
import clr

clr.AddReference("RevitServices")
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager
doc = DocumentManager.Instance.CurrentDBDocument

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import *

clr.AddReference("RevitNodes")
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)


pipes = UnwrapElement(IN[0])
margin = IN[1]

fittings = []
connectors = {}
connlist = []

for pipe in pipes:
	conns = pipe.ConnectorManager.Connectors
	for conn in conns:
		if conn.IsConnected:
			continue
		connectors[conn] = None
		connlist.append(conn)

for k in connectors.keys():
	mindist = 1000000
	closest = None
	for conn in connlist:
		if conn.Owner.Id.Equals(k.Owner.Id):
			continue
		dist = k.Origin.DistanceTo(conn.Origin)
		if dist < mindist:
			mindist = dist
			closest = conn
	if mindist > margin:
		continue
	connectors[k] = closest
	connlist.remove(closest)
	try:
		del connectors[closest]
	except:
		pass


for k,v in connectors.items():
	TransactionManager.Instance.EnsureInTransaction(doc)		
	try:
		fitting = doc.Create.NewElbowFitting(k,v)
		fittings.append(fitting.ToDSType(False))
	except:
		pass
	TransactionManager.Instance.TransactionTaskDone()

OUT = fittings