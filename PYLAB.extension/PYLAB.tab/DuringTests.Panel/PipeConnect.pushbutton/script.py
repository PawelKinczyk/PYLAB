import os
import math

from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from Autodesk.Revit.Creation import *
from pyrevit import forms
from pyrevit import output
from pyrevit import revit

from System.Collections.Generic import List
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
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

def distance(xyz1, xyz2):
    d = 0.0
    d = math.sqrt((xyz2[0] - xyz1[0])**2 + (xyz2[1] - xyz1[1])**2 + (xyz2[2] - xyz1[2])**2)
    return d

class PickElements:
    def __init__(self, title="", filter="", error_message="", max_pipes_number=100):
        self.title = title
        self.filter = filter
        self.error_message = error_message
        self.max_pipes_number = max_pipes_number
    def pick_pipes(self):
        try:
            self.pipes = pick_objects(title=self.title, filter=self.filter)
            if len(self.pipes)>self.max_pipes_number:
                forms.alert(title="Program Error", msg="You picked more than {} pipes".format(self.max_pipes_number), exitscript=True)
            return self.pipes
        except:
            forms.alert(title="Program Error", msg=self.error_message, exitscript=True)

class GetPipeConnectors(object):
    def __init__(self, pipes_list):
        self.pipes_list=pipes_list
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
                print(conn)
        return self.connlist, self.connectors

class CreateParallelPipeAndConnect(GetPipeConnectors):
    def __init__(self, pipes_list, closest_distance=1000000):
        super(CreateParallelPipeAndConnect, self).__init__(pipes_list=pipes_list)
        self.closest_distance = closest_distance

    def search_for_closest_connectors(self):
        self.closest_distance = 1000000
        self.closest_connectors = []
        for i in range(len(self.connectors.items())):
            for j in range(len(self.connectors.items())):
                if i != j:
                    xyz1 = self.connectors.items()[i]
                    xyz2 = self.connectors.items()[j]
                    a = distance(xyz1[0].Origin, xyz2[0].Origin)
                    print(a)
                    if self.closest_distance > a:
                        self.closest_distance = a
                        self.closest_connectors={xyz1[0]: None, xyz2[0]:None}
        return self.closest_connectors
    def create_parallel_pipe(self):
        ## get middle point
        p1 = self.closest_connectors.items()[0]
        p2 = self.closest_connectors.items()[1]

        # create variable for connector to remove indexing and have more understandable code
        p1_connector = p1[0]
        p2_connector = p2[0]

        # this is the "Direction" of the connector
        p1_vector = p1_connector.CoordinateSystem.BasisZ
        p2_vector = p2_connector.CoordinateSystem.BasisZ

        vector_between_connectors = p1_connector.Origin.Subtract(p2_connector.Origin)

        # this will give us the scalar for the projected distance between connectors
        # multiply 0.5 to get the midpoint of the distance between the vectors
        distance_between_connectors = p2_vector.DotProduct(vector_between_connectors) * 0.5

        # now we add the distance to both of the pipes endpoints
        self.p1_point = p1_connector.Origin.Add(p1_vector.Multiply(distance_between_connectors))
        self.p2_point = p2_connector.Origin.Add(p2_vector.Multiply(distance_between_connectors))

        is_parallel = round(p1_vector.X * p2_vector.Y - p1_vector.Y * p2_vector.X) == 0.0

        # please use attributes for xyz objects instead of indexing
        # be explicit with your code. indexing just makes the code harder to read and understand
        # I.E. use p1_connector.Origin.Z instead of p1_connector.Origin[2]
        if (p1_connector.Origin.Z - p2_connector.Origin.Z) < 0.0000001 and is_parallel:
            print("Create Pipe!!!")

            transaction = Transaction(doc, 'pipe create')
            transaction.Start()
            self.new_pipe = Plumbing.Pipe.Create(doc, ElementId(592532), ElementId(142438), ElementId(311), self.p1_point, self.p2_point)
            transaction.Commit()
        for conn in self.new_pipe.ConnectorManager.Connectors:
            self.closest_connectors[conn] = None
    
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


        transaction = Transaction(doc, 'Air terminal calculator - PYLAB')
        transaction.Start()

        for k, v in closest_connectors.items():
            print(k)
            try:
                fitting = doc.Create.NewElbowFitting(k, v)
                fittings.append(fitting.ToDSType(False))
            except:
                pass

        transaction.Commit()

doc = revit.doc
uidoc = revit.uidoc

pick_pipes = PickElements(title="Pick pipes to be connected", filter="Pipes", error_message="You didn't pick any pipe", max_pipes_number=2)
pipes = pick_pipes.pick_pipes()


# fittings = []
# connectors = {}
# connlist = []

# for pipe in pipes:
#     pipe = doc.GetElement(pipe)
#     conns = pipe.ConnectorManager.Connectors
#     for conn in conns:
#         if conn.IsConnected:  # get only connected
#             continue
#         connectors[conn] = None
#         connlist.append(conn)
#         print(conn)

# get_pipe_connectors = GetPipeConnectors(pipes_list=pipes)
# connlist, connectors = get_pipe_connectors.get_connectors()

# # search for closest connectors
# closest_distance = 1000000
# closest_connectors = []
# for i in range(len(connectors.items())):
#     for j in range(len(connectors.items())):
#         if i != j:
#             xyz1 = connectors.items()[i]
#             xyz2 = connectors.items()[j]
#             a = distance(xyz1[0].Origin, xyz2[0].Origin)
#             print(a)
#             if closest_distance > a:
#                 closest_distance = a
#                 closest_connectors={xyz1[0]: None, xyz2[0]:None}

# print(closest_connectors)

get_pipe_connectors = CreateParallelPipeAndConnect(pipes_list=pipes, closest_distance=1000000)
get_pipe_connectors.get_connectors()
closest_connectors = get_pipe_connectors.search_for_closest_connectors()
get_pipe_connectors.create_parallel_pipe()
get_pipe_connectors.connect_pipes()

# # create pipe between and add to closest_connectors list
# ## get middle point
# p1 = closest_connectors.items()[0]
# p2 = closest_connectors.items()[1]
# print(p1[0].Owner.Location.Curve)
# vector_p1 = p1[0].Owner.Location.Curve
# vector_p2 = p2[0].Owner.Location.Curve
# vector_p1_num = vector_p1.GetEndPoint(1) - vector_p1.GetEndPoint(0)
# vector_p2_num = vector_p2.GetEndPoint(1) - vector_p2.GetEndPoint(0)
# print(vector_p1_num)
# parrarel = vector_p1_num[0]*vector_p2_num[1]-vector_p1_num[1]*vector_p2_num[0]
# print("parrarel = {}".format(parrarel))
# print("location = {}".format(p1[0].Owner.Location.Curve.Direction))
# print(p1[0].Origin[2] - p2[0].Origin[2])
# print(parrarel ==0.0)

# # create variable for connector to remove indexing and have more understandable code
# p1_connector = p1[0]
# p2_connector = p2[0]

# # this is the "Direction" of the connector
# p1_vector = p1_connector.CoordinateSystem.BasisZ
# p2_vector = p2_connector.CoordinateSystem.BasisZ

# vector_between_connectors = p1_connector.Origin.Subtract(p2_connector.Origin)

# # this will give us the scalar for the projected distance between connectors
# # multiply 0.5 to get the midpoint of the distance between the vectors
# distance_between_connectors = p2_vector.DotProduct(vector_between_connectors) * 0.5

# # now we add the distance to both of the pipes endpoints
# p1_point = p1_connector.Origin.Add(p1_vector.Multiply(distance_between_connectors))
# p2_point = p2_connector.Origin.Add(p2_vector.Multiply(distance_between_connectors))

# is_parallel = round(p1_vector.X * p2_vector.Y - p1_vector.Y * p2_vector.X) == 0.0

# # please use attributes for xyz objects instead of indexing
# # be explicit with your code. indexing just makes the code harder to read and understand
# # I.E. use p1_connector.Origin.Z instead of p1_connector.Origin[2]
# if (p1_connector.Origin.Z - p2_connector.Origin.Z) < 0.0000001 and is_parallel:
#     print("Create Pipe!!!")

#     transaction = Transaction(doc, 'pipe create')
#     transaction.Start()
#     new_pipe = Plumbing.Pipe.Create(doc, ElementId(592532), ElementId(142438), ElementId(311), p1_point, p2_point)
#     transaction.Commit()

# print("New pipe: {}".format(new_pipe))
# print(new_pipe.ConnectorManager.Connectors)

# Add connectors from new pipe
# for conn in new_pipe.ConnectorManager.Connectors:
#     closest_connectors[conn] = None

# connlist = closest_connectors.keys()
# for k in closest_connectors.keys():
#     mindist = 1000000
#     closest = None
#     for conn in connlist:
#         if conn.Owner.Id.Equals(k.Owner.Id):
#             continue
#         dist = k.Origin.DistanceTo(conn.Origin)
#         if dist < mindist:
#             mindist = dist
#             closest = conn
#     if mindist > 1:
#         continue
#     closest_connectors[k] = closest
#     connlist.remove(closest)
#     try:
#         del closest_connectors[closest]
#     except:
#         pass


# transaction = Transaction(doc, 'Air terminal calculator - PYLAB')
# transaction.Start()

# for k, v in closest_connectors.items():
#     print(k)
#     try:
#         fitting = doc.Create.NewElbowFitting(k, v)
#         fittings.append(fitting.ToDSType(False))
#     except:
#         pass

# transaction.Commit()
