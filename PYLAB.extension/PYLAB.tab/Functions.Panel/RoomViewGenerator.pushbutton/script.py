"""Generate sections and 3D views for selected rooms/spaces.

Room.GetBoundarySegments → accurate bounding box → ViewSection.CreateSection
per direction. Optional 3D view with section box (reuses Element3DFocus math).
"""

import clr
import os
import re

from Autodesk.Revit.DB import (
    BoundingBoxXYZ,
    BuiltInCategory,
    BuiltInParameter,
    ElementId,
    FilteredElementCollector,
    SpatialElementBoundaryOptions,
    Transaction,
    TransactionGroup,
    Transform,
    View,
    View3D,
    ViewFamily,
    ViewFamilyType,
    ViewSection,
    ViewType,
    XYZ,
)
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
    CheckBox,
    CheckedListBox,
    DialogResult,
    Form,
    FormBorderStyle,
    FormStartPosition,
    Label,
    MessageBox,
    MessageBoxButtons,
    MessageBoxIcon,
    TextBox,
)

doc = revit.doc
uidoc = revit.uidoc
output = script.get_output()

FORBIDDEN_CHARS = re.compile(r'[:{}\[\]|;<>?\'~]')

DIRECTIONS = {
    "North": XYZ(0, 1, 0),
    "South": XYZ(0, -1, 0),
    "East": XYZ(1, 0, 0),
    "West": XYZ(-1, 0, 0),
}


def sanitize_name(name):
    """Remove Revit-forbidden characters from a view name."""
    return FORBIDDEN_CHARS.sub("", name)


def make_unique_name(base_name):
    """Ensure view name is unique. Appends (2), (3)... if needed."""
    name = sanitize_name(base_name)
    existing = set()
    all_views = FilteredElementCollector(doc).OfClass(View)
    for v in all_views:
        if v.Name:
            existing.Add(v.Name)

    if name not in existing:
        return name

    counter = 2
    while True:
        candidate = "{} ({})".format(name, counter)
        if candidate not in existing:
            return candidate
        counter += 1


def get_room_boundary(room):
    """Get accurate boundary of a room from its boundary segments. Returns BoundingBoxXYZ."""
    options = SpatialElementBoundaryOptions()
    options.SpatialElementBoundaryLocation = (
        SpatialElementBoundaryOptions.SpatialElementBoundaryLocation.Finish
    )

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    try:
        boundary_segments = room.GetBoundarySegments(options)
        if boundary_segments:
            for loop in boundary_segments:
                for segment in loop:
                    curve = segment.GetCurve()
                    for point in (curve.GetEndPoint(0), curve.GetEndPoint(1)):
                        pt = point
                        min_x = min(min_x, pt.X)
                        min_y = min(min_y, pt.Y)
                        min_z = min(min_z, pt.Z)
                        max_x = max(max_x, pt.X)
                        max_y = max(max_y, pt.Y)
                        max_z = max(max_z, pt.Z)
        else:
            # Fallback: use room bounding box
            bbox = room.get_BoundingBox(None)
            if bbox is not None:
                return bbox
    except Exception:
        bbox = room.get_BoundingBox(None)
        if bbox is not None:
            return bbox

    if min_x == float("inf"):
        bbox = room.get_BoundingBox(None)
        if bbox is not None:
            return bbox
        return None

    # Add small margin
    margin = 1.0
    bbox = BoundingBoxXYZ()
    bbox.Min = XYZ(min_x - margin, min_y - margin, min_z - margin)
    bbox.Max = XYZ(max_x + margin, max_y + margin, max_z + margin)
    return bbox


def get_section_view_family_type():
    """Get the first Section ViewFamilyType."""
    vft_collector = FilteredElementCollector(doc).OfClass(ViewFamilyType)
    for vft in vft_collector:
        if vft.ViewFamily == ViewFamily.Section:
            return vft
    return None


def get_3d_view_family_type():
    """Get the 3D ViewFamilyType."""
    vft_collector = FilteredElementCollector(doc).OfClass(ViewFamilyType)
    for vft in vft_collector:
        if vft.ViewFamily == ViewFamily.ThreeDimensional:
            return vft
    return None


def create_section_view(room, direction_key, direction_vec, view_family_type):
    """Create a section view for a room in the given direction.

    Direction vector points in the view direction (e.g., North = (0,1,0)).
    Section plane is perpendicular to direction.
    """
    bbox = get_room_boundary(room)
    if bbox is None:
        return None, "Could not compute room boundary"

    # Build section box transform
    # Section view looks toward the direction vector
    # Origin: center of room bounding box
    center_x = (bbox.Min.X + bbox.Max.X) / 2.0
    center_y = (bbox.Min.Y + bbox.Max.Y) / 2.0
    center_z = (bbox.Min.Z + bbox.Max.Z) / 2.0

    origin = XYZ(center_x, center_y, center_z)
    view_dir = direction_vec

    # Up vector is always Z
    up_dir = XYZ(0, 0, 1)

    # Build transform: origin at center, facing direction
    transform = Transform.Identity
    transform.Origin = origin
    transform.BasisX = XYZ(-view_dir.Y, view_dir.X, 0)  # right = perpendicular to view dir
    transform.BasisY = up_dir
    transform.BasisZ = view_dir  # view direction

    # Section box dimensions
    span_x = (bbox.Max.X - bbox.Min.X) + 2.0
    span_y = (bbox.Max.Y - bbox.Min.Y) + 2.0
    span_z = (bbox.Max.Z - bbox.Min.Z) + 2.0

    try:
        section_box = BoundingBoxXYZ()
        section_box.Transform = transform
        section_box.Min = XYZ(-max(span_x, span_y) / 2.0, -span_z / 2.0, -20.0)
        section_box.Max = XYZ(max(span_x, span_y) / 2.0, span_z / 2.0, 20.0)

        view = ViewSection.CreateSection(doc, view_family_type.Id, section_box)
        return view, None
    except Exception as exc:
        return None, str(exc)


def create_3d_view(room, view_family_type):
    """Create a 3D view with section box for the room."""
    bbox = get_room_boundary(room)
    if bbox is None:
        return None, "Could not compute room boundary"

    try:
        # Create default 3D view
        view3d = View3D.CreateIsometric(doc, view_family_type.Id)
        if view3d is None:
            return None, "Failed to create 3D view"

        # Apply section box
        margin = 1.0
        section_box = BoundingBoxXYZ()
        section_box.Min = XYZ(bbox.Min.X - margin, bbox.Min.Y - margin, bbox.Min.Z - margin)
        section_box.Max = XYZ(bbox.Max.X + margin, bbox.Max.Y + margin, bbox.Max.Z + margin)
        view3d.SetSectionBox(section_box)

        return view3d, None
    except Exception as exc:
        return None, str(exc)


def get_room_list():
    """Get all rooms and spaces in the document as (id, name, number)."""
    items = []

    # Rooms
    rooms = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms)
    for room in rooms:
        if room is None:
            continue
        try:
            number_param = room.get_Parameter(BuiltInParameter.ROOM_NUMBER)
            number = number_param.AsString() if number_param and number_param.HasValue else ""
        except Exception:
            number = room.Number if hasattr(room, "Number") else ""

        name = room.get_Name() if room.get_Name() else ""

        display = "{} - {}".format(number, name) if number and name else (number or name or "Room {}".format(room.Id.IntegerValue))
        items.append((room.Id, display, number, name, "Room"))

    # Spaces
    spaces = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_MEPSpaces)
    for space in spaces:
        if space is None:
            continue
        try:
            number_param = space.get_Parameter(BuiltInParameter.SPACE_NUMBER)
            number = number_param.AsString() if number_param and number_param.HasValue else ""
        except Exception:
            number = space.Number if hasattr(space, "Number") else ""

        name = space.get_Name() if space.get_Name() else ""

        display = "{} - {}".format(number, name) if number and name else (number or name or "Space {}".format(space.Id.IntegerValue))
        items.append((space.Id, display, number, name, "Space"))

    return items


class RoomViewGeneratorForm(Form):
    """WinForms dialog for room view generation."""

    def __init__(self, room_items):
        Form.__init__(self)
        self.Text = "Room View Generator"
        self.Size = Size(700, 620)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._room_items = room_items
        self._build_ui()

    def _build_ui(self):
        y = 10

        # Filter textbox
        filter_label = Label()
        filter_label.Text = "Filter:"
        filter_label.Location = Point(12, y + 3)
        filter_label.Size = Size(40, 20)
        self.Controls.Add(filter_label)

        self._filter_box = TextBox()
        self._filter_box.Location = Point(55, y)
        self._filter_box.Size = Size(200, 23)
        self._filter_box.TextChanged += self._on_filter_changed
        self.Controls.Add(self._filter_box)
        y += 30

        # Select all / none
        select_all = Button()
        select_all.Text = "All"
        select_all.Location = Point(12, y)
        select_all.Size = Size(50, 23)
        select_all.Click += lambda s, e: self._set_all(True)
        self.Controls.Add(select_all)

        select_none = Button()
        select_none.Text = "None"
        select_none.Location = Point(65, y)
        select_none.Size = Size(50, 23)
        select_none.Click += lambda s, e: self._set_all(False)
        self.Controls.Add(select_none)
        y += 28

        # Room list
        self._room_list = CheckedListBox()
        self._room_list.Location = Point(12, y)
        self._room_list.Size = Size(380, 300)
        self._room_list.CheckOnClick = True
        self.Controls.Add(self._room_list)
        y += 310

        # Directions
        dir_label = Label()
        dir_label.Text = "Directions:"
        dir_label.Location = Point(12, y + 3)
        dir_label.Size = Size(60, 20)
        self.Controls.Add(dir_label)

        self._dir_north = CheckBox()
        self._dir_north.Text = "North"
        self._dir_north.Location = Point(75, y)
        self._dir_north.Size = Size(70, 23)
        self._dir_north.Checked = True
        self.Controls.Add(self._dir_north)

        self._dir_south = CheckBox()
        self._dir_south.Text = "South"
        self._dir_south.Location = Point(150, y)
        self._dir_south.Size = Size(70, 23)
        self.Controls.Add(self._dir_south)

        self._dir_east = CheckBox()
        self._dir_east.Text = "East"
        self._dir_east.Location = Point(225, y)
        self._dir_east.Size = Size(70, 23)
        self.Controls.Add(self._dir_east)

        self._dir_west = CheckBox()
        self._dir_west.Text = "West"
        self._dir_west.Location = Point(300, y)
        self._dir_west.Size = Size(70, 23)
        self.Controls.Add(self._dir_west)
        y += 30

        # 3D option
        self._gen_3d = CheckBox()
        self._gen_3d.Text = "Also generate 3D view with section box"
        self._gen_3d.Location = Point(75, y)
        self._gen_3d.Size = Size(280, 23)
        self.Controls.Add(self._gen_3d)
        y += 40

        # Generate button
        gen_btn = Button()
        gen_btn.Text = "Generate"
        gen_btn.Location = Point(450, 500)
        gen_btn.Size = Size(100, 30)
        gen_btn.Click += self._on_generate
        self.Controls.Add(gen_btn)

        # Close button
        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(560, 500)
        close_btn.Size = Size(100, 30)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

        # Populate list
        self._populate_list("")

    def _populate_list(self, filter_text):
        self._room_list.Items.Clear()
        filter_lower = filter_text.lower()
        for item in self._room_items:
            elem_id, display, number, name, kind = item
            if filter_lower and filter_lower not in display.lower():
                continue
            self._room_list.Items.Add(display)

    def _on_filter_changed(self, sender, event_args):
        self._populate_list(self._filter_box.Text)

    def _set_all(self, checked):
        for i in range(self._room_list.Items.Count):
            self._room_list.SetItemChecked(i, checked)

    def _get_selected_rooms(self):
        selected = []
        for i in range(self._room_list.Items.Count):
            if self._room_list.GetItemChecked(i):
                display = self._room_list.Items[i]
                # Find matching item
                for item in self._room_items:
                    if item[1] == display:
                        selected.append(item)
                        break
        return selected

    def _get_selected_directions(self):
        dirs = []
        if self._dir_north.Checked:
            dirs.append(("North", DIRECTIONS["North"]))
        if self._dir_south.Checked:
            dirs.append(("South", DIRECTIONS["South"]))
        if self._dir_east.Checked:
            dirs.append(("East", DIRECTIONS["East"]))
        if self._dir_west.Checked:
            dirs.append(("West", DIRECTIONS["West"]))
        return dirs

    def _on_generate(self, sender, event_args):
        selected = self._get_selected_rooms()
        if not selected:
            MessageBox.Show(
                self,
                "Select at least one room/space.",
                "No selection",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        dirs = self._get_selected_directions()
        if not dirs:
            MessageBox.Show(
                self,
                "Select at least one direction.",
                "No direction",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        gen_3d = self._gen_3d.Checked

        view_family_type = get_section_view_family_type()
        if view_family_type is None:
            MessageBox.Show(
                self,
                "No Section ViewFamilyType found in document.",
                "Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error,
            )
            return

        view3d_family_type = None
        if gen_3d:
            view3d_family_type = get_3d_view_family_type()
            if view3d_family_type is None:
                MessageBox.Show(
                    self,
                    "No 3D ViewFamilyType found in document.",
                    "Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error,
                )
                return

        # Generate
        success = 0
        failed = 0

        with TransactionGroup(doc, "Room View Generator") as tg:
            tg.Start()

            for elem_id, display, number, name, kind in selected:
                room = doc.GetElement(elem_id)
                if room is None:
                    failed += 1
                    continue

                base_name = "{} - {}".format(number, name) if number and name else (number or name or kind)

                # Section views per direction
                for dir_key, dir_vec in dirs:
                    with Transaction(doc, "Create {} section for {}".format(dir_key, base_name)) as t:
                        t.Start()
                        view_name = make_unique_name("{} - Section {}".format(base_name, dir_key))
                        view, error = create_section_view(
                            room, dir_key, dir_vec, view_family_type
                        )
                        if view is not None:
                            view.Name = view_name
                            success += 1
                            t.Commit()
                        else:
                            failed += 1
                            t.RollBack()

                # 3D view
                if gen_3d:
                    with Transaction(doc, "Create 3D view for {}".format(base_name)) as t:
                        t.Start()
                        view_name = make_unique_name("{} - 3D".format(base_name))
                        view, error = create_3d_view(room, view3d_family_type)
                        if view is not None:
                            view.Name = view_name
                            success += 1
                            t.Commit()
                        else:
                            failed += 1
                            t.RollBack()

            tg.Assimilate()

        # Report
        output.print_md("# Room View Generator — Results")
        output.print_md("**{} views created** | {} failed".format(success, failed))
        output.print_md(
            "Rooms/spaces processed: {}  |  Directions: {}  |  3D: {}".format(
                len(selected), len(dirs), "Yes" if gen_3d else "No"
            )
        )

        self.Close()


def main():
    room_items = get_room_list()
    if not room_items:
        forms.alert(
            "No rooms or spaces found in this model.",
            title="Room View Generator",
        )
        return

    form = RoomViewGeneratorForm(room_items)
    form.ShowDialog()


if __name__ == "__main__":
    main()
