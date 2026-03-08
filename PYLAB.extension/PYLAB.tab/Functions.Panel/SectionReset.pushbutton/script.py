import math

from Autodesk.Revit.DB import BoundingBoxXYZ, Transaction, Transform, View3D, XYZ
from pyrevit import forms, revit


doc = revit.doc
uidoc = revit.uidoc

COMMAND_TITLE = "SectionReset"
ACTION_RESET = "Reset rotation"
ACTION_ROTATE_POS_45 = "Rotate +45"
ACTION_ROTATE_NEG_45 = "Rotate -45"
ACTION_ROTATE_POS_90 = "Rotate +90"
ACTION_ROTATE_NEG_90 = "Rotate -90"

ACTION_ANGLES = {
    ACTION_ROTATE_POS_45: 45.0,
    ACTION_ROTATE_NEG_45: -45.0,
    ACTION_ROTATE_POS_90: 90.0,
    ACTION_ROTATE_NEG_90: -90.0,
}


def show_warning(message):
    forms.alert(
        msg=message,
        title=COMMAND_TITLE,
        warn_icon=True,
        exitscript=False,
    )


def get_active_view3d_with_section_box():
    active_view = uidoc.ActiveView
    if not isinstance(active_view, View3D):
        show_warning("SectionReset works only in an active 3D view.")
        return None

    try:
        if active_view.IsTemplate:
            show_warning("SectionReset cannot run on a 3D view template.")
            return None
    except Exception:
        pass

    try:
        if not active_view.IsSectionBoxActive:
            show_warning("The active 3D view does not have Section Box enabled.")
            return None
    except Exception:
        show_warning("Could not determine whether the active 3D view has Section Box enabled.")
        return None

    try:
        section_box = active_view.GetSectionBox()
    except Exception as ex:
        show_warning("Could not read the section box from the active 3D view:\n\n{}".format(ex))
        return None

    if section_box is None:
        show_warning("The active 3D view does not contain a valid section box.")
        return None

    try:
        if section_box.Min is None or section_box.Max is None or section_box.Transform is None:
            show_warning("The active 3D view section box is invalid.")
            return None
    except Exception:
        show_warning("The active 3D view section box is invalid.")
        return None

    return active_view


def get_section_box_corners(section_box):
    transform = section_box.Transform
    min_point = section_box.Min
    max_point = section_box.Max

    # Convert the local box definition into model-space corner points.
    corners_local = [
        XYZ(x, y, z)
        for x in (min_point.X, max_point.X)
        for y in (min_point.Y, max_point.Y)
        for z in (min_point.Z, max_point.Z)
    ]
    return [transform.OfPoint(corner) for corner in corners_local]


def build_world_aligned_section_box(points):
    min_x = min(point.X for point in points)
    min_y = min(point.Y for point in points)
    min_z = min(point.Z for point in points)
    max_x = max(point.X for point in points)
    max_y = max(point.Y for point in points)
    max_z = max(point.Z for point in points)

    new_box = BoundingBoxXYZ()
    new_box.Transform = Transform.Identity
    new_box.Min = XYZ(min_x, min_y, min_z)
    new_box.Max = XYZ(max_x, max_y, max_z)
    return new_box


def get_section_box_center_local(section_box):
    return XYZ(
        (section_box.Min.X + section_box.Max.X) / 2.0,
        (section_box.Min.Y + section_box.Max.Y) / 2.0,
        (section_box.Min.Z + section_box.Max.Z) / 2.0,
    )


def clone_section_box(section_box):
    cloned_box = BoundingBoxXYZ()
    cloned_box.Transform = section_box.Transform
    cloned_box.Min = XYZ(section_box.Min.X, section_box.Min.Y, section_box.Min.Z)
    cloned_box.Max = XYZ(section_box.Max.X, section_box.Max.Y, section_box.Max.Z)
    return cloned_box


def reset_section_box_rotation(view3d):
    section_box = view3d.GetSectionBox()
    corners_world = get_section_box_corners(section_box)
    new_box = build_world_aligned_section_box(corners_world)
    view3d.SetSectionBox(new_box)


def rotate_section_box(view3d, angle_degrees):
    section_box = view3d.GetSectionBox()
    center_local = get_section_box_center_local(section_box)
    center_world = section_box.Transform.OfPoint(center_local)

    angle_radians = math.radians(angle_degrees)
    rotation = Transform.CreateRotationAtPoint(XYZ.BasisZ, angle_radians, center_world)

    rotated_box = clone_section_box(section_box)
    # Apply a world-space rotation around the current section box center.
    rotated_box.Transform = rotation.Multiply(section_box.Transform)
    view3d.SetSectionBox(rotated_box)


def ask_for_action():
    return forms.CommandSwitchWindow.show(
        [
            ACTION_RESET,
            ACTION_ROTATE_POS_45,
            ACTION_ROTATE_NEG_45,
            ACTION_ROTATE_POS_90,
            ACTION_ROTATE_NEG_90,
        ],
        message="Select section box action:",
        recognize_access_key=False,
    )


def main():
    view3d = get_active_view3d_with_section_box()
    if view3d is None:
        return

    selected_action = ask_for_action()
    if not selected_action:
        return

    transaction = Transaction(doc, "SectionReset - PYLAB")
    try:
        transaction.Start()

        if selected_action == ACTION_RESET:
            reset_section_box_rotation(view3d)
        else:
            rotate_section_box(view3d, ACTION_ANGLES[selected_action])

        transaction.Commit()
    except Exception as ex:
        if transaction.HasStarted():
            transaction.RollBack()
        show_warning("Could not modify the section box:\n\n{}".format(ex))


if __name__ == "__main__":
    main()
