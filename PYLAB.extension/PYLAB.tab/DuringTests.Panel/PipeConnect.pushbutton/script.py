import os

from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from Autodesk.Revit.Creation import *
from pyrevit import forms
from pyrevit import output
from pyrevit import revit

# def / class


class CustomISelectionFilter(ISelectionFilter):
    def __init__(self, nom_categorie):
        self.nom_categorie = nom_categorie

    def AllowElement(self, e):
        if e.Category.Name in self.nom_categorie:
            # if self.nom_categorie.Contains(e.Category.Name):
            # if e.Category.Name == self.nom_categorie:
            return True
        else:
            return False

    def AllowReference(self, ref, point):
        return True


def pick_objects(title="Pick", filter=""):
    with forms.WarningBar(title=title):
        return uidoc.Selection.PickObjects(ObjectType.Element, CustomISelectionFilter(filter))


doc = revit.doc
uidoc = revit.uidoc


try:
    pipes = pick_objects(
        title="Pick pipes to be connected", filter="Pipes")
except:
    forms.alert(title="Program Error",
                msg="You didn't pick any pipe", exitscript=True)

fittings = []
connectors = {}
connlist = []

for pipe in pipes:
    pipe = doc.GetElement(pipe)
    conns = pipe.ConnectorManager.Connectors
    for conn in conns:
        if conn.IsConnected:  # get only connected
            continue
        connectors[conn] = None
        connlist.append(conn)
        print(conn)

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
    if mindist > 1:
        continue
    connectors[k] = closest
    connlist.remove(closest)
    try:
        del connectors[closest]
    except:
        pass

transaction = Transaction(doc, 'Air terminal calculator - PYLAB')
transaction.Start()

for k, v in connectors.items():
    print(k.CoordinateSystem)
    print(k.Origin)
    try:
        fitting = doc.Create.NewElbowFitting(k, v)
        fittings.append(fitting.ToDSType(False))
    except:
        pass
p1 = XYZ(-8.847503179, -1.335469686, 9.022309711)
p2 = XYZ(-12.010972410, -1.335469686, 9.022309711)
Plumbing.Pipe.Create(doc, ElementId(592532), ElementId(142438), ElementId(311), p1, p2)


transaction.Commit()
