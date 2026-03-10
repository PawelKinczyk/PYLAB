"""Create bypasses for selected pipes and ducts around one obstacle.

Assumptions:
- Runs inside pyRevit with IronPython-compatible Python and the Revit API.
- Supports straight, near-horizontal pipe and duct curves only.
- Processes one picked obstacle from the active model or a linked model.
- Keeps the requested 30/45/90 angle exact. If Revit cannot create fittings for
  that geometry and type, the element is rolled back and reported as failed.
"""

import json
import math
import os
import clr

from Autodesk.Revit import DB
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    FailureProcessingResult,
    FailureSeverity,
    GeometryInstance,
    IFailuresPreprocessor,
    InsulationLiningBase,
    Line,
    Mesh,
    Options,
    RevitLinkInstance,
    Solid,
    SubTransaction,
    Transaction,
    TransactionGroup,
    Transform,
    UnitUtils,
    XYZ,
)
from Autodesk.Revit.DB.Mechanical import Duct, MechanicalUtils
from Autodesk.Revit.DB.Plumbing import Pipe, PlumbingUtils
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
    ComboBox,
    ComboBoxStyle,
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
SPEC_TYPE_ID = getattr(DB, "SpecTypeId", None)
UNIT_TYPE = getattr(DB, "UnitType", None)

EPS = 1e-9
GEOMETRY_EPS = 1e-6
HORIZONTAL_TOL = 0.01
DEFAULT_DIRECTION = "Above"
DEFAULT_ANGLE = "45"
DEFAULT_CLEARANCE = 50.0
DEFAULT_INCLUDE_INSULATION = True
TITLE = "Bypass"
MIN_SEGMENT_LENGTH_FACTOR = 1.0
SEGMENT_LENGTH_FACTOR_STEP = 0.25
MAX_SEGMENT_LENGTH_FACTOR = 4.0
SPACING_RETRY_ERROR_MARKERS = (
    "additional fitting spacing",
    "causing the connections to be invalid",
    "opposite direction",
    "not close enough for intersection",
    "not close enough together",
)
INSUFFICIENT_SECTION_ERROR_MARKERS = (
    "installation section is too short",
    "bypass legs are too short",
)
TOP_STRAIGHT_CONNECTION_MARKERS = (
    "rise-top",
    "top-drop",
)
COMMIT_RETRY_WARNING_MARKERS = (
    "opposite direction causing the connections to be invalid",
    "modified to be in the opposite direction",
)


class BypassFailuresPreprocessor(IFailuresPreprocessor):
    def __init__(self, rollback_warning_markers=None):
        self.rollback_warning_markers = [
            (marker or "").lower() for marker in (rollback_warning_markers or [])
        ]
        self.warning_messages = []
        self.retryable_warning_messages = []
        self.rollback_requested = False

    def PreprocessFailures(self, failures_accessor):
        try:
            failure_messages = list(failures_accessor.GetFailureMessages())
        except Exception:
            failure_messages = []

        for failure_message in failure_messages:
            try:
                description = failure_message.GetDescriptionText() or ""
            except Exception:
                description = ""

            if description:
                self.warning_messages.append(description)
                normalized_description = description.lower()
                if any(
                    marker in normalized_description
                    for marker in self.rollback_warning_markers
                ):
                    self.retryable_warning_messages.append(description)
                    self.rollback_requested = True

            try:
                if failure_message.GetSeverity() == FailureSeverity.Warning:
                    failures_accessor.DeleteWarning(failure_message)
            except Exception:
                continue

        if self.rollback_requested:
            return FailureProcessingResult.ProceedWithRollBack
        return FailureProcessingResult.Continue


class MepCurveSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        category_id = element.Category.Id.IntegerValue
        return category_id in (
            int(BuiltInCategory.OST_PipeCurves),
            int(BuiltInCategory.OST_DuctCurves),
        )

    def AllowReference(self, reference, point):
        return True


class HostObstacleSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not element or isinstance(element, RevitLinkInstance):
            return False
        return bool(element.Category)

    def AllowReference(self, reference, point):
        return True


class LinkedObstacleSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        return isinstance(element, RevitLinkInstance)

    def AllowReference(self, reference, point):
        return True


class ObstacleInfo(object):
    def __init__(self, element, transform, label_text):
        self.element = element
        self.transform = transform or Transform.Identity
        self.label_text = label_text


class BypassOptions(object):
    def __init__(self, direction, angle_label, clearance_value, include_insulation):
        self.direction = direction
        self.angle_label = angle_label
        self.clearance_value = clearance_value
        self.include_insulation = include_insulation

    @property
    def angle_degrees(self):
        return float(self.angle_label)


class BypassResult(object):
    def __init__(self, source_label, status, message, warning_message):
        self.source_label = source_label
        self.status = status
        self.message = message
        self.warning_message = warning_message or ""


class BypassCreationError(Exception):
    def __init__(self, message, debug_data):
        Exception.__init__(self, message)
        self.debug_data = debug_data or {}


class BypassOptionsDialog(Form):
    def __init__(self, current_options, unit_label):
        self.Text = TITLE
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.StartPosition = FormStartPosition.CenterScreen
        self.MinimizeBox = False
        self.MaximizeBox = False
        self.SuspendLayout()

        left_margin = 16
        top_margin = 14
        form_width = 590
        button_width = 85
        button_gap = 8
        input_width = 140
        input_left = 255
        wrap_width = form_width - (left_margin * 2)
        current_y = top_margin

        title_label = Label()
        title_label.Text = "Configure how the bypass should be created:"
        title_label.AutoSize = True
        title_label.MaximumSize = Size(wrap_width, 0)
        title_label.Location = Point(left_margin, current_y)
        self.Controls.Add(title_label)
        current_y = title_label.Bottom + 18

        direction_label = Label()
        direction_label.Text = "Bypass direction:"
        direction_label.AutoSize = True
        direction_label.Location = Point(left_margin, current_y + 4)
        self.Controls.Add(direction_label)

        self.direction_combo = ComboBox()
        self.direction_combo.DropDownStyle = ComboBoxStyle.DropDownList
        self.direction_combo.Location = Point(input_left, current_y)
        self.direction_combo.Size = Size(input_width, 24)
        self.direction_combo.Items.Add("Above")
        self.direction_combo.Items.Add("Below")
        self.direction_combo.SelectedItem = current_options.direction
        self.Controls.Add(self.direction_combo)
        current_y += max(direction_label.Height, self.direction_combo.Height) + 14

        angle_label = Label()
        angle_label.Text = "Bypass angle:"
        angle_label.AutoSize = True
        angle_label.Location = Point(left_margin, current_y + 4)
        self.Controls.Add(angle_label)

        self.angle_combo = ComboBox()
        self.angle_combo.DropDownStyle = ComboBoxStyle.DropDownList
        self.angle_combo.Location = Point(input_left, current_y)
        self.angle_combo.Size = Size(input_width, 24)
        self.angle_combo.Items.Add("30")
        self.angle_combo.Items.Add("45")
        self.angle_combo.Items.Add("90")
        self.angle_combo.SelectedItem = current_options.angle_label
        self.Controls.Add(self.angle_combo)
        current_y += max(angle_label.Height, self.angle_combo.Height) + 14

        clearance_label = Label()
        clearance_label.Text = "Clearance [{}]:".format(unit_label)
        clearance_label.AutoSize = True
        clearance_label.Location = Point(left_margin, current_y + 4)
        self.Controls.Add(clearance_label)

        self.clearance_text = TextBox()
        self.clearance_text.Text = str(current_options.clearance_value)
        self.clearance_text.Location = Point(input_left, current_y)
        self.clearance_text.Size = Size(input_width, 24)
        self.Controls.Add(self.clearance_text)
        current_y += max(clearance_label.Height, self.clearance_text.Height) + 8

        clearance_help = Label()
        clearance_help.Text = "Use a non-negative number."
        clearance_help.AutoSize = True
        clearance_help.MaximumSize = Size(wrap_width, 0)
        clearance_help.Location = Point(left_margin, current_y)
        self.Controls.Add(clearance_help)
        current_y = clearance_help.Bottom + 10

        self.include_insulation_checkbox = CheckBox()
        self.include_insulation_checkbox.Text = "Include insulation in clearance calculations"
        self.include_insulation_checkbox.Checked = bool(current_options.include_insulation)
        self.include_insulation_checkbox.AutoSize = True
        self.include_insulation_checkbox.MaximumSize = Size(wrap_width, 0)
        self.include_insulation_checkbox.Location = Point(left_margin, current_y)
        self.Controls.Add(self.include_insulation_checkbox)
        current_y = self.include_insulation_checkbox.Bottom + 20

        cancel_x = form_width - left_margin - button_width
        ok_x = cancel_x - button_gap - button_width

        ok_button = Button()
        ok_button.Text = "Run"
        ok_button.Location = Point(ok_x, current_y)
        ok_button.Size = Size(85, 28)
        ok_button.Click += self._on_ok_click
        self.Controls.Add(ok_button)

        cancel_button = Button()
        cancel_button.Text = "Cancel"
        cancel_button.Location = Point(cancel_x, current_y)
        cancel_button.Size = Size(85, 28)
        cancel_button.DialogResult = DialogResult.Cancel
        self.Controls.Add(cancel_button)

        self.ClientSize = Size(form_width, cancel_button.Bottom + 16)
        self.AcceptButton = ok_button
        self.CancelButton = cancel_button
        self.result = None
        self.ResumeLayout(True)

    def _on_ok_click(self, sender, args):
        try:
            clearance_value = parse_numeric_text(self.clearance_text.Text)
            if clearance_value is None or clearance_value < 0:
                raise ValueError
        except Exception:
            MessageBox.Show(
                "Invalid clearance. Use a non-negative numeric value.",
                TITLE,
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        direction_value = str(self.direction_combo.SelectedItem or DEFAULT_DIRECTION)
        angle_value = str(self.angle_combo.SelectedItem or DEFAULT_ANGLE)
        include_insulation = bool(self.include_insulation_checkbox.Checked)

        self.result = BypassOptions(
            direction_value,
            angle_value,
            clearance_value,
            include_insulation,
        )
        self.DialogResult = DialogResult.OK
        self.Close()


def parse_numeric_text(text_value):
    if text_value is None:
        return None
    normalized = str(text_value).strip().replace(",", ".")
    if not normalized:
        return None
    return float(normalized)


def load_settings():
    cfg = script.get_config()
    direction = getattr(cfg, "direction", DEFAULT_DIRECTION)
    angle_label = str(getattr(cfg, "angle", DEFAULT_ANGLE))
    clearance_value = getattr(cfg, "clearance", DEFAULT_CLEARANCE)
    include_insulation = getattr(cfg, "include_insulation", DEFAULT_INCLUDE_INSULATION)

    try:
        clearance_value = float(str(clearance_value).replace(",", "."))
    except Exception:
        clearance_value = DEFAULT_CLEARANCE

    if direction not in ("Above", "Below"):
        direction = DEFAULT_DIRECTION
    if angle_label not in ("30", "45", "90"):
        angle_label = DEFAULT_ANGLE
    if clearance_value < 0:
        clearance_value = DEFAULT_CLEARANCE

    return BypassOptions(direction, angle_label, clearance_value, include_insulation)


def save_settings(options):
    cfg = script.get_config()
    cfg.direction = options.direction
    cfg.angle = options.angle_label
    cfg.clearance = float(options.clearance_value)
    cfg.include_insulation = bool(options.include_insulation)
    script.save_config()


def convert_length_to_internal(document, value):
    units = document.GetUnits()

    if SPEC_TYPE_ID is not None:
        try:
            unit_type_id = units.GetFormatOptions(SPEC_TYPE_ID.Length).GetUnitTypeId()
            return UnitUtils.ConvertToInternalUnits(value, unit_type_id)
        except Exception:
            pass

    if UNIT_TYPE is not None:
        try:
            display_units = units.GetFormatOptions(UNIT_TYPE.UT_Length).DisplayUnits
            return UnitUtils.ConvertToInternalUnits(value, display_units)
        except Exception:
            pass

    raise Exception("Could not determine project length units.")


def convert_length_from_internal(document, value):
    units = document.GetUnits()

    if SPEC_TYPE_ID is not None:
        try:
            unit_type_id = units.GetFormatOptions(SPEC_TYPE_ID.Length).GetUnitTypeId()
            return UnitUtils.ConvertFromInternalUnits(value, unit_type_id)
        except Exception:
            pass

    if UNIT_TYPE is not None:
        try:
            display_units = units.GetFormatOptions(UNIT_TYPE.UT_Length).DisplayUnits
            return UnitUtils.ConvertFromInternalUnits(value, display_units)
        except Exception:
            pass

    raise Exception("Could not determine project length units.")


def format_length_unit_name(unit_value):
    if unit_value is None:
        return ""

    raw_value = getattr(unit_value, "TypeId", None) or str(unit_value)
    if not raw_value:
        return ""

    normalized = raw_value.strip()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    if "-" in normalized:
        normalized = normalized.split("-", 1)[0]
    if normalized.startswith("DUT_"):
        normalized = normalized[4:]

    normalized = normalized.replace("_", " ").strip().lower()
    unit_name_overrides = {
        "millimeter": "millimeters",
        "centimeter": "centimeters",
        "meter": "meters",
        "decimeter": "decimeters",
        "foot": "feet",
        "inch": "inches",
    }
    return unit_name_overrides.get(normalized, normalized)


def get_project_length_unit_label(document):
    units = document.GetUnits()

    if SPEC_TYPE_ID is not None:
        try:
            unit_type_id = units.GetFormatOptions(SPEC_TYPE_ID.Length).GetUnitTypeId()
            unit_name = format_length_unit_name(unit_type_id)
            if unit_name:
                return unit_name
        except Exception:
            pass

    if UNIT_TYPE is not None:
        try:
            display_units = units.GetFormatOptions(UNIT_TYPE.UT_Length).DisplayUnits
            unit_name = format_length_unit_name(display_units)
            if unit_name:
                return unit_name
        except Exception:
            pass

    return "project units"


def show_options_dialog():
    unit_label = get_project_length_unit_label(doc)
    current_options = load_settings()
    dialog = BypassOptionsDialog(current_options, unit_label)
    if dialog.ShowDialog() != DialogResult.OK:
        return None, None
    save_settings(dialog.result)
    return dialog.result, convert_length_to_internal(doc, dialog.result.clearance_value)


def is_pipe_curve(element):
    return (
        element
        and element.Category
        and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_PipeCurves)
    )


def is_duct_curve(element):
    return (
        element
        and element.Category
        and element.Category.Id.IntegerValue == int(BuiltInCategory.OST_DuctCurves)
    )


def get_element_label(element):
    if element is None:
        return "Element"
    try:
        return "{} {}".format(element.Category.Name, element.Id.IntegerValue)
    except Exception:
        try:
            return "Element {}".format(element.Id.IntegerValue)
        except Exception:
            return "Element [invalid]"


def get_double_param(element, built_in_parameter):
    param = element.get_Parameter(built_in_parameter)
    if param is None:
        return None
    try:
        return param.AsDouble()
    except Exception:
        return None


def get_double_param_by_name(element, built_in_parameter_name):
    try:
        built_in_parameter = getattr(BuiltInParameter, built_in_parameter_name)
    except Exception:
        return None
    return get_double_param(element, built_in_parameter)


def get_element_id_param(element, built_in_parameter):
    param = element.get_Parameter(built_in_parameter)
    if param is None:
        return None
    try:
        value = param.AsElementId()
        if value and value.IntegerValue != -1:
            return value
    except Exception:
        return None
    return None


def get_curve_line(element):
    location = getattr(element, "Location", None)
    if location is None:
        return None
    curve = getattr(location, "Curve", None)
    if curve is None or not isinstance(curve, Line):
        return None
    return curve


def unit_xy(vector):
    planar = XYZ(vector.X, vector.Y, 0.0)
    length = planar.GetLength()
    if length < EPS:
        return None
    return XYZ(planar.X / length, planar.Y / length, 0.0)


def get_curve_plan_factor(curve_line):
    direction = curve_line.Direction
    return XYZ(direction.X, direction.Y, 0.0).GetLength()


def get_min_segment_length():
    try:
        short_tol = doc.Application.ShortCurveTolerance
    except Exception:
        short_tol = 0.01
    return max(short_tol * 2.0, 0.1)


def xyz_to_data(point):
    if point is None:
        return None
    return {
        "x": point.X,
        "y": point.Y,
        "z": point.Z,
    }


def data_to_xyz(point_data):
    if not point_data:
        return None
    return XYZ(point_data["x"], point_data["y"], point_data["z"])


def curve_to_data(curve_line):
    if curve_line is None:
        return None
    try:
        return {
            "start": xyz_to_data(curve_line.GetEndPoint(0)),
            "end": xyz_to_data(curve_line.GetEndPoint(1)),
            "length": curve_line.Length,
        }
    except Exception:
        return None


def get_debug_folder_path():
    appdata_path = os.environ.get("APPDATA")
    if not appdata_path:
        return None
    return os.path.join(appdata_path, "pyRevit", "PYLAB", "Bypass")


def get_debug_file_path():
    folder_path = get_debug_folder_path()
    if not folder_path:
        return None
    return os.path.join(folder_path, "last_run_debug.json")


def ensure_folder(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def write_debug_cache(payload):
    debug_file_path = get_debug_file_path()
    if not debug_file_path:
        return None

    ensure_folder(os.path.dirname(debug_file_path))
    with open(debug_file_path, "w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=False)
    return debug_file_path


def get_connector_manager(element):
    manager = getattr(element, "ConnectorManager", None)
    if manager is not None:
        return manager

    mep_model = getattr(element, "MEPModel", None)
    if mep_model is not None:
        return getattr(mep_model, "ConnectorManager", None)

    return None


def get_connectors(element):
    manager = get_connector_manager(element)
    if manager is None:
        return []
    connectors = []
    try:
        for connector in manager.Connectors:
            connectors.append(connector)
    except Exception:
        pass
    return connectors


def get_nearest_connector(element, point, require_open):
    best_connector = None
    best_distance = None

    for connector in get_connectors(element):
        try:
            if require_open and connector.IsConnected:
                continue
            distance = connector.Origin.DistanceTo(point)
            if best_distance is None or distance < best_distance:
                best_connector = connector
                best_distance = distance
        except Exception:
            continue

    return best_connector


def connect_with_elbow(element_a, point_a, element_b, point_b, connection_label=None):
    connector_a = get_nearest_connector(element_a, point_a, True)
    connector_b = get_nearest_connector(element_b, point_b, True)
    if connector_a is None or connector_b is None:
        if connection_label:
            raise Exception(
                "Could not find open connectors for elbow connection [{}].".format(
                    connection_label
                )
            )
        raise Exception("Could not find open connectors for elbow connection.")
    try:
        doc.Create.NewElbowFitting(connector_a, connector_b)
    except Exception as elbow_error:
        if connection_label:
            raise Exception(
                "Failed to insert elbow [{}]: {}".format(connection_label, elbow_error)
            )
        raise Exception("Failed to insert elbow: {}".format(elbow_error))


def get_insulation_thickness_from_element(insulation_element, is_pipe):
    if insulation_element is None:
        return None

    if is_pipe:
        thickness = get_double_param(
            insulation_element, BuiltInParameter.RBS_PIPE_INSULATION_THICKNESS
        )
        if thickness and thickness > 0:
            return thickness
    else:
        thickness = get_double_param(
            insulation_element, BuiltInParameter.RBS_DUCT_INSULATION_THICKNESS
        )
        if thickness and thickness > 0:
            return thickness

    generic = get_double_param_by_name(insulation_element, "RBS_INSULATION_THICKNESS")
    if generic and generic > 0:
        return generic

    for param_name in ("Insulation Thickness", "Thickness"):
        try:
            param = insulation_element.LookupParameter(param_name)
            if param is None:
                continue
            thickness = param.AsDouble()
            if thickness and thickness > 0:
                return thickness
        except Exception:
            continue

    return None


def get_lining_thickness_from_element(lining_element):
    if lining_element is None:
        return None

    thickness = get_double_param_by_name(lining_element, "RBS_DUCT_LINING_THICKNESS")
    if thickness and thickness > 0:
        return thickness

    generic = get_double_param_by_name(lining_element, "RBS_LINING_THICKNESS")
    if generic and generic > 0:
        return generic

    for param_name in ("Lining Thickness", "Thickness"):
        try:
            param = lining_element.LookupParameter(param_name)
            if param is None:
                continue
            thickness = param.AsDouble()
            if thickness and thickness > 0:
                return thickness
        except Exception:
            continue

    return None


def get_attached_insulation_thickness(element, is_pipe):
    thickness = None

    try:
        insulation_ids = list(InsulationLiningBase.GetInsulationIds(doc, element.Id))
    except Exception:
        insulation_ids = []

    for insulation_id in insulation_ids:
        insulation_element = doc.GetElement(insulation_id)
        current_thickness = get_insulation_thickness_from_element(insulation_element, is_pipe)
        if current_thickness and current_thickness > 0:
            if thickness is None or current_thickness > thickness:
                thickness = current_thickness

    return thickness


def get_curve_profile(element, include_insulation):
    if is_pipe_curve(element):
        diameter = get_double_param_by_name(element, "RBS_PIPE_OUTER_DIAMETER")
        if diameter is None:
            diameter = get_double_param_by_name(element, "RBS_CURVE_OUTER_DIAMETER")
        if diameter is None:
            diameter = get_double_param(element, BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        if diameter is None:
            diameter = get_double_param(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
        if diameter is None or diameter <= 0:
            raise Exception("Could not read pipe diameter.")

        insulation_thickness = 0.0
        if include_insulation:
            insulation_thickness = get_attached_insulation_thickness(element, True) or 0.0

        half_size = (diameter * 0.5) + insulation_thickness
        return {
            "shape": "round",
            "half_height": half_size,
            "half_width": half_size,
            "outer_diameter": half_size * 2.0,
            "outer_width": half_size * 2.0,
            "outer_height": half_size * 2.0,
        }

    diameter = get_double_param_by_name(element, "RBS_CURVE_OUTER_DIAMETER")
    if diameter is None:
        diameter = get_double_param(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)

    insulation_thickness = 0.0
    if include_insulation:
        insulation_thickness = get_attached_insulation_thickness(element, False) or 0.0

    if diameter and diameter > 0:
        half_size = (diameter * 0.5) + insulation_thickness
        return {
            "shape": "round",
            "half_height": half_size,
            "half_width": half_size,
            "outer_diameter": half_size * 2.0,
            "outer_width": half_size * 2.0,
            "outer_height": half_size * 2.0,
        }

    width = get_double_param(element, BuiltInParameter.RBS_CURVE_WIDTH_PARAM)
    height = get_double_param(element, BuiltInParameter.RBS_CURVE_HEIGHT_PARAM)
    if width is None or height is None or width <= 0 or height <= 0:
        raise Exception("Could not read duct size.")

    return {
        "shape": "rectangular",
        "half_height": (height * 0.5) + insulation_thickness,
        "half_width": (width * 0.5) + insulation_thickness,
        "outer_diameter": None,
        "outer_width": width + (insulation_thickness * 2.0),
        "outer_height": height + (insulation_thickness * 2.0),
    }


def get_curve_covering_specs(element):
    specs = []

    if is_pipe_curve(element):
        try:
            insulation_ids = list(InsulationLiningBase.GetInsulationIds(doc, element.Id))
        except Exception:
            insulation_ids = []

        for insulation_id in insulation_ids:
            insulation_element = doc.GetElement(insulation_id)
            thickness = get_insulation_thickness_from_element(insulation_element, True)
            if thickness and thickness > 0:
                specs.append(
                    {
                        "kind": "pipe_insulation",
                        "type_id": insulation_element.GetTypeId(),
                        "thickness": thickness,
                    }
                )
        return specs

    try:
        insulation_ids = list(InsulationLiningBase.GetInsulationIds(doc, element.Id))
    except Exception:
        insulation_ids = []

    for insulation_id in insulation_ids:
        insulation_element = doc.GetElement(insulation_id)
        thickness = get_insulation_thickness_from_element(insulation_element, False)
        if thickness and thickness > 0:
            specs.append(
                {
                    "kind": "duct_insulation",
                    "type_id": insulation_element.GetTypeId(),
                    "thickness": thickness,
                }
            )

    get_lining_ids = getattr(InsulationLiningBase, "GetLiningIds", None)
    if get_lining_ids is None:
        return specs

    try:
        lining_ids = list(get_lining_ids(doc, element.Id))
    except Exception:
        lining_ids = []

    for lining_id in lining_ids:
        lining_element = doc.GetElement(lining_id)
        thickness = get_lining_thickness_from_element(lining_element)
        if thickness and thickness > 0:
            specs.append(
                {
                    "kind": "duct_lining",
                    "type_id": lining_element.GetTypeId(),
                    "thickness": thickness,
                }
            )

    return specs


def get_required_straight_length(profile):
    short_curve_min = get_min_segment_length()
    if profile.get("shape") == "round":
        size_based_length = profile.get("outer_diameter") or max(
            profile.get("outer_width", 0.0),
            profile.get("outer_height", 0.0),
        )
    else:
        size_based_length = max(
            profile.get("outer_width", 0.0),
            profile.get("outer_height", 0.0),
        )
    return max(short_curve_min, size_based_length)


def get_segment_length_factors():
    factors = []
    current_factor = MIN_SEGMENT_LENGTH_FACTOR
    while current_factor <= MAX_SEGMENT_LENGTH_FACTOR + EPS:
        factors.append(round(current_factor, 2))
        current_factor += SEGMENT_LENGTH_FACTOR_STEP
    return factors


def get_required_bypass_segment_length(required_straight_length, segment_length_factor):
    try:
        factor = float(segment_length_factor)
    except Exception:
        factor = MIN_SEGMENT_LENGTH_FACTOR
    factor = max(MIN_SEGMENT_LENGTH_FACTOR, factor)
    return required_straight_length * factor, factor


def is_spacing_retryable_error_message(message):
    text = (message or "").lower()
    if not text:
        return False
    for marker in SPACING_RETRY_ERROR_MARKERS:
        if marker in text:
            return True
    return False


def is_insufficient_section_error_message(message):
    text = (message or "").lower()
    if not text:
        return False
    for marker in INSUFFICIENT_SECTION_ERROR_MARKERS:
        if marker in text:
            return True
    return False


def is_top_straight_retryable_error_message(message):
    text = (message or "").lower()
    if not text or not is_spacing_retryable_error_message(text):
        return False
    for marker in TOP_STRAIGHT_CONNECTION_MARKERS:
        if marker in text:
            return True
    return False


def get_type_display_name(element):
    try:
        element_type = doc.GetElement(element.GetTypeId())
    except Exception:
        element_type = None

    if element_type is None:
        return "Unknown type"

    family_name = ""
    type_name = ""

    try:
        family_name = getattr(element_type, "FamilyName", "") or ""
    except Exception:
        family_name = ""

    try:
        type_name = element_type.Name or ""
    except Exception:
        type_name = ""

    if not type_name:
        for param_name in ("Type Name", "Type"):
            try:
                param = element_type.LookupParameter(param_name)
                if param is None:
                    continue
                type_name = param.AsString() or param.AsValueString() or ""
                if type_name:
                    break
            except Exception:
                continue

    if family_name and type_name:
        return "{} : {}".format(family_name, type_name)
    if type_name:
        return type_name
    if family_name:
        return family_name
    return "Type {}".format(element_type.Id.IntegerValue)


def format_project_length_value(length_internal):
    length_project = convert_length_from_internal(doc, length_internal)
    unit_label = get_project_length_unit_label(doc)
    return "{:.2f} {}".format(length_project, unit_label)


def get_profile_size_label(profile):
    if profile.get("shape") == "round":
        return "diameter {}".format(
            format_project_length_value(profile.get("outer_diameter", 0.0))
        )

    return "{} x {}".format(
        format_project_length_value(profile.get("outer_width", 0.0)),
        format_project_length_value(profile.get("outer_height", 0.0)),
    )


def get_size_label_for_element(element, include_insulation):
    try:
        return get_profile_size_label(get_curve_profile(element, include_insulation))
    except Exception:
        return "unknown size"


def apply_coverings(target_elements, covering_specs):
    warnings = []

    for target_element in target_elements:
        for spec in covering_specs:
            try:
                if spec["kind"] == "pipe_insulation":
                    DB.Plumbing.PipeInsulation.Create(
                        doc,
                        target_element.Id,
                        spec["type_id"],
                        spec["thickness"],
                    )
                elif spec["kind"] == "duct_insulation":
                    DB.Mechanical.DuctInsulation.Create(
                        doc,
                        target_element.Id,
                        spec["type_id"],
                        spec["thickness"],
                    )
                elif spec["kind"] == "duct_lining":
                    DB.Mechanical.DuctLining.Create(
                        doc,
                        target_element.Id,
                        spec["type_id"],
                        spec["thickness"],
                    )
            except Exception as covering_error:
                warnings.append(str(covering_error))

    return warnings


def get_reference_level_id(element):
    try:
        reference_level = element.ReferenceLevel
        if reference_level is not None:
            return reference_level.Id
    except Exception:
        pass

    for parameter_name in ("RBS_START_LEVEL_PARAM", "FAMILY_LEVEL_PARAM"):
        try:
            built_in_parameter = getattr(BuiltInParameter, parameter_name)
        except Exception:
            continue
        level_id = get_element_id_param(element, built_in_parameter)
        if level_id is not None:
            return level_id

    raise Exception("Could not resolve reference level.")


def get_curve_system_type_id(element):
    if is_pipe_curve(element):
        parameter_name = "RBS_PIPING_SYSTEM_TYPE_PARAM"
    else:
        parameter_name = "RBS_DUCT_SYSTEM_TYPE_PARAM"

    try:
        built_in_parameter = getattr(BuiltInParameter, parameter_name)
        system_type_id = get_element_id_param(element, built_in_parameter)
        if system_type_id is not None:
            return system_type_id
    except Exception:
        pass

    try:
        system = element.MEPSystem
        if system is not None:
            system_type_id = system.GetTypeId()
            if system_type_id and system_type_id.IntegerValue != -1:
                return system_type_id
    except Exception:
        pass

    raise Exception("Could not resolve system type.")


def copy_curve_size(source_element, target_element):
    if is_pipe_curve(source_element):
        source_diameter = get_double_param(source_element, BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
        if source_diameter is None:
            source_diameter = get_double_param(source_element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
        if source_diameter is None:
            return

        for built_in_parameter in (
            BuiltInParameter.RBS_PIPE_DIAMETER_PARAM,
            BuiltInParameter.RBS_CURVE_DIAMETER_PARAM,
        ):
            try:
                param = target_element.get_Parameter(built_in_parameter)
                if param is not None and not param.IsReadOnly:
                    param.Set(source_diameter)
                    return
            except Exception:
                continue
        return

    source_diameter = get_double_param(source_element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
    if source_diameter and source_diameter > 0:
        try:
            param = target_element.get_Parameter(BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
            if param is not None and not param.IsReadOnly:
                param.Set(source_diameter)
            return
        except Exception:
            pass

    source_width = get_double_param(source_element, BuiltInParameter.RBS_CURVE_WIDTH_PARAM)
    source_height = get_double_param(source_element, BuiltInParameter.RBS_CURVE_HEIGHT_PARAM)

    if source_width and source_width > 0:
        try:
            width_param = target_element.get_Parameter(BuiltInParameter.RBS_CURVE_WIDTH_PARAM)
            if width_param is not None and not width_param.IsReadOnly:
                width_param.Set(source_width)
        except Exception:
            pass

    if source_height and source_height > 0:
        try:
            height_param = target_element.get_Parameter(BuiltInParameter.RBS_CURVE_HEIGHT_PARAM)
            if height_param is not None and not height_param.IsReadOnly:
                height_param.Set(source_height)
        except Exception:
            pass


def create_curve_like(source_element, start_point, end_point):
    system_type_id = get_curve_system_type_id(source_element)
    curve_type_id = source_element.GetTypeId()
    level_id = get_reference_level_id(source_element)

    if is_pipe_curve(source_element):
        new_curve = Pipe.Create(
            doc,
            system_type_id,
            curve_type_id,
            level_id,
            start_point,
            end_point,
        )
    else:
        new_curve = Duct.Create(
            doc,
            system_type_id,
            curve_type_id,
            level_id,
            start_point,
            end_point,
        )

    copy_curve_size(source_element, new_curve)
    return new_curve


def get_segment_endpoints(base_start, base_end, is_forward):
    if is_forward:
        return base_start, base_end
    return base_end, base_start


def break_curve_at_point(element, point):
    if is_pipe_curve(element):
        return PlumbingUtils.BreakCurve(doc, element.Id, point)
    return MechanicalUtils.BreakCurve(doc, element.Id, point)


def make_world_point(origin, axis_x, distance_along, absolute_z):
    return XYZ(
        origin.X + (axis_x.X * distance_along),
        origin.Y + (axis_x.Y * distance_along),
        absolute_z,
    )


def get_source_point_at_plan_distance(curve_line, plan_distance):
    plan_factor = get_curve_plan_factor(curve_line)
    if plan_factor <= EPS:
        raise Exception("Could not resolve source curve plan direction.")

    line_distance = plan_distance / plan_factor
    if line_distance < -EPS or line_distance > curve_line.Length + EPS:
        raise Exception("Calculated split point is outside the selected curve.")

    normalized_parameter = line_distance / curve_line.Length
    normalized_parameter = max(0.0, min(1.0, normalized_parameter))
    return curve_line.Evaluate(normalized_parameter, True)


def is_point_on_curve(curve_line, point, tolerance):
    if curve_line is None or point is None:
        return False

    try:
        result = curve_line.Project(point)
        if result is None:
            return False
        projected_point = result.XYZPoint
        return projected_point.DistanceTo(point) <= tolerance
    except Exception:
        return False


def get_curve_from_element(element):
    if element is None:
        return None
    return get_curve_line(element)


def get_segment_containing_point(element_a, element_b, point, tolerance):
    curve_a = get_curve_from_element(element_a)
    curve_b = get_curve_from_element(element_b)

    if is_point_on_curve(curve_a, point, tolerance):
        return element_a, element_b
    if is_point_on_curve(curve_b, point, tolerance):
        return element_b, element_a

    raise Exception("Could not identify the segment that contains the split point.")


def get_bbox_corners(bbox, transform):
    if bbox is None:
        return []

    current_transform = transform or Transform.Identity
    min_point = bbox.Min
    max_point = bbox.Max
    corners = []
    for x_value in (min_point.X, max_point.X):
        for y_value in (min_point.Y, max_point.Y):
            for z_value in (min_point.Z, max_point.Z):
                corners.append(current_transform.OfPoint(XYZ(x_value, y_value, z_value)))
    return corners


def collect_geometry_points(geometry_element, current_transform, points):
    if geometry_element is None:
        return

    for geometry_object in geometry_element:
        if isinstance(geometry_object, Solid):
            if geometry_object.Volume <= GEOMETRY_EPS:
                continue
            try:
                for face in geometry_object.Faces:
                    mesh = face.Triangulate()
                    for index in range(mesh.NumVertices):
                        points.append(current_transform.OfPoint(mesh.get_Vertex(index)))
            except Exception:
                continue
        elif isinstance(geometry_object, Mesh):
            try:
                for index in range(geometry_object.NumVertices):
                    points.append(current_transform.OfPoint(geometry_object.get_Vertex(index)))
            except Exception:
                continue
        elif isinstance(geometry_object, GeometryInstance):
            instance_transform = current_transform.Multiply(geometry_object.Transform)
            try:
                instance_geometry = geometry_object.GetInstanceGeometry()
            except Exception:
                instance_geometry = geometry_object.SymbolGeometry
            collect_geometry_points(instance_geometry, instance_transform, points)
        else:
            try:
                tessellated = geometry_object.Tessellate()
                for tess_point in tessellated:
                    points.append(current_transform.OfPoint(tess_point))
            except Exception:
                continue


def get_obstacle_points(obstacle_info):
    points = []
    geometry_options = Options()
    geometry_options.IncludeNonVisibleObjects = True
    geometry_options.ComputeReferences = False
    geometry_options.DetailLevel = DB.ViewDetailLevel.Fine

    try:
        geometry = obstacle_info.element.get_Geometry(geometry_options)
    except Exception:
        geometry = None

    if geometry is not None:
        collect_geometry_points(geometry, obstacle_info.transform, points)

    if points:
        return points

    try:
        bbox = obstacle_info.element.get_BoundingBox(None)
    except Exception:
        bbox = None

    return get_bbox_corners(bbox, obstacle_info.transform)


def get_obstacle_expansion(element, include_insulation):
    if not include_insulation:
        return 0.0

    if is_pipe_curve(element):
        return get_attached_insulation_thickness(element, True) or 0.0

    if is_duct_curve(element):
        return get_attached_insulation_thickness(element, False) or 0.0

    return 0.0


def get_local_obstacle_bounds(source_origin, axis_x, obstacle_info, include_insulation):
    points = get_obstacle_points(obstacle_info)
    if not points:
        raise Exception("Could not read obstacle geometry.")

    axis_y = XYZ.BasisZ.CrossProduct(axis_x)
    min_s = None
    max_s = None
    min_y = None
    max_y = None
    min_z = None
    max_z = None

    for point in points:
        relative = point.Subtract(source_origin)
        s_value = relative.DotProduct(axis_x)
        y_value = relative.DotProduct(axis_y)
        z_value = point.Z

        if min_s is None or s_value < min_s:
            min_s = s_value
        if max_s is None or s_value > max_s:
            max_s = s_value
        if min_y is None or y_value < min_y:
            min_y = y_value
        if max_y is None or y_value > max_y:
            max_y = y_value
        if min_z is None or z_value < min_z:
            min_z = z_value
        if max_z is None or z_value > max_z:
            max_z = z_value

    expansion = get_obstacle_expansion(obstacle_info.element, include_insulation)
    if expansion > 0:
        min_s -= expansion
        max_s += expansion
        min_y -= expansion
        max_y += expansion
        min_z -= expansion
        max_z += expansion

    return {
        "min_s": min_s,
        "max_s": max_s,
        "min_y": min_y,
        "max_y": max_y,
        "min_z": min_z,
        "max_z": max_z,
    }


def pick_source_curves():
    try:
        with forms.WarningBar(title="Pick pipes and ducts for bypass"):
            references = uidoc.Selection.PickObjects(ObjectType.Element, MepCurveSelectionFilter())
    except Exception:
        return None

    elements = []
    seen_ids = set()
    for reference in references:
        element = doc.GetElement(reference.ElementId)
        if element is None:
            continue
        element_id_value = element.Id.IntegerValue
        if element_id_value in seen_ids:
            continue
        seen_ids.add(element_id_value)
        elements.append(element)
    return elements


def pick_obstacle():
    pick_mode = forms.CommandSwitchWindow.show(
        ["Active model", "Linked model"],
        message="Select obstacle source",
        recognize_access_key=False,
    )
    if pick_mode is None:
        return None

    if pick_mode == "Active model":
        try:
            with forms.WarningBar(title="Pick obstacle in active model"):
                reference = uidoc.Selection.PickObject(ObjectType.Element, HostObstacleSelectionFilter())
        except Exception:
            return None

        element = doc.GetElement(reference.ElementId)
        if element is None:
            return None
        return ObstacleInfo(element, Transform.Identity, get_element_label(element))

    try:
        with forms.WarningBar(title="Pick obstacle in linked model"):
            reference = uidoc.Selection.PickObject(ObjectType.LinkedElement, LinkedObstacleSelectionFilter())
    except Exception:
        return None

    link_instance = doc.GetElement(reference.ElementId)
    if link_instance is None:
        return None

    linked_document = link_instance.GetLinkDocument()
    if linked_document is None:
        raise Exception("The selected Revit link is not loaded.")

    linked_element = linked_document.GetElement(reference.LinkedElementId)
    if linked_element is None:
        raise Exception("Could not resolve the linked obstacle.")

    try:
        transform = link_instance.GetTotalTransform()
    except Exception:
        transform = link_instance.GetTransform()

    label = "{} (link)".format(get_element_label(linked_element))
    return ObstacleInfo(linked_element, transform, label)


def validate_source_curve(element):
    curve_line = get_curve_line(element)
    if curve_line is None:
        raise Exception("Only straight pipe and duct curves are supported.")

    direction = curve_line.Direction
    if abs(direction.Z) > HORIZONTAL_TOL:
        raise Exception("Only near-horizontal pipe and duct curves are supported.")

    axis_x = unit_xy(direction)
    if axis_x is None:
        raise Exception("Could not resolve curve direction.")

    return curve_line, axis_x


def build_bypass_plan(
    source_element,
    obstacle_info,
    options,
    clearance_internal,
    segment_length_factor=MIN_SEGMENT_LENGTH_FACTOR,
):
    curve_line, axis_x = validate_source_curve(source_element)
    source_origin = curve_line.GetEndPoint(0)
    source_plan_factor = get_curve_plan_factor(curve_line)
    source_plan_length = curve_line.Length * source_plan_factor
    source_z = source_origin.Z

    profile = get_curve_profile(source_element, options.include_insulation)
    required_straight_length = get_required_straight_length(profile)
    required_top_segment_length, segment_length_factor = get_required_bypass_segment_length(
        required_straight_length,
        segment_length_factor,
    )
    required_leg_segment_length = required_straight_length
    required_source_plan_length = required_straight_length * source_plan_factor
    obstacle_bounds = get_local_obstacle_bounds(
        source_origin,
        axis_x,
        obstacle_info,
        options.include_insulation,
    )

    if obstacle_bounds["max_y"] < (-profile["half_width"] - clearance_internal):
        raise Exception("Obstacle does not intersect the selected element corridor.")
    if obstacle_bounds["min_y"] > (profile["half_width"] + clearance_internal):
        raise Exception("Obstacle does not intersect the selected element corridor.")
    if obstacle_bounds["max_s"] <= 0 or obstacle_bounds["min_s"] >= source_plan_length:
        raise Exception("Obstacle does not overlap the selected curve span.")

    current_bottom = source_z - profile["half_height"]
    current_top = source_z + profile["half_height"]

    if options.direction == "Above":
        if current_bottom >= obstacle_bounds["max_z"] + clearance_internal - EPS:
            raise Exception("The selected element already clears the obstacle above.")
        minimum_target_z = obstacle_bounds["max_z"] + profile["half_height"] + clearance_internal
    else:
        if current_top <= obstacle_bounds["min_z"] - clearance_internal + EPS:
            raise Exception("The selected element already clears the obstacle below.")
        minimum_target_z = obstacle_bounds["min_z"] - profile["half_height"] - clearance_internal

    minimum_vertical_delta = abs(minimum_target_z - source_z)

    if options.angle_degrees >= 89.999:
        minimum_vertical_for_leg = required_leg_segment_length
    else:
        minimum_vertical_for_leg = required_leg_segment_length * math.sin(
            math.radians(options.angle_degrees)
        )

    actual_vertical_delta_abs = max(minimum_vertical_delta, minimum_vertical_for_leg)
    vertical_delta = actual_vertical_delta_abs if options.direction == "Above" else -actual_vertical_delta_abs
    target_z = source_z + vertical_delta
    if options.direction == "Above":
        achieved_clearance = (target_z - profile["half_height"]) - obstacle_bounds["max_z"]
    else:
        achieved_clearance = obstacle_bounds["min_z"] - (target_z + profile["half_height"])
    achieved_clearance = max(0.0, achieved_clearance)

    angle_radians = math.radians(options.angle_degrees)
    if options.angle_degrees >= 89.999:
        run_length = 0.0
    else:
        tan_value = math.tan(angle_radians)
        if abs(tan_value) < EPS:
            raise Exception("Invalid bypass angle.")
        run_length = abs(vertical_delta) / tan_value

    base_start_top_s = obstacle_bounds["min_s"] - clearance_internal
    base_end_top_s = obstacle_bounds["max_s"] + clearance_internal
    base_top_span = base_end_top_s - base_start_top_s
    additional_top_span = max(0.0, required_top_segment_length - base_top_span)
    extra_top_span_each_side = additional_top_span * 0.5

    start_top_s = base_start_top_s - extra_top_span_each_side
    end_top_s = base_end_top_s + extra_top_span_each_side
    top_segment_length = end_top_s - start_top_s
    leg_segment_length = (
        required_leg_segment_length
        if options.angle_degrees >= 89.999
        else abs(vertical_delta) / math.sin(angle_radians)
    )

    start_break_s = start_top_s - run_length
    end_break_s = end_top_s + run_length

    if start_break_s <= required_source_plan_length:
        raise Exception(
            "Installation section is too short before the obstacle for the selected bypass parameters."
        )
    if end_break_s >= source_plan_length - required_source_plan_length:
        raise Exception(
            "Installation section is too short after the obstacle for the selected bypass parameters."
        )
    if start_top_s - start_break_s < -EPS:
        raise Exception("Invalid bypass start geometry.")
    if end_break_s - end_top_s < -EPS:
        raise Exception("Invalid bypass end geometry.")
    if top_segment_length + EPS < required_top_segment_length:
        raise Exception(
            "Installation section is too short to keep the required straight segment between bypass fittings."
        )
    if leg_segment_length + EPS < required_leg_segment_length:
        raise Exception(
            "Bypass legs are too short to satisfy fitting spacing requirements."
        )

    point_1 = get_source_point_at_plan_distance(curve_line, start_break_s)
    point_4 = get_source_point_at_plan_distance(curve_line, end_break_s)

    top_start_base = get_source_point_at_plan_distance(curve_line, start_top_s)
    top_end_base = get_source_point_at_plan_distance(curve_line, end_top_s)

    point_2 = XYZ(top_start_base.X, top_start_base.Y, target_z)
    point_3 = XYZ(top_end_base.X, top_end_base.Y, target_z)

    return {
        "source_curve": curve_to_data(curve_line),
        "source_start": xyz_to_data(curve_line.GetEndPoint(0)),
        "source_end": xyz_to_data(curve_line.GetEndPoint(1)),
        "source_plan_length": source_plan_length,
        "required_straight_length": required_straight_length,
        "required_bypass_segment_length": required_top_segment_length,
        "required_top_segment_length": required_top_segment_length,
        "required_leg_segment_length": required_leg_segment_length,
        "segment_length_factor": segment_length_factor,
        "required_source_plan_length": required_source_plan_length,
        "minimum_target_z": minimum_target_z,
        "target_z": target_z,
        "vertical_delta": vertical_delta,
        "achieved_clearance": achieved_clearance,
        "minimum_vertical_delta": minimum_vertical_delta,
        "minimum_vertical_for_leg": minimum_vertical_for_leg,
        "run_length": run_length,
        "base_top_span": base_top_span,
        "additional_top_span": additional_top_span,
        "top_segment_length": top_segment_length,
        "leg_segment_length": leg_segment_length,
        "obstacle_bounds": obstacle_bounds,
        "point_1": point_1,
        "point_2": point_2,
        "point_3": point_3,
        "point_4": point_4,
    }


def create_bypass_for_curve_attempt(
    source_element,
    obstacle_info,
    options,
    clearance_internal,
    segment_length_factor,
):
    covering_specs = get_curve_covering_specs(source_element)
    profile = get_curve_profile(source_element, options.include_insulation)
    type_name = get_type_display_name(source_element)
    size_label = get_profile_size_label(profile)
    bypass_plan = build_bypass_plan(
        source_element,
        obstacle_info,
        options,
        clearance_internal,
        segment_length_factor,
    )

    debug_data = {
        "source_element_id": source_element.Id.IntegerValue,
        "source_category": source_element.Category.Name if source_element.Category else "",
        "type_name": type_name,
        "size_label": size_label,
        "source_curve": bypass_plan.get("source_curve"),
        "source_start": bypass_plan.get("source_start"),
        "source_end": bypass_plan.get("source_end"),
        "source_plan_length": bypass_plan.get("source_plan_length"),
        "required_straight_length": bypass_plan.get("required_straight_length"),
        "required_bypass_segment_length": bypass_plan.get("required_bypass_segment_length"),
        "required_top_segment_length": bypass_plan.get("required_top_segment_length"),
        "required_leg_segment_length": bypass_plan.get("required_leg_segment_length"),
        "segment_length_factor": bypass_plan.get("segment_length_factor"),
        "required_source_plan_length": bypass_plan.get("required_source_plan_length"),
        "minimum_target_z": bypass_plan.get("minimum_target_z"),
        "target_z": bypass_plan.get("target_z"),
        "vertical_delta": bypass_plan.get("vertical_delta"),
        "achieved_clearance": bypass_plan.get("achieved_clearance"),
        "minimum_vertical_delta": bypass_plan.get("minimum_vertical_delta"),
        "minimum_vertical_for_leg": bypass_plan.get("minimum_vertical_for_leg"),
        "run_length": bypass_plan.get("run_length"),
        "base_top_span": bypass_plan.get("base_top_span"),
        "additional_top_span": bypass_plan.get("additional_top_span"),
        "top_segment_length": bypass_plan.get("top_segment_length"),
        "leg_segment_length": bypass_plan.get("leg_segment_length"),
        "obstacle_bounds": bypass_plan.get("obstacle_bounds"),
        "point_1": xyz_to_data(bypass_plan["point_1"]),
        "point_2": xyz_to_data(bypass_plan["point_2"]),
        "point_3": xyz_to_data(bypass_plan["point_3"]),
        "point_4": xyz_to_data(bypass_plan["point_4"]),
    }

    tolerance = max(doc.Application.ShortCurveTolerance, 0.001)
    source_start_point = data_to_xyz(bypass_plan.get("source_start"))
    source_end_point = data_to_xyz(bypass_plan.get("source_end"))

    downstream_segment_id = break_curve_at_point(source_element, bypass_plan["point_1"])
    downstream_segment = doc.GetElement(downstream_segment_id)
    updated_source_element = doc.GetElement(source_element.Id)
    if downstream_segment is None or updated_source_element is None:
        raise Exception("Failed to split the selected element at the bypass start.")
    doc.Regenerate()

    left_segment, segment_to_break = get_segment_containing_point(
        updated_source_element,
        downstream_segment,
        source_start_point,
        tolerance,
    )

    segment_to_break, _unused_other = get_segment_containing_point(
        updated_source_element,
        downstream_segment,
        bypass_plan["point_4"],
        tolerance,
    )
    if segment_to_break.Id == left_segment.Id:
        raise Exception("Could not resolve the downstream segment after the first split.")

    right_segment_id = break_curve_at_point(segment_to_break, bypass_plan["point_4"])
    right_segment_candidate = doc.GetElement(right_segment_id)
    updated_middle_candidate = doc.GetElement(segment_to_break.Id)
    if right_segment_candidate is None or updated_middle_candidate is None:
        raise Exception("Failed to split the selected element at the bypass end.")
    doc.Regenerate()

    right_segment, middle_segment = get_segment_containing_point(
        right_segment_candidate,
        updated_middle_candidate,
        source_end_point,
        tolerance,
    )

    debug_data["left_segment_id"] = left_segment.Id.IntegerValue
    debug_data["middle_segment_id"] = middle_segment.Id.IntegerValue
    debug_data["right_segment_id"] = right_segment.Id.IntegerValue
    debug_data["left_segment_curve"] = curve_to_data(get_curve_from_element(left_segment))
    debug_data["middle_segment_curve"] = curve_to_data(get_curve_from_element(middle_segment))
    debug_data["right_segment_curve"] = curve_to_data(get_curve_from_element(right_segment))

    doc.Delete(middle_segment.Id)
    orientation_attempts = [
        (True, True, True),
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (False, False, True),
        (False, True, False),
        (True, False, False),
        (False, False, False),
    ]
    attempt_errors = []

    for rise_forward, top_forward, drop_forward in orientation_attempts:
        attempt_subtransaction = SubTransaction(doc)
        attempt_subtransaction.Start()

        try:
            rise_start, rise_end = get_segment_endpoints(
                bypass_plan["point_1"],
                bypass_plan["point_2"],
                rise_forward,
            )
            top_start, top_end = get_segment_endpoints(
                bypass_plan["point_2"],
                bypass_plan["point_3"],
                top_forward,
            )
            drop_start, drop_end = get_segment_endpoints(
                bypass_plan["point_3"],
                bypass_plan["point_4"],
                drop_forward,
            )

            rise_segment = create_curve_like(source_element, rise_start, rise_end)
            top_segment = create_curve_like(source_element, top_start, top_end)
            drop_segment = create_curve_like(source_element, drop_start, drop_end)
            doc.Regenerate()

            connect_with_elbow(
                left_segment,
                bypass_plan["point_1"],
                rise_segment,
                bypass_plan["point_1"],
                "source-rise",
            )
            connect_with_elbow(
                rise_segment,
                bypass_plan["point_2"],
                top_segment,
                bypass_plan["point_2"],
                "rise-top",
            )
            connect_with_elbow(
                top_segment,
                bypass_plan["point_3"],
                drop_segment,
                bypass_plan["point_3"],
                "top-drop",
            )
            connect_with_elbow(
                drop_segment,
                bypass_plan["point_4"],
                right_segment,
                bypass_plan["point_4"],
                "drop-source",
            )

            covering_warnings = apply_coverings(
                [rise_segment, top_segment, drop_segment],
                covering_specs,
            )

            attempt_subtransaction.Commit()
            debug_data["orientation_attempt"] = {
                "rise_forward": rise_forward,
                "top_forward": top_forward,
                "drop_forward": drop_forward,
            }

            warning_message = ""
            if covering_warnings:
                warning_message = "Coverings were not fully restored: {}".format(
                    "; ".join(covering_warnings)
                )

            result_message = "Bypass created. Clearance between elements: {}.".format(
                format_project_length_value(bypass_plan["achieved_clearance"]),
            )
            return result_message, warning_message, debug_data
        except Exception as attempt_error:
            if attempt_subtransaction.HasStarted():
                attempt_subtransaction.RollBack()
            attempt_errors.append(
                {
                    "rise_forward": rise_forward,
                    "top_forward": top_forward,
                    "drop_forward": drop_forward,
                    "error": str(attempt_error),
                }
            )

    debug_data["orientation_attempts"] = attempt_errors
    debug_data["requested_angle_degrees"] = options.angle_label
    if any(
        is_top_straight_retryable_error_message(attempt.get("error"))
        for attempt in attempt_errors
    ):
        debug_data["spacing_retryable"] = True
        debug_data["spacing_retry_reason"] = "top_straight_section"
        raise BypassCreationError(
            "Bypass requires a longer straight section between elbows for this size and angle.",
            debug_data,
        )
    raise BypassCreationError(
        "Selected type '{}' does not support {} deg elbows for size {} under current routing preferences.".format(
            type_name,
            options.angle_label,
            size_label,
        ),
        debug_data,
    )


def create_bypass_for_curve(source_element, obstacle_info, options, clearance_internal):
    profile = get_curve_profile(source_element, options.include_insulation)
    size_label = get_profile_size_label(profile)
    attempted_factors = []
    last_spacing_error = None
    last_spacing_debug = None

    for segment_length_factor in get_segment_length_factors():
        attempted_factors.append(segment_length_factor)
        transaction = Transaction(doc, "Create bypass - PYLAB")
        transaction.Start()
        failure_preprocessor = BypassFailuresPreprocessor(COMMIT_RETRY_WARNING_MARKERS)
        failure_options = transaction.GetFailureHandlingOptions()
        failure_options.SetFailuresPreprocessor(failure_preprocessor)
        failure_options.SetClearAfterRollback(True)
        transaction.SetFailureHandlingOptions(failure_options)

        try:
            result_message, warning_message, debug_data = create_bypass_for_curve_attempt(
                source_element,
                obstacle_info,
                options,
                clearance_internal,
                segment_length_factor,
            )
            debug_data["attempted_segment_length_factors"] = attempted_factors
            commit_status = transaction.Commit()
            debug_data["commit_warning_messages"] = list(
                failure_preprocessor.warning_messages
            )

            if failure_preprocessor.rollback_requested:
                last_spacing_error = (
                    failure_preprocessor.retryable_warning_messages[-1]
                    if failure_preprocessor.retryable_warning_messages
                    else "Transaction rolled back because Revit reported invalid bypass connections."
                )
                debug_data["spacing_retryable"] = True
                debug_data["spacing_retry_reason"] = "commit_warning"
                debug_data["spacing_retry_last_error"] = last_spacing_error
                last_spacing_debug = debug_data
                continue

            if commit_status != DB.TransactionStatus.Committed:
                raise BypassCreationError(
                    "Bypass transaction did not commit.",
                    debug_data,
                )

            return result_message, warning_message, debug_data
        except Exception as attempt_error:
            if transaction.HasStarted():
                transaction.RollBack()

            attempt_message = str(attempt_error)
            attempt_debug = getattr(attempt_error, "debug_data", {}) or {}
            attempt_debug["attempted_segment_length_factors"] = attempted_factors

            if attempt_debug.get("spacing_retryable") or is_top_straight_retryable_error_message(
                attempt_message
            ):
                last_spacing_error = attempt_message
                last_spacing_debug = attempt_debug
                continue

            if last_spacing_error and is_insufficient_section_error_message(attempt_message):
                failure_debug = dict(last_spacing_debug or {})
                failure_debug.update(attempt_debug)
                failure_debug["attempted_segment_length_factors"] = attempted_factors
                failure_debug["spacing_retry_last_error"] = last_spacing_error
                raise BypassCreationError(
                    "Installation section is too short to create a bypass with a long enough straight section between elbows for size {}.".format(
                        size_label
                    ),
                    failure_debug,
                )

            raise

    failure_debug = dict(last_spacing_debug or {})
    failure_debug["attempted_segment_length_factors"] = attempted_factors
    if last_spacing_error:
        failure_debug["spacing_retry_last_error"] = last_spacing_error
    raise BypassCreationError(
        "Installation section is too short to create a bypass with a long enough straight section between elbows for size {}.".format(
            size_label
        ),
        failure_debug,
    )


def process_curves(source_elements, obstacle_info, options, clearance_internal):
    results = []
    debug_records = []
    transaction_group = TransactionGroup(doc, "Create bypass - PYLAB")
    transaction_group.Start()

    try:
        for source_element in source_elements:
            source_label = get_element_label(source_element)

            try:
                result_message, warning_message, debug_data = create_bypass_for_curve(
                    source_element,
                    obstacle_info,
                    options,
                    clearance_internal,
                )
                results.append(
                    BypassResult(
                        source_label,
                        "Success",
                        result_message,
                        warning_message,
                    )
                )
                debug_data["status"] = "Success"
                debug_records.append(debug_data)
            except Exception as source_error:
                results.append(
                    BypassResult(
                        source_label,
                        "Failed",
                        str(source_error),
                        "",
                    )
                )
                failure_debug = {
                    "source_element_id": source_element.Id.IntegerValue,
                    "source_category": source_element.Category.Name if source_element.Category else "",
                    "type_name": get_type_display_name(source_element),
                    "size_label": get_size_label_for_element(
                        source_element,
                        options.include_insulation,
                    ),
                    "requested_angle_degrees": options.angle_label,
                    "status": "Failed",
                    "error": str(source_error),
                }
                if hasattr(source_error, "debug_data"):
                    try:
                        failure_debug.update(source_error.debug_data)
                    except Exception:
                        pass
                try:
                    failure_segment_length_factor = failure_debug.get(
                        "segment_length_factor",
                        MIN_SEGMENT_LENGTH_FACTOR,
                    )
                    failure_plan = build_bypass_plan(
                        source_element,
                        obstacle_info,
                        options,
                        clearance_internal,
                        failure_segment_length_factor,
                    )
                    failure_debug["source_curve"] = failure_plan.get("source_curve")
                    failure_debug["source_start"] = failure_plan.get("source_start")
                    failure_debug["source_end"] = failure_plan.get("source_end")
                    failure_debug["source_plan_length"] = failure_plan.get("source_plan_length")
                    failure_debug["required_straight_length"] = failure_plan.get("required_straight_length")
                    failure_debug["required_bypass_segment_length"] = failure_plan.get(
                        "required_bypass_segment_length"
                    )
                    failure_debug["required_top_segment_length"] = failure_plan.get(
                        "required_top_segment_length"
                    )
                    failure_debug["required_leg_segment_length"] = failure_plan.get(
                        "required_leg_segment_length"
                    )
                    failure_debug["segment_length_factor"] = failure_plan.get(
                        "segment_length_factor"
                    )
                    failure_debug["required_source_plan_length"] = failure_plan.get("required_source_plan_length")
                    failure_debug["minimum_target_z"] = failure_plan.get("minimum_target_z")
                    failure_debug["target_z"] = failure_plan.get("target_z")
                    failure_debug["vertical_delta"] = failure_plan.get("vertical_delta")
                    failure_debug["achieved_clearance"] = failure_plan.get("achieved_clearance")
                    failure_debug["minimum_vertical_delta"] = failure_plan.get("minimum_vertical_delta")
                    failure_debug["minimum_vertical_for_leg"] = failure_plan.get("minimum_vertical_for_leg")
                    failure_debug["run_length"] = failure_plan.get("run_length")
                    failure_debug["base_top_span"] = failure_plan.get("base_top_span")
                    failure_debug["additional_top_span"] = failure_plan.get("additional_top_span")
                    failure_debug["top_segment_length"] = failure_plan.get("top_segment_length")
                    failure_debug["leg_segment_length"] = failure_plan.get("leg_segment_length")
                    failure_debug["obstacle_bounds"] = failure_plan.get("obstacle_bounds")
                    failure_debug["point_1"] = xyz_to_data(failure_plan["point_1"])
                    failure_debug["point_2"] = xyz_to_data(failure_plan["point_2"])
                    failure_debug["point_3"] = xyz_to_data(failure_plan["point_3"])
                    failure_debug["point_4"] = xyz_to_data(failure_plan["point_4"])
                except Exception as debug_error:
                    failure_debug["debug_plan_error"] = str(debug_error)
                debug_records.append(
                    failure_debug
                )
        transaction_group.Assimilate()
    except Exception:
        transaction_group.RollBack()
        raise

    debug_payload = {
        "tool": TITLE,
        "obstacle": obstacle_info.label_text,
        "direction": options.direction,
        "angle_degrees": options.angle_label,
        "include_insulation": bool(options.include_insulation),
        "clearance_internal": clearance_internal,
        "records": debug_records,
    }
    debug_file_path = write_debug_cache(debug_payload)

    return results, debug_file_path


def write_report(results, obstacle_info, options, debug_file_path):
    output.print_md("## Bypass Results")
    output.print_md(
        "Obstacle: **{}**  \nDirection: **{}**  \nAngle: **{} deg**  \nInclude insulation: **{}**".format(
            obstacle_info.label_text,
            options.direction,
            options.angle_label,
            "Yes" if options.include_insulation else "No",
        )
    )
    if debug_file_path:
        print("Debug cache: {}".format(debug_file_path))

    for result in results:
        if result.status == "Success":
            print("[OK] {} - {}".format(result.source_label, result.message))
            if result.warning_message:
                print("  Warning: {}".format(result.warning_message))
        else:
            print("[FAILED] {} - {}".format(result.source_label, result.message))


def show_summary(results, debug_file_path):
    success_count = len([result for result in results if result.status == "Success"])
    failure_count = len(results) - success_count
    warning_count = len(
        [result for result in results if result.status == "Success" and result.warning_message]
    )

    summary_lines = [
        "Processed elements: {}".format(len(results)),
        "Successful bypasses: {}".format(success_count),
        "Failures: {}".format(failure_count),
    ]
    if warning_count:
        summary_lines.append("Warnings: {}".format(warning_count))
    if debug_file_path:
        summary_lines.append("Debug cache: {}".format(debug_file_path))

    forms.alert(
        "\n".join(summary_lines),
        title=TITLE,
        warn_icon=failure_count > 0,
        exitscript=False,
    )


def main():
    source_elements = pick_source_curves()
    if not source_elements:
        return

    try:
        obstacle_info = pick_obstacle()
    except Exception as obstacle_error:
        forms.alert(str(obstacle_error), title=TITLE, warn_icon=True, exitscript=False)
        return

    if obstacle_info is None:
        return

    options, clearance_internal = show_options_dialog()
    if options is None:
        return

    try:
        results, debug_file_path = process_curves(
            source_elements,
            obstacle_info,
            options,
            clearance_internal,
        )
    except Exception as run_error:
        forms.alert(str(run_error), title=TITLE, warn_icon=True, exitscript=False)
        return

    write_report(results, obstacle_info, options, debug_file_path)
    show_summary(results, debug_file_path)


if __name__ == "__main__":
    main()
