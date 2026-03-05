import clr

from Autodesk.Revit.DB import (
    BoundingBoxXYZ,
    ElementId,
    FilteredElementCollector,
    Transaction,
    View3D,
    ViewFamily,
    ViewFamilyType,
    XYZ,
)
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")
from System.Collections.Generic import List
from System.Drawing import Point, Size
from System.Windows.Forms import (
    Button,
    CheckBox,
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

M_TO_FT = 3.280839895013123
DEFAULT_OFFSET_M = 0.1
DEFAULT_ISOLATE_IN_VIEW = False
FALLBACK_3D_NAME = "PYLAB - Element 3D Focus"


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def show_warning(message):
    forms.alert(
        msg=message,
        title="Element 3D Focus",
        warn_icon=True,
        exitscript=False,
    )


def load_settings():
    cfg = script.get_config()
    offset_m_raw = getattr(cfg, "offset_m", DEFAULT_OFFSET_M)
    isolate_in_view = getattr(cfg, "isolate_in_view", DEFAULT_ISOLATE_IN_VIEW)

    try:
        offset_m = float(str(offset_m_raw).replace(",", "."))
    except Exception:
        offset_m = DEFAULT_OFFSET_M

    if offset_m < 0:
        offset_m = DEFAULT_OFFSET_M

    return offset_m, bool(isolate_in_view)


def save_settings(offset_m, isolate_in_view):
    cfg = script.get_config()
    cfg.offset_m = float(offset_m)
    cfg.isolate_in_view = bool(isolate_in_view)
    script.save_config()


def parse_offset_m(text_value):
    if text_value is None:
        return None
    value = text_value.strip().replace(",", ".")
    if not value:
        return None
    return float(value)


class SettingsDialog(Form):
    def __init__(self, current_offset_m, current_isolate_in_view):
        self.Text = "Element 3D Focus settings"
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(520, 230)
        self.MinimizeBox = False
        self.MaximizeBox = False

        title_label = Label()
        title_label.Text = "Configure behavior for Element 3D Focus:"
        title_label.Location = Point(16, 12)
        title_label.Size = Size(490, 20)
        self.Controls.Add(title_label)

        offset_label = Label()
        offset_label.Text = "3D section box offset around element [m]:"
        offset_label.Location = Point(16, 45)
        offset_label.Size = Size(300, 20)
        self.Controls.Add(offset_label)

        self.offset_text = TextBox()
        self.offset_text.Text = str(current_offset_m)
        self.offset_text.Location = Point(325, 43)
        self.offset_text.Size = Size(90, 24)
        self.Controls.Add(self.offset_text)

        offset_help = Label()
        offset_help.Text = "Use non-negative meters. Both 0.1 and 0,1 are accepted."
        offset_help.Location = Point(16, 70)
        offset_help.Size = Size(490, 20)
        self.Controls.Add(offset_help)

        self.isolate_checkbox = CheckBox()
        self.isolate_checkbox.Text = "Temporarily isolate element in {3D} view"
        self.isolate_checkbox.Checked = bool(current_isolate_in_view)
        self.isolate_checkbox.Location = Point(16, 105)
        self.isolate_checkbox.Size = Size(350, 22)
        self.Controls.Add(self.isolate_checkbox)

        ok_button = Button()
        ok_button.Text = "Save"
        ok_button.Location = Point(330, 176)
        ok_button.Size = Size(85, 28)
        ok_button.Click += self._on_ok_click
        self.Controls.Add(ok_button)

        cancel_button = Button()
        cancel_button.Text = "Cancel"
        cancel_button.Location = Point(421, 176)
        cancel_button.Size = Size(85, 28)
        cancel_button.DialogResult = DialogResult.Cancel
        self.Controls.Add(cancel_button)

        self.AcceptButton = ok_button
        self.CancelButton = cancel_button

        self.result_offset_m = None
        self.result_isolate_in_view = None

    def _on_ok_click(self, sender, args):
        try:
            offset_m = parse_offset_m(self.offset_text.Text)
            if offset_m is None or offset_m < 0:
                raise ValueError
        except Exception:
            MessageBox.Show(
                "Invalid offset. Use a non-negative number in meters.",
                "Element 3D Focus",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        self.result_offset_m = offset_m
        self.result_isolate_in_view = self.isolate_checkbox.Checked
        self.DialogResult = DialogResult.OK
        self.Close()


def show_settings_dialog():
    current_offset_m, current_isolate_in_view = load_settings()
    dialog = SettingsDialog(current_offset_m, current_isolate_in_view)
    if dialog.ShowDialog() != DialogResult.OK:
        return
    save_settings(dialog.result_offset_m, dialog.result_isolate_in_view)


def ask_for_element_id():
    raw_id = forms.ask_for_string(
        prompt="Type element ID",
        title="Element 3D Focus",
        default="",
    )
    if raw_id is None:
        return None

    value = raw_id.strip()
    if not value:
        return None

    try:
        int_value = int(value)
    except Exception:
        show_warning("Invalid element id. Enter an integer value.")
        return None

    return ElementId(int_value)


def _get_non_template_3d_view_by_name(view_name):
    collector = FilteredElementCollector(doc).OfClass(View3D)
    for view_3d in collector:
        try:
            if view_3d.IsTemplate:
                continue
            if view_3d.Name == view_name:
                return view_3d
        except Exception:
            continue
    return None


def _create_fallback_3d_view():
    view_family_type_id = None
    vft_collector = FilteredElementCollector(doc).OfClass(ViewFamilyType)
    for view_family_type in vft_collector:
        try:
            if view_family_type.ViewFamily == ViewFamily.ThreeDimensional:
                view_family_type_id = view_family_type.Id
                break
        except Exception:
            continue

    if not view_family_type_id:
        return None

    tx = Transaction(doc, "Create 3D view - PYLAB")
    created_view = None
    try:
        tx.Start()
        created_view = View3D.CreateIsometric(doc, view_family_type_id)
        if created_view:
            try:
                created_view.Name = FALLBACK_3D_NAME
            except Exception:
                pass
        tx.Commit()
    except Exception:
        if tx.HasStarted():
            tx.RollBack()
        return None

    return created_view


def get_or_create_target_3d_view():
    default_view = _get_non_template_3d_view_by_name("{3D}")
    if default_view:
        return default_view

    fallback_view = _get_non_template_3d_view_by_name(FALLBACK_3D_NAME)
    if fallback_view:
        return fallback_view

    return _create_fallback_3d_view()


def is_3d_view_locked(view_3d):
    try:
        return bool(view_3d.IsLocked)
    except Exception:
        return False


def get_element_bbox(element):
    bbox = element.get_BoundingBox(None)
    if bbox:
        return bbox

    active_view = uidoc.ActiveView
    if active_view:
        return element.get_BoundingBox(active_view)

    return None


def expand_bbox(bbox, offset_ft):
    expanded = BoundingBoxXYZ()
    expanded.Min = XYZ(
        bbox.Min.X - offset_ft,
        bbox.Min.Y - offset_ft,
        bbox.Min.Z - offset_ft,
    )
    expanded.Max = XYZ(
        bbox.Max.X + offset_ft,
        bbox.Max.Y + offset_ft,
        bbox.Max.Z + offset_ft,
    )
    return expanded


def set_ui_selection(element_id):
    ids = List[ElementId]()
    ids.Add(element_id)
    uidoc.Selection.SetElementIds(ids)


def focus_element_in_3d(element, target_view_3d, offset_m, isolate_in_view):
    bbox = get_element_bbox(element)
    if not bbox:
        show_warning("Could not read element bounding box.")
        return

    offset_ft = offset_m * M_TO_FT
    section_box = expand_bbox(bbox, offset_ft)

    uidoc.ActiveView = target_view_3d

    tx = Transaction(doc, "Element 3D Focus - PYLAB")
    try:
        tx.Start()
        target_view_3d.IsSectionBoxActive = True
        target_view_3d.SetSectionBox(section_box)

        if isolate_in_view:
            ids = List[ElementId]()
            ids.Add(element.Id)
            target_view_3d.IsolateElementsTemporary(ids)

        tx.Commit()
    except Exception as ex:
        if tx.HasStarted():
            tx.RollBack()
        show_warning("Could not update 3D view: {}".format(ex))
        return


def main():
    if get_shiftclick_state():
        show_settings_dialog()
        return

    target_element_id = ask_for_element_id()
    if not target_element_id:
        return

    element = doc.GetElement(target_element_id)
    if not element:
        show_warning("Element doesn't exist")
        return

    view_3d = get_or_create_target_3d_view()
    if not view_3d:
        show_warning("No usable 3D view found and could not create a new 3D view.")
        return
    if is_3d_view_locked(view_3d):
        show_warning('3D view is locked, unlock it -> "{}"'.format(view_3d.Name))
        return

    offset_m, isolate_in_view = load_settings()
    set_ui_selection(target_element_id)
    focus_element_in_3d(element, view_3d, offset_m, isolate_in_view)


if __name__ == "__main__":
    main()
