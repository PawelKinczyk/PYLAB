import clr

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    ElementTransformUtils,
    InsulationLiningBase,
    Transaction,
    XYZ,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")
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

EPS = 1e-9
FT_TO_MM = 304.8
PARALLEL_TOL = 0.001

DEFAULT_OFFSET_MM = 50.0
DEFAULT_INCLUDE_INSULATION = True


class PipeDuctSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        cat_id = element.Category.Id.IntegerValue
        return cat_id in (
            int(BuiltInCategory.OST_PipeCurves),
            int(BuiltInCategory.OST_DuctCurves),
        )

    def AllowReference(self, reference, point):
        return True


def get_shiftclick_state():
    try:
        return bool(__shiftclick__)
    except Exception:
        return False


def get_double_param(element, bip):
    param = element.get_Parameter(bip)
    if not param:
        return None
    try:
        return param.AsDouble()
    except Exception:
        return None


def get_double_param_by_name(element, bip_name):
    try:
        bip = getattr(BuiltInParameter, bip_name)
    except Exception:
        return None
    return get_double_param(element, bip)


def as_length_mm(text_value):
    if text_value is None:
        return None
    value = text_value.strip().replace(",", ".")
    if not value:
        return None
    return float(value)


def get_curve(element):
    location = getattr(element, "Location", None)
    if not location:
        return None
    curve = getattr(location, "Curve", None)
    if not curve:
        return None
    return curve


def unit_xy(vector):
    vec = XYZ(vector.X, vector.Y, 0.0)
    length = vec.GetLength()
    if length < EPS:
        return None
    return XYZ(vec.X / length, vec.Y / length, 0.0)


def get_plan_reach(element, include_insulation):
    cat_id = element.Category.Id.IntegerValue

    if cat_id == int(BuiltInCategory.OST_PipeCurves):
        # Prefer physical outside diameter for true edge-to-edge spacing.
        diameter = get_double_param_by_name(element, "RBS_PIPE_OUTER_DIAMETER")
        if diameter is None:
            diameter = get_double_param_by_name(element, "RBS_CURVE_OUTER_DIAMETER")
        if diameter is None:
            diameter = get_double_param(element, BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        if diameter is None:
            diameter = get_double_param(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
        if diameter is None or diameter <= 0:
            return None

        reach = diameter * 0.5
        if include_insulation:
            ins = get_insulation_thickness(element, True)
            if ins and ins > 0:
                reach += ins
        return reach

    if cat_id == int(BuiltInCategory.OST_DuctCurves):
        diameter = get_double_param_by_name(element, "RBS_CURVE_OUTER_DIAMETER")
        if diameter is None:
            diameter = get_double_param(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
        if diameter and diameter > 0:
            reach = diameter * 0.5
        else:
            width = get_double_param(element, BuiltInParameter.RBS_CURVE_WIDTH_PARAM)
            if width is None or width <= 0:
                return None
            reach = width * 0.5

        if include_insulation:
            ins = get_insulation_thickness(element, False)
            if ins and ins > 0:
                reach += ins
        return reach

    return None


def get_insulation_thickness_from_element(ins_element, is_pipe):
    if not ins_element:
        return None

    if is_pipe:
        thickness = get_double_param(
            ins_element, BuiltInParameter.RBS_PIPE_INSULATION_THICKNESS
        )
        if thickness and thickness > 0:
            return thickness
    else:
        thickness = get_double_param(
            ins_element, BuiltInParameter.RBS_DUCT_INSULATION_THICKNESS
        )
        if thickness and thickness > 0:
            return thickness

    generic = get_double_param_by_name(ins_element, "RBS_INSULATION_THICKNESS")
    if generic and generic > 0:
        return generic

    for param_name in ("Insulation Thickness", "Thickness"):
        param = ins_element.LookupParameter(param_name)
        if not param:
            continue
        try:
            value = param.AsDouble()
            if value and value > 0:
                return value
        except Exception:
            continue

    return None


def get_insulation_thickness(element, is_pipe):
    # First try host-level parameter (works in some templates/models).
    if is_pipe:
        thickness = get_double_param(element, BuiltInParameter.RBS_PIPE_INSULATION_THICKNESS)
    else:
        thickness = get_double_param(element, BuiltInParameter.RBS_DUCT_INSULATION_THICKNESS)

    if thickness and thickness > 0:
        return thickness

    # Fallback: read attached insulation elements.
    insulation_ids = []
    try:
        ids = InsulationLiningBase.GetInsulationIds(doc, element.Id)
        if ids:
            insulation_ids = list(ids)
    except Exception:
        insulation_ids = []

    best_thickness = None
    for ins_id in insulation_ids:
        ins_element = doc.GetElement(ins_id)
        ins_thickness = get_insulation_thickness_from_element(ins_element, is_pipe)
        if ins_thickness and ins_thickness > 0:
            if best_thickness is None or ins_thickness > best_thickness:
                best_thickness = ins_thickness

    return best_thickness


def get_signed_center_distance_xy(reference_curve, moving_curve):
    ref_mid = reference_curve.Evaluate(0.5, True)
    mov_mid = moving_curve.Evaluate(0.5, True)

    ref_dir = reference_curve.ComputeDerivatives(0.5, True).BasisX
    mov_dir = moving_curve.ComputeDerivatives(0.5, True).BasisX

    ref_dir_xy = unit_xy(ref_dir)
    mov_dir_xy = unit_xy(mov_dir)
    if not ref_dir_xy or not mov_dir_xy:
        return None, None

    cross = abs(ref_dir_xy.X * mov_dir_xy.Y - ref_dir_xy.Y * mov_dir_xy.X)
    if cross > PARALLEL_TOL:
        return None, None

    normal = XYZ(-ref_dir_xy.Y, ref_dir_xy.X, 0.0)
    between = XYZ(mov_mid.X - ref_mid.X, mov_mid.Y - ref_mid.Y, 0.0)
    signed_distance = between.DotProduct(normal)

    if abs(signed_distance) < EPS:
        mov_end = moving_curve.GetEndPoint(1)
        between_end = XYZ(mov_end.X - ref_mid.X, mov_end.Y - ref_mid.Y, 0.0)
        signed_distance = between_end.DotProduct(normal)

    return signed_distance, normal


def pick_element(title_text):
    with forms.WarningBar(title=title_text):
        ref = uidoc.Selection.PickObject(ObjectType.Element, PipeDuctSelectionFilter())
    return doc.GetElement(ref.ElementId)


def show_error_window(message):
    forms.alert(
        msg=message,
        title="Pipe/duct offset",
        warn_icon=True,
        exitscript=False,
    )


def load_settings():
    cfg = script.get_config()
    offset_mm = getattr(cfg, "offset_mm", DEFAULT_OFFSET_MM)
    include_insulation = getattr(cfg, "include_insulation", DEFAULT_INCLUDE_INSULATION)
    return float(offset_mm), bool(include_insulation)


def save_settings(offset_mm, include_insulation):
    cfg = script.get_config()
    cfg.offset_mm = float(offset_mm)
    cfg.include_insulation = bool(include_insulation)
    script.save_config()


class SettingsDialog(Form):
    def __init__(self, current_offset_mm, current_include_insulation):
        self.Text = "Pipe/duct offset settings"
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition = FormStartPosition.CenterScreen
        self.ClientSize = Size(520, 245)
        self.MinimizeBox = False
        self.MaximizeBox = False

        title_label = Label()
        title_label.Text = "Configure how offset is calculated:"
        title_label.Location = Point(16, 12)
        title_label.Size = Size(490, 20)
        self.Controls.Add(title_label)

        offset_label = Label()
        offset_label.Text = "Required 2D edge distance [mm]:"
        offset_label.Location = Point(16, 42)
        offset_label.Size = Size(240, 20)
        self.Controls.Add(offset_label)

        self.offset_text = TextBox()
        self.offset_text.Text = str(int(round(current_offset_mm)))
        self.offset_text.Location = Point(265, 40)
        self.offset_text.Size = Size(100, 24)
        self.Controls.Add(self.offset_text)

        offset_help = Label()
        offset_help.Text = (
            "Distance between element edges in plan view. "
            "Non-negative number; height difference is ignored."
        )
        offset_help.Location = Point(16, 68)
        offset_help.Size = Size(490, 34)
        self.Controls.Add(offset_help)

        self.include_insulation_checkbox = CheckBox()
        self.include_insulation_checkbox.Text = "Include insulation in calculations"
        self.include_insulation_checkbox.Checked = bool(current_include_insulation)
        self.include_insulation_checkbox.Location = Point(16, 110)
        self.include_insulation_checkbox.Size = Size(300, 22)
        self.Controls.Add(self.include_insulation_checkbox)

        insulation_help = Label()
        insulation_help.Text = (
            "If enabled, insulation thickness is added to element size when "
            "computing edge offset."
        )
        insulation_help.Location = Point(16, 136)
        insulation_help.Size = Size(490, 34)
        self.Controls.Add(insulation_help)

        ok_button = Button()
        ok_button.Text = "Save"
        ok_button.Location = Point(330, 190)
        ok_button.Size = Size(85, 28)
        ok_button.Click += self._on_ok_click
        self.Controls.Add(ok_button)

        cancel_button = Button()
        cancel_button.Text = "Cancel"
        cancel_button.Location = Point(421, 190)
        cancel_button.Size = Size(85, 28)
        cancel_button.DialogResult = DialogResult.Cancel
        self.Controls.Add(cancel_button)

        self.AcceptButton = ok_button
        self.CancelButton = cancel_button

        self.result_offset_mm = None
        self.result_include_insulation = None

    def _on_ok_click(self, sender, args):
        try:
            offset_mm = as_length_mm(self.offset_text.Text)
            if offset_mm is None or offset_mm < 0:
                raise ValueError
        except Exception:
            MessageBox.Show(
                "Invalid distance value. Use a non-negative number in mm.",
                "Pipe/duct offset",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        self.result_offset_mm = offset_mm
        self.result_include_insulation = self.include_insulation_checkbox.Checked
        self.DialogResult = DialogResult.OK
        self.Close()


def show_settings_dialog():
    current_offset, current_include_insulation = load_settings()
    dialog = SettingsDialog(current_offset, current_include_insulation)
    if dialog.ShowDialog() != DialogResult.OK:
        return
    save_settings(dialog.result_offset_mm, dialog.result_include_insulation)


def apply_offset(reference, moving, target_edge_ft, include_insulation):
    if reference.Id == moving.Id:
        return "Pick two different elements."

    ref_curve = get_curve(reference)
    mov_curve = get_curve(moving)
    if not ref_curve or not mov_curve:
        return "Element {}: only curve-based pipes/ducts are supported.".format(
            moving.Id.IntegerValue
        )

    ref_reach = get_plan_reach(reference, include_insulation)
    mov_reach = get_plan_reach(moving, include_insulation)
    if ref_reach is None or mov_reach is None:
        return "Element {}: could not read element sizes for 2D distance calculation.".format(
            moving.Id.IntegerValue
        )

    signed_center, normal = get_signed_center_distance_xy(ref_curve, mov_curve)
    if signed_center is None or normal is None:
        return "Element {}: elements must be parallel in plan view.".format(
            moving.Id.IntegerValue
        )

    current_center = abs(signed_center)
    target_center = target_edge_ft + ref_reach + mov_reach
    delta = target_center - current_center

    if abs(delta) <= 1e-6:
        return None

    side = 1.0 if signed_center >= 0 else -1.0
    move_vector = XYZ(normal.X * side * delta, normal.Y * side * delta, 0.0)

    tx = Transaction(doc, "Pipe/duct offset - PYLAB")
    try:
        tx.Start()
        ElementTransformUtils.MoveElement(doc, moving.Id, move_vector)
        tx.Commit()
    except Exception as ex:
        if tx.HasStarted():
            tx.RollBack()
        return "Element {}: move failed: {}".format(moving.Id.IntegerValue, ex)

    return None


def run_loop():
    offset_mm, include_insulation = load_settings()
    target_edge_ft = offset_mm / FT_TO_MM

    while True:
        try:
            reference = pick_element("Pick reference pipe/duct (ESC to finish)")
        except Exception:
            break

        try:
            moving = pick_element("Pick pipe/duct to move from reference (ESC to finish)")
        except Exception:
            break

        error = apply_offset(reference, moving, target_edge_ft, include_insulation)
        if error:
            show_error_window(error)


def main():
    if get_shiftclick_state():
        show_settings_dialog()
        return

    run_loop()


if __name__ == "__main__":
    main()
