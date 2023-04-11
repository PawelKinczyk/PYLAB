import math

from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from Autodesk.Revit.Creation import *
from Autodesk.Revit.Exceptions import ArgumentException
from pyrevit import forms
from pyrevit import revit

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')


# def / class
# Custom filter to allow picking only the mentioned category
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

# Pick object/objects with custom filter


def pick_objects(title="Pick", filter=""):
    with forms.WarningBar(title=title):
        return uidoc.Selection.PickObjects(ObjectType.Element, CustomISelectionFilter(filter))

# Mesure distance between two points


def distance(xyz1, xyz2):
    d = 0.0
    d = math.sqrt((xyz2[0] - xyz1[0])**2 + (xyz2[1] -
                  xyz1[1])**2 + (xyz2[2] - xyz1[2])**2)
    return d

# Pick right category and amount of pipes also write error when something is wrong


class PickElements:
    def __init__(self, title="", filter="", error_message="", max_pipes_number=100):
        self.title = title
        self.filter = filter
        self.error_message = error_message
        self.max_pipes_number = max_pipes_number

    def pick_pipes(self):
        try:
            self.pipes = pick_objects(title=self.title, filter=self.filter)
            if len(self.pipes) > self.max_pipes_number:
                forms.alert(title="Program Error", msg="You picked more than {} pipes".format(
                    self.max_pipes_number), exitscript=True)
            return self.pipes
        except:
            forms.alert(title="Program Error",
                        msg=self.error_message, exitscript=True)

# Loop over the pipes and collect all connectors


class GetPipeConnectors(object):
    def __init__(self, pipes_list):
        self.pipes_list = pipes_list
        self.connectors = {}
        self.connlist = []

    def get_connectors(self):

        for pipe in self.pipes_list:
            pipe = doc.GetElement(pipe)
            conns = pipe.ConnectorManager.Connectors
            for conn in conns:
                if conn.IsConnected:  # get only connected
                    continue
                self.connectors[conn] = None
                self.connlist.append(conn)
                # print(conn)
        return self.connlist, self.connectors

# Main function class that create new pipe and connect them together


class CreateParallelPipeAndConnect(GetPipeConnectors):
    def __init__(self, pipes_list, closest_distance=1000000):
        # Parent class is GetPipeConnectors
        super(CreateParallelPipeAndConnect, self).__init__(
            pipes_list=pipes_list)
        self.closest_distance = closest_distance

    # *** CODE FROM DYNAMO NODES WRITEEN BY Alban de Chasteigner https://github.com/albandechasteigner ***
    # Search for two closest connectors to draw pipe between them
    def search_for_closest_connectors(self):
        self.closest_distance = 1000000
        self.closest_connectors = []
        for i in range(len(self.connectors.items())):
            for j in range(len(self.connectors.items())):
                if i != j:
                    xyz1 = self.connectors.items()[i]
                    xyz2 = self.connectors.items()[j]
                    a = distance(xyz1[0].Origin, xyz2[0].Origin)
                    # print(a)
                    if self.closest_distance > a:
                        self.closest_distance = a
                        self.closest_connectors = {
                            xyz1[0]: None, xyz2[0]: None}
        return self.closest_connectors
    # *** ***

    # *** CODE FROM PYREVIT FORUM MANY THANKS TO Nicholas Miles https://github.com/Negazero and Jean-Marc https://github.com/jmcouffin ***
    # Create pipe parallel to two picked pipes
    def create_parallel_pipe(self):
        # Get middle point
        p1 = self.closest_connectors.items()[0]
        p2 = self.closest_connectors.items()[1]

        # Create variable for connector to remove indexing and have more understandable code
        p1_connector = p1[0]
        p2_connector = p2[0]

        # This is the "Direction" of the connector
        p1_vector = p1_connector.CoordinateSystem.BasisZ
        p2_vector = p2_connector.CoordinateSystem.BasisZ

        vector_between_connectors = p1_connector.Origin.Subtract(
            p2_connector.Origin)

        # This will give us the scalar for the projected distance between connectors
        # Multiply 0.5 to get the midpoint of the distance between the vectors
        distance_between_connectors = p2_vector.DotProduct(
            vector_between_connectors) * 0.5

        # Now we add the distance to both of the pipes endpoints
        self.p1_point = p1_connector.Origin.Add(
            p1_vector.Multiply(distance_between_connectors))
        self.p2_point = p2_connector.Origin.Add(
            p2_vector.Multiply(distance_between_connectors))

        is_parallel = round(p1_vector.X * p2_vector.Y -
                            p1_vector.Y * p2_vector.X) == 0.0

        if (p1_connector.Origin.Z - p2_connector.Origin.Z) < 0.0000001 and is_parallel:

            transaction = Transaction(doc, 'Create parallel pipe')
            transaction.Start()
            try:
                parent_pipe = doc.GetElement(self.pipes_list[0])

                self.new_pipe = Plumbing.Pipe.Create(doc, parent_pipe.MEPSystem.GetTypeId(
                ), parent_pipe.GetTypeId(), parent_pipe.ReferenceLevel.Id, self.p1_point, self.p2_point)
                transaction.Commit()
            except ArgumentException:
                transaction.Commit()
                forms.alert(title="Program Error",
                            msg="Please try to move pipes closer", exitscript=True)

            except Exception as e:
                transaction.Commit()
                print(e)

        for conn in self.new_pipe.ConnectorManager.Connectors:
            self.closest_connectors[conn] = None
    # *** ***

    # *** CODE FROM DYNAMO NODES WRITEEN BY Alban de Chasteigner https://github.com/albandechasteigner ***
    # Connect all connectors together
    def connect_pipes(self):
        connlist = self.closest_connectors.keys()
        for k in self.closest_connectors.keys():
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
            self.closest_connectors[k] = closest
            connlist.remove(closest)
            try:
                del self.closest_connectors[closest]
            except:
                pass

        transaction = Transaction(doc, 'Connect pipes - PYLAB')
        transaction.Start()

        for k, v in closest_connectors.items():
            try:
                fitting = doc.Create.NewElbowFitting(k, v)
                fittings.append(fitting.ToDSType(False))
            except:
                pass

        transaction.Commit()
    # *** ***


doc = revit.doc
uidoc = revit.uidoc

pick_pipes = PickElements(title="Pick pipes to be connected", filter="Pipes",
                          error_message="You didn't pick any pipe", max_pipes_number=2)

pipes = pick_pipes.pick_pipes()

get_pipe_connectors = CreateParallelPipeAndConnect(
    pipes_list=pipes, closest_distance=1000000)

get_pipe_connectors.get_connectors()

closest_connectors = get_pipe_connectors.search_for_closest_connectors()

get_pipe_connectors.create_parallel_pipe()

get_pipe_connectors.connect_pipes()
