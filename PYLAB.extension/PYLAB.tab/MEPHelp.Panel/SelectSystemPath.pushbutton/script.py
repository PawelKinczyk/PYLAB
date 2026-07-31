"""Select all elements in pipe/duct system between two picked points.

BFS over connector graph within the system for shortest path.
"""

import clr

from Autodesk.Revit.DB import (
    BuiltInCategory,
    ElementId,
    MechanicalSystem,
    PipingSystem,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from collections import deque
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

clr.AddReference("System.Core")

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

PIPE_CATEGORIES = [
    BuiltInCategory.OST_PipeCurves,
    BuiltInCategory.OST_PipeFitting,
    BuiltInCategory.OST_PipeAccessory,
]

DUCT_CATEGORIES = [
    BuiltInCategory.OST_DuctCurves,
    BuiltInCategory.OST_DuctFitting,
    BuiltInCategory.OST_DuctAccessory,
]


class MEPElementFilter(ISelectionFilter):
    """Allow only pipe or duct element selection."""

    def AllowElement(self, elem):
        if elem is None:
            return False
        cat = elem.Category
        if cat is None:
            return False
        cat_id = cat.Id.IntegerValue
        allowed = [int(c) for c in PIPE_CATEGORIES + DUCT_CATEGORIES]
        return cat_id in allowed

    def AllowReference(self, ref, point):
        return True


def get_system_elements(mep_element):
    """Get all elements in the same MEPSystem as the given element."""
    system = None

    # Try pipe system
    try:
        system = mep_element.MEPSystem
    except Exception:
        pass

    if system is None:
        return set()

    element_ids = set()
    try:
        # PipingSystem: use PipingNetwork.Elements
        if hasattr(system, "PipingNetwork") and system.PipingNetwork is not None:
            for elem_id in system.PipingNetwork.Elements:
                element_ids.Add(elem_id)
        # MechanicalSystem: use DuctNetwork equivalent
        elif hasattr(system, "DuctNetwork") and system.DuctNetwork is not None:
            for elem_id in system.DuctNetwork.Elements:
                element_ids.Add(elem_id)
        else:
            # Fallback: iterate system elements directly
            for elem_id in system.Elements:
                element_ids.Add(elem_id)
    except Exception:
        # Ultimate fallback for older API
        try:
            for elem_id in system.Elements:
                element_ids.Add(elem_id)
        except Exception:
            return set()

    return element_ids


def get_element_connectors(elem):
    """Return list of connector objects for an element."""
    connectors = []
    try:
        conn_mgr = elem.ConnectorManager
        if conn_mgr is not None:
            for conn in conn_mgr.Connectors:
                connectors.append(conn)
    except Exception:
        pass

    try:
        mep_model = elem.MEPModel
        if mep_model is not None:
            conn_mgr = mep_model.ConnectorManager
            if conn_mgr is not None:
                for conn in conn_mgr.Connectors:
                    connectors.append(conn)
    except Exception:
        pass

    return connectors


def get_neighbors(elem, system_element_ids):
    """Return set of neighboring element IDs in the same system."""
    neighbors = set()
    connectors = get_element_connectors(elem)
    for conn in connectors:
        try:
            for ref in conn.AllRefs:
                owner_id = ref.Owner.Id
                if owner_id in system_element_ids and owner_id != elem.Id:
                    neighbors.Add(owner_id)
        except Exception:
            pass
    return neighbors


def bfs_shortest_path(start_id, end_id, system_element_ids):
    """BFS from start to end within the connector graph. Returns list of ElementIds or None."""
    if start_id == end_id:
        return [start_id]

    visited = {start_id}
    parent = {start_id: None}
    queue = deque([start_id])

    while queue:
        current = queue.popleft()
        elem = doc.GetElement(current)
        if elem is None:
            continue

        for neighbor_id in get_neighbors(elem, system_element_ids):
            if neighbor_id in visited:
                continue
            visited.Add(neighbor_id)
            parent[neighbor_id] = current

            if neighbor_id == end_id:
                # Reconstruct path
                path = []
                node = end_id
                while node is not None:
                    path.append(node)
                    node = parent[node]
                path.reverse()
                return path

            queue.append(neighbor_id)

    return None


def get_total_length(path_element_ids):
    """Sum length parameter of path elements. Returns feet (internal units)."""
    total = 0.0
    for elem_id in path_element_ids:
        elem = doc.GetElement(elem_id)
        if elem is None:
            continue
        try:
            length_param = elem.get_Parameter(
                BuiltInParameter.CURVE_ELEM_LENGTH
            )
            if length_param is not None and length_param.HasValue:
                total += length_param.AsDouble()
        except Exception:
            pass
    return total


def main():
    # Pick start element
    with forms.WarningBar(title="Pick START element (pipe/duct fitting/accessory)"):
        try:
            start_ref = uidoc.Selection.PickObject(
                ObjectType.Element, MEPElementFilter(), "Pick start element"
            )
        except Exception:
            output.print_md("**Cancelled** — no start element picked.")
            return

    start_elem = doc.GetElement(start_ref.ElementId)

    # Pick end element
    with forms.WarningBar(title="Pick END element (pipe/duct fitting/accessory)"):
        try:
            end_ref = uidoc.Selection.PickObject(
                ObjectType.Element, MEPElementFilter(), "Pick end element"
            )
        except Exception:
            output.print_md("**Cancelled** — no end element picked.")
            return

    end_elem = doc.GetElement(end_ref.ElementId)

    # Validate same system
    system_ids = get_system_elements(start_elem)
    if end_elem.Id not in system_ids:
        output.print_md(
            "**Error**: Start and end elements are not in the same system."
        )
        return

    if not system_ids:
        output.print_md(
            "**Error**: Could not retrieve system elements. "
            "Ensure both elements are part of a pipe or duct system."
        )
        return

    # BFS
    path = bfs_shortest_path(start_elem.Id, end_elem.Id, system_ids)

    if path is None:
        output.print_md(
            "**No path found** between the two elements in the system."
        )
        return

    # Select path
    try:
        from System.Collections.Generic import List

        id_list = List[ElementId]()
        for eid in path:
            id_list.Add(eid)
        uidoc.Selection.SetElementIds(id_list)
    except Exception:
        # Older API fallback
        selection = uidoc.Selection.GetElementIds()
        selection.Clear()
        for eid in path:
            selection.Add(eid)
        uidoc.Selection.SetElementIds(selection)

    # Report
    length_ft = get_total_length(path)
    length_m = length_ft * 0.3048

    output.print_md("# System Path Result")
    output.print_md(
        "**{} elements** selected in the shortest path.".format(len(path))
    )
    output.print_md(
        "Total length: **{:.2f} ft** ({:.2f} m)".format(length_ft, length_m)
    )


if __name__ == "__main__":
    main()
