"""Place non-hosted family instances into Rooms and/or MEP Spaces.

Assumptions:
- Runs inside pyRevit with IronPython-compatible Python and the Revit API.
- Offsets are entered in project length units and converted to Revit internal units.
- Only the active document is processed; linked models are ignored.
- Family filtering is best-effort. Final placement validation is authoritative.
"""

import os
import math
import clr

clr.AddReference("System")
clr.AddReference("System.Core")
clr.AddReference("PresentationCore")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

from System import Object, Predicate
from System.Collections.ObjectModel import ObservableCollection
from System.Windows.Data import CollectionViewSource

from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from Autodesk.Revit import DB

from Autodesk.Revit.DB import (
    BuiltInCategory,
    CategoryType,
    ElementId,
    ElementTransformUtils,
    FamilyPlacementType,
    FamilySymbol,
    FilteredElementCollector,
    Level,
    Line,
    LocationPoint,
    SpatialElementBoundaryOptions,
    StorageType,
    SubTransaction,
    Transaction,
    UnitUtils,
    XYZ,
)
from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.DB.Mechanical import Space
from Autodesk.Revit.DB.Structure import StructuralType


doc = revit.doc
output = script.get_output()
SPEC_TYPE_ID = getattr(DB, "SpecTypeId", None)
UNIT_TYPE = getattr(DB, "UnitType", None)


EXCLUDED_CATEGORY_IDS = set([
    int(BuiltInCategory.OST_GenericAnnotation),
    int(BuiltInCategory.OST_DetailComponents),
    int(BuiltInCategory.OST_TitleBlocks),
    int(BuiltInCategory.OST_Viewports),
    int(BuiltInCategory.OST_Views),
    int(BuiltInCategory.OST_Cameras),
    int(BuiltInCategory.OST_ProfileFamilies),
])

SUPPORTED_PARAMETER_NAMES = {
    "Room/Space Number": "number",
    "Room/Space Name": "name",
    "Source Spatial Element Id": "element_id_text",
    "Source Spatial Type": "spatial_type",
}


# -----------------------------------------------------------------------------
# Data collection helpers
# -----------------------------------------------------------------------------


class SpatialRow(object):
    def __init__(self, element, spatial_type, number, name, level_name, level_id):
        self.IsSelected = False
        self.SpatialType = spatial_type
        self.Number = number or ""
        self.Name = name or ""
        self.LevelName = level_name or ""
        self.LevelId = level_id
        self.ElementRef = element
        self.ElementIdValue = element.Id.IntegerValue
        self.ElementIdText = str(element.Id.IntegerValue)
        self.FamilyOptions = None
        self.SelectedFamilyOption = None


class FamilySymbolOption(object):
    def __init__(self, symbol):
        self.Symbol = symbol
        self.DisplayName = "{} : {}".format(
            get_family_name(symbol),
            get_symbol_name(symbol)
        )


class PlacementResult(object):
    def __init__(self, row, family_name, status, instance_id=None, error_message="", warning_message=""):
        self.row = row
        self.family_name = family_name or ""
        self.status = status
        self.instance_id = instance_id
        self.error_message = error_message or ""
        self.warning_message = warning_message or ""


def get_sorted_levels(document):
    levels = list(
        FilteredElementCollector(document)
        .OfClass(Level)
        .WhereElementIsNotElementType()
    )
    levels.sort(key=lambda level: level.Elevation)
    return levels


def get_string_parameter_value(element, parameter_name):
    try:
        parameter = element.LookupParameter(parameter_name)
        if parameter is None:
            return ""
        value = parameter.AsString()
        if value:
            return value
        value = parameter.AsValueString()
        if value:
            return value
    except Exception:
        pass
    return ""


def get_spatial_number(element):
    try:
        value = getattr(element, "Number", None)
        if value:
            return value
    except Exception:
        pass
    return get_string_parameter_value(element, "Number")


def get_spatial_name(element):
    try:
        value = getattr(element, "Name", None)
        if value:
            return value
    except Exception:
        pass
    return get_string_parameter_value(element, "Name")


def get_location_point_xyz(element):
    try:
        location = element.Location
        if isinstance(location, LocationPoint):
            return location.Point
    except Exception:
        pass
    return None


def get_bounding_box_center(element):
    try:
        bbox = element.get_BoundingBox(None)
        if bbox is None:
            return None
        min_point = bbox.Min
        max_point = bbox.Max
        if min_point is None or max_point is None:
            return None
        return XYZ(
            (min_point.X + max_point.X) / 2.0,
            (min_point.Y + max_point.Y) / 2.0,
            (min_point.Z + max_point.Z) / 2.0
        )
    except Exception:
        pass
    return None


def is_valid_spatial_element(element):
    try:
        area = getattr(element, "Area", None)
        if area is not None and area <= 0:
            return False
    except Exception:
        pass

    if get_location_point_xyz(element) is not None:
        return True
    if get_bounding_box_center(element) is not None:
        return True
    if get_primary_boundary_loop_points(element) is not None:
        return True
    return False


def get_nearest_level(levels, elevation):
    nearest_level = None
    nearest_distance = None
    for level in levels:
        distance = abs(level.Elevation - elevation)
        if nearest_distance is None or distance < nearest_distance:
            nearest_distance = distance
            nearest_level = level
    return nearest_level


def get_best_level(document, element, levels, reference_point=None):
    try:
        level_id = element.LevelId
        if level_id and level_id != ElementId.InvalidElementId:
            level = document.GetElement(level_id)
            if isinstance(level, Level):
                return level
    except Exception:
        pass

    if reference_point is None:
        reference_point = get_location_point_xyz(element) or get_bounding_box_center(element)
    if reference_point is None:
        return None
    return get_nearest_level(levels, reference_point.Z)


def collect_spatial_rows(document, levels):
    rows = []
    collectors = [
        ("Room", FilteredElementCollector(document)
         .OfCategory(BuiltInCategory.OST_Rooms)
         .WhereElementIsNotElementType()),
        ("Space", FilteredElementCollector(document)
         .OfCategory(BuiltInCategory.OST_MEPSpaces)
         .WhereElementIsNotElementType()),
    ]

    for spatial_type, collector in collectors:
        for element in collector:
            if not is_valid_spatial_element(element):
                continue

            level = get_best_level(document, element, levels)
            level_id = level.Id if level else ElementId.InvalidElementId
            level_name = level.Name if level else ""
            rows.append(
                SpatialRow(
                    element=element,
                    spatial_type=spatial_type,
                    number=get_spatial_number(element),
                    name=get_spatial_name(element),
                    level_name=level_name,
                    level_id=level_id,
                )
            )

    rows.sort(key=lambda row: (row.SpatialType, row.LevelName, row.Number, row.Name))
    return rows


# -----------------------------------------------------------------------------
# Family compatibility helpers
# -----------------------------------------------------------------------------


def get_family_name(symbol):
    try:
        return symbol.Family.Name
    except Exception:
        return "<Unknown Family>"


def get_symbol_name(symbol):
    try:
        return symbol.Name
    except Exception:
        return "<Unknown Type>"


def get_symbol_category_id(symbol):
    try:
        if symbol.Category is None:
            return None
        return symbol.Category.Id.IntegerValue
    except Exception:
        return None


def is_supported_placement_type(symbol):
    try:
        family = symbol.Family
        if family is None:
            return False, "Family is missing."
        placement_type = family.FamilyPlacementType
        if placement_type != FamilyPlacementType.OneLevelBased:
            return False, "Family placement type '{}' is not supported.".format(placement_type)
    except Exception as placement_error:
        return False, "Could not read family placement type: {}".format(placement_error)
    return True, ""


def is_likely_compatible_symbol(symbol):
    if not isinstance(symbol, FamilySymbol):
        return False, "Element is not a family symbol."

    try:
        category = symbol.Category
        if category is None:
            return False, "Family symbol category is missing."
        if category.CategoryType != CategoryType.Model:
            return False, "Family symbol category is not a model category."
    except Exception as category_error:
        return False, "Could not evaluate symbol category: {}".format(category_error)

    try:
        family = symbol.Family
        if family is None:
            return False, "Family symbol does not belong to a loadable family."
        if getattr(family, "IsInPlace", False):
            return False, "In-place families are not supported."
    except Exception as family_error:
        return False, "Could not evaluate family metadata: {}".format(family_error)

    category_id = get_symbol_category_id(symbol)
    if category_id in EXCLUDED_CATEGORY_IDS:
        return False, "Category is excluded from non-hosted placement."

    # Revit does not expose a perfect generic "non-hosted point-based" flag,
    # so this list is best-effort and the final placement validation below is
    # authoritative for the command.
    return is_supported_placement_type(symbol)


def get_compatible_family_symbol_options(document):
    options = []
    collector = (
        FilteredElementCollector(document)
        .OfClass(FamilySymbol)
        .WhereElementIsElementType()
    )

    for symbol in collector:
        is_compatible, _ = is_likely_compatible_symbol(symbol)
        if is_compatible:
            options.append(FamilySymbolOption(symbol))

    options.sort(key=lambda option: option.DisplayName)
    return options


def validate_selected_symbol(symbol):
    is_compatible, reason = is_likely_compatible_symbol(symbol)
    if not is_compatible:
        return False, reason
    return True, ""


# -----------------------------------------------------------------------------
# Insertion point helpers
# -----------------------------------------------------------------------------


def points_are_close(point_a, point_b, tolerance=1e-06):
    if point_a is None or point_b is None:
        return False

    try:
        return point_a.DistanceTo(point_b) <= tolerance
    except Exception:
        return False


def is_point_inside_spatial_element(element, point):
    if point is None:
        return False
    try:
        if isinstance(element, Room):
            return element.IsPointInRoom(point)
        if isinstance(element, Space):
            return element.IsPointInSpace(point)
    except Exception:
        return False
    return False


def build_offset_xyz(x_offset, y_offset, z_offset):
    return XYZ(x_offset, y_offset, z_offset)


def add_xyz(base_point, offset_xyz):
    return XYZ(
        base_point.X + offset_xyz.X,
        base_point.Y + offset_xyz.Y,
        base_point.Z + offset_xyz.Z
    )


def build_xy_from_point(point, z_value):
    return XYZ(point.X, point.Y, z_value)


def get_candidate_points(element):
    candidates = []

    location_point = get_location_point_xyz(element)
    if location_point is not None:
        candidates.append(("LocationPoint", location_point))

    bbox_center = get_bounding_box_center(element)
    if bbox_center is not None:
        candidates.append(("BoundingBoxCenter", bbox_center))

    return candidates


def get_spatial_type_label(element):
    if isinstance(element, Room):
        return "Room"
    if isinstance(element, Space):
        return "Space"
    return "spatial element"


def get_default_reference_point(element):
    location_point = get_location_point_xyz(element)
    if location_point is not None:
        return location_point
    return get_bounding_box_center(element)


def get_valid_spatial_reference_point(element):
    for _, candidate_point in get_candidate_points(element):
        if is_point_inside_spatial_element(element, candidate_point):
            return candidate_point
    return get_default_reference_point(element)


def get_curve_points(curve):
    points = []

    try:
        for point in curve.Tessellate():
            points.append(point)
    except Exception:
        pass

    if not points:
        try:
            points.append(curve.GetEndPoint(0))
            points.append(curve.GetEndPoint(1))
        except Exception:
            pass

    return points


def get_boundary_loops_points(element):
    try:
        boundary_loops = element.GetBoundarySegments(SpatialElementBoundaryOptions())
    except Exception:
        boundary_loops = None

    if not boundary_loops:
        return []

    loops = []
    for boundary_loop in boundary_loops:
        loop_points = []
        for boundary_segment in boundary_loop:
            curve = boundary_segment.GetCurve()
            for point in get_curve_points(curve):
                if not loop_points or not points_are_close(loop_points[-1], point):
                    loop_points.append(point)

        if len(loop_points) < 3:
            continue

        if not points_are_close(loop_points[0], loop_points[-1]):
            loop_points.append(loop_points[0])

        if len(loop_points) >= 4:
            loops.append(loop_points)

    return loops


def get_polygon_signed_area_and_centroid(points):
    if not points or len(points) < 4:
        return 0.0, None

    area_factor = 0.0
    centroid_x_factor = 0.0
    centroid_y_factor = 0.0

    for index in range(len(points) - 1):
        point_a = points[index]
        point_b = points[index + 1]
        cross = (point_a.X * point_b.Y) - (point_b.X * point_a.Y)
        area_factor += cross
        centroid_x_factor += (point_a.X + point_b.X) * cross
        centroid_y_factor += (point_a.Y + point_b.Y) * cross

    signed_area = area_factor / 2.0
    if abs(signed_area) <= 1e-09:
        return signed_area, None

    centroid_x = centroid_x_factor / (6.0 * signed_area)
    centroid_y = centroid_y_factor / (6.0 * signed_area)
    return signed_area, XYZ(centroid_x, centroid_y, points[0].Z)


def get_polygon_bbox_center(points, z_value):
    if not points or len(points) < 2:
        return None

    non_repeated_points = points[:-1]
    min_x = min([point.X for point in non_repeated_points])
    max_x = max([point.X for point in non_repeated_points])
    min_y = min([point.Y for point in non_repeated_points])
    max_y = max([point.Y for point in non_repeated_points])
    return XYZ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, z_value)


def get_primary_boundary_loop_points(element):
    primary_loop = None
    primary_area = None

    for loop_points in get_boundary_loops_points(element):
        signed_area, _ = get_polygon_signed_area_and_centroid(loop_points)
        current_area = abs(signed_area)
        if current_area <= 1e-09:
            continue

        if primary_area is None or current_area > primary_area:
            primary_loop = loop_points
            primary_area = current_area

    return primary_loop


def get_target_center_xy(element):
    reference_point = get_valid_spatial_reference_point(element)
    if reference_point is None:
        reference_point = get_default_reference_point(element)
    if reference_point is None:
        return None, None, "Could not determine a valid reference point for the {}.".format(
            get_spatial_type_label(element)
        )

    base_z = reference_point.Z
    primary_loop = get_primary_boundary_loop_points(element)
    if primary_loop is not None:
        _, centroid_point = get_polygon_signed_area_and_centroid(primary_loop)
        if centroid_point is not None:
            centroid_xy = build_xy_from_point(centroid_point, base_z)
            if is_point_inside_spatial_element(element, centroid_xy):
                return centroid_xy, reference_point, ""

        boundary_bbox_center = get_polygon_bbox_center(primary_loop, base_z)
        if boundary_bbox_center is not None and is_point_inside_spatial_element(element, boundary_bbox_center):
            return boundary_bbox_center, reference_point, ""

    location_point = get_location_point_xyz(element)
    if location_point is not None:
        location_xy = build_xy_from_point(location_point, base_z)
        if is_point_inside_spatial_element(element, location_xy):
            return location_xy, reference_point, ""

    bbox_center = get_bounding_box_center(element)
    if bbox_center is not None:
        bbox_center_xy = build_xy_from_point(bbox_center, base_z)
        if is_point_inside_spatial_element(element, bbox_center_xy):
            return bbox_center_xy, reference_point, ""

    return None, reference_point, "Could not determine a valid 2D center inside the {}.".format(
        get_spatial_type_label(element)
    )


def get_target_center_point(element, offset_xyz):
    target_center_xy, reference_point, error_message = get_target_center_xy(element)
    if target_center_xy is None:
        return None, reference_point, error_message

    final_target_point = XYZ(
        target_center_xy.X + offset_xyz.X,
        target_center_xy.Y + offset_xyz.Y,
        target_center_xy.Z + offset_xyz.Z
    )
    return final_target_point, reference_point, ""


def get_instance_bounding_box(instance):
    bbox = instance.get_BoundingBox(None)
    if bbox is None or bbox.Min is None or bbox.Max is None:
        raise Exception("Could not determine the placed family bounding box.")
    return bbox


def get_bbox_xy_dimensions(bbox):
    return abs(bbox.Max.X - bbox.Min.X), abs(bbox.Max.Y - bbox.Min.Y)


def get_instance_bbox_xy_center(instance, z_value):
    bbox = get_instance_bounding_box(instance)
    return XYZ(
        (bbox.Min.X + bbox.Max.X) / 2.0,
        (bbox.Min.Y + bbox.Max.Y) / 2.0,
        z_value
    )


def align_instance_bbox_center_to_target(document, instance, target_point):
    current_center = get_instance_bbox_xy_center(instance, target_point.Z)
    move_delta = XYZ(
        target_point.X - current_center.X,
        target_point.Y - current_center.Y,
        0.0
    )

    if abs(move_delta.X) <= 1e-09 and abs(move_delta.Y) <= 1e-09:
        return

    ElementTransformUtils.MoveElement(document, instance.Id, move_delta)
    document.Regenerate()


def rotate_instance_to_state(document, instance, pivot_point, current_rotation_state, desired_rotation_state):
    if current_rotation_state == desired_rotation_state:
        return current_rotation_state

    rotation_angle = (desired_rotation_state - current_rotation_state) * (math.pi / 2.0)
    axis_line = Line.CreateBound(
        XYZ(pivot_point.X, pivot_point.Y, pivot_point.Z),
        XYZ(pivot_point.X, pivot_point.Y, pivot_point.Z + 1.0)
    )
    ElementTransformUtils.RotateElement(document, instance.Id, axis_line, rotation_angle)
    document.Regenerate()
    return desired_rotation_state


def evaluate_instance_2d_fit(element, instance, placement_z):
    bbox = get_instance_bounding_box(instance)
    bbox_center = XYZ((bbox.Min.X + bbox.Max.X) / 2.0, (bbox.Min.Y + bbox.Max.Y) / 2.0, placement_z)
    bbox_corner_points = [
        XYZ(bbox.Min.X, bbox.Min.Y, placement_z),
        XYZ(bbox.Min.X, bbox.Max.Y, placement_z),
        XYZ(bbox.Max.X, bbox.Min.Y, placement_z),
        XYZ(bbox.Max.X, bbox.Max.Y, placement_z),
    ]

    test_points = [bbox_center] + bbox_corner_points
    inside_count = 0
    for test_point in test_points:
        if is_point_inside_spatial_element(element, test_point):
            inside_count += 1

    if inside_count == len(test_points):
        return True, inside_count, ""

    return False, inside_count, "Centered but family footprint extends outside the {}.".format(
        get_spatial_type_label(element)
    )


def evaluate_instance_at_target(document, instance, element, target_point, current_rotation_state, desired_rotation_state):
    align_instance_bbox_center_to_target(document, instance, target_point)
    current_rotation_state = rotate_instance_to_state(
        document,
        instance,
        target_point,
        current_rotation_state,
        desired_rotation_state
    )
    align_instance_bbox_center_to_target(document, instance, target_point)
    document.Regenerate()

    fits_inside, fit_score, warning_message = evaluate_instance_2d_fit(element, instance, target_point.Z)
    return current_rotation_state, fits_inside, fit_score, warning_message


def generate_local_search_targets(target_point, width_value, depth_value):
    search_targets = []
    max_dimension = max(width_value, depth_value)
    step_size = max(max_dimension / 8.0, 0.1)
    max_radius = max(width_value / 2.0, depth_value / 2.0, step_size)
    ring_count = int(math.ceil(max_radius / step_size))

    for ring_index in range(1, ring_count + 1):
        for x_index in range(-ring_index, ring_index + 1):
            for y_index in range(-ring_index, ring_index + 1):
                if max(abs(x_index), abs(y_index)) != ring_index:
                    continue

                search_targets.append(
                    XYZ(
                        target_point.X + (x_index * step_size),
                        target_point.Y + (y_index * step_size),
                        target_point.Z
                    )
                )

    return search_targets


def try_find_nearby_fit(document, instance, element, target_point, current_rotation_state):
    bbox = get_instance_bounding_box(instance)
    bbox_width, bbox_depth = get_bbox_xy_dimensions(bbox)

    for search_target in generate_local_search_targets(target_point, bbox_width, bbox_depth):
        for desired_rotation_state in [0, 1]:
            current_rotation_state, fits_inside, _, warning_message = evaluate_instance_at_target(
                document,
                instance,
                element,
                search_target,
                current_rotation_state,
                desired_rotation_state
            )
            if fits_inside:
                return current_rotation_state, True, warning_message

    return current_rotation_state, False, "Centered but family footprint extends outside the {}.".format(
        get_spatial_type_label(element)
    )


def place_and_center_instance(document, element, symbol, level, target_point):
    instance = document.Create.NewFamilyInstance(
        target_point,
        symbol,
        level,
        StructuralType.NonStructural
    )
    document.Regenerate()

    current_rotation_state = 0
    centered_attempts = []

    for desired_rotation_state in [0, 1]:
        current_rotation_state, fits_inside, fit_score, warning_message = evaluate_instance_at_target(
            document,
            instance,
            element,
            target_point,
            current_rotation_state,
            desired_rotation_state
        )
        centered_attempts.append((desired_rotation_state, fit_score, warning_message))
        if fits_inside:
            return instance, "Placed", ""

    current_rotation_state, found_nearby_fit, warning_message = try_find_nearby_fit(
        document,
        instance,
        element,
        target_point,
        current_rotation_state
    )
    if found_nearby_fit:
        return instance, "Placed", ""

    best_centered_attempt = max(centered_attempts, key=lambda attempt: attempt[1])
    current_rotation_state, _, _, best_warning_message = evaluate_instance_at_target(
        document,
        instance,
        element,
        target_point,
        current_rotation_state,
        best_centered_attempt[0]
    )
    warning_message = best_centered_attempt[2] or best_warning_message or warning_message
    return instance, "Placed with warning", warning_message


# -----------------------------------------------------------------------------
# Parameter writeback helpers
# -----------------------------------------------------------------------------


def set_parameter_value(parameter, value):
    storage_type = parameter.StorageType

    if storage_type == StorageType.String:
        parameter.Set("" if value is None else str(value))
        return True

    if storage_type == StorageType.Integer:
        try:
            parameter.Set(int(value))
            return True
        except Exception:
            return False

    return False


def write_instance_parameters(instance, row):
    values = {
        "number": row.Number,
        "name": row.Name,
        "element_id_text": row.ElementIdText,
        "spatial_type": row.SpatialType,
    }

    for parameter_name, value_key in SUPPORTED_PARAMETER_NAMES.items():
        try:
            parameter = instance.LookupParameter(parameter_name)
            if parameter is None or parameter.IsReadOnly:
                continue
            set_parameter_value(parameter, values[value_key])
        except Exception:
            continue


# -----------------------------------------------------------------------------
# Unit helpers
# -----------------------------------------------------------------------------


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

    raise Exception("Could not determine project length units for offset conversion.")


def get_project_length_units_label(document):
    units = document.GetUnits()

    if SPEC_TYPE_ID is not None:
        try:
            unit_type_id = units.GetFormatOptions(SPEC_TYPE_ID.Length).GetUnitTypeId()
            return "Project length units ({})".format(unit_type_id.TypeId)
        except Exception:
            pass

    if UNIT_TYPE is not None:
        try:
            display_units = units.GetFormatOptions(UNIT_TYPE.UT_Length).DisplayUnits
            return "Project length units ({})".format(display_units)
        except Exception:
            pass

    return "Project length units"


def parse_offset_value(document, raw_value, axis_label):
    if raw_value is None:
        return 0.0

    normalized = str(raw_value).strip()
    if not normalized:
        return 0.0

    normalized = normalized.replace(",", ".")
    try:
        numeric_value = float(normalized)
    except Exception:
        raise ValueError("{} offset must be a numeric value.".format(axis_label))

    return convert_length_to_internal(document, numeric_value)


# -----------------------------------------------------------------------------
# WPF window class
# -----------------------------------------------------------------------------


class PlaceInRoomsSpacesWindow(forms.WPFWindow):
    def __init__(self, xaml_file, rows, family_options, units_label):
        forms.WPFWindow.__init__(self, xaml_file)

        self._all_rows = rows
        self._rows = ObservableCollection[Object]()
        for row in rows:
            self._rows.Add(row)

        self._family_options = ObservableCollection[Object]()
        for option in family_options:
            self._family_options.Add(option)

        for row in rows:
            row.FamilyOptions = self._family_options

        self.result = None
        self._view = None

        self.units_tb.Text = units_label
        self.bulk_family_combo.ItemsSource = self._family_options
        if self._family_options.Count > 0:
            self.bulk_family_combo.SelectedIndex = 0

        self.spatial_grid.ItemsSource = self._rows
        self._view = CollectionViewSource.GetDefaultView(self.spatial_grid.ItemsSource)
        self._view.Filter = Predicate[Object](self._filter_row)

        self.search_tb.TextChanged += self.on_filters_changed
        self.mode_rooms_rb.Checked += self.on_filters_changed
        self.mode_spaces_rb.Checked += self.on_filters_changed
        self.mode_both_rb.Checked += self.on_filters_changed
        self.assign_family_btn.Click += self.on_assign_family_to_selected_rows
        self.check_all_btn.Click += self.on_check_all
        self.uncheck_all_btn.Click += self.on_uncheck_all
        self.apply_btn.Click += self.on_apply
        self.cancel_btn.Click += self.on_cancel

        self._view.Refresh()

    def _filter_row(self, item):
        if item is None:
            return False

        mode = self.get_mode()
        if mode == "Room" and item.SpatialType != "Room":
            return False
        if mode == "Space" and item.SpatialType != "Space":
            return False

        search_text = self.get_search_text()
        if not search_text:
            return True

        haystack = "{} {} {}".format(item.Number, item.Name, item.LevelName).lower()
        return search_text in haystack

    def get_mode(self):
        if self.mode_rooms_rb.IsChecked:
            return "Room"
        if self.mode_spaces_rb.IsChecked:
            return "Space"
        return "Both"

    def get_search_text(self):
        return str(self.search_tb.Text or "").strip().lower()

    def on_filters_changed(self, sender, args):
        if self._view is not None:
            self._view.Refresh()
            self.spatial_grid.Items.Refresh()

    def on_check_all(self, sender, args):
        for item in self._view:
            item.IsSelected = True
        self.spatial_grid.Items.Refresh()

    def on_uncheck_all(self, sender, args):
        for item in self._view:
            item.IsSelected = False
        self.spatial_grid.Items.Refresh()

    def on_assign_family_to_selected_rows(self, sender, args):
        selected_option = self.bulk_family_combo.SelectedItem
        if selected_option is None or selected_option.Symbol is None:
            forms.alert("Select a family type to assign.", warn_icon=True)
            return

        selected_grid_rows = list(self.spatial_grid.SelectedItems)
        if not selected_grid_rows:
            forms.alert(
                "Select one or more rows in the table first. You can use Shift or Ctrl to select multiple rows.",
                warn_icon=True
            )
            return

        for row in selected_grid_rows:
            row.SelectedFamilyOption = selected_option

        self.spatial_grid.Items.Refresh()

    def on_apply(self, sender, args):
        selected_rows = [row for row in self._all_rows if row.IsSelected]
        if not selected_rows:
            forms.alert("Select at least one Room or Space.", warn_icon=True)
            return

        rows_without_family = []
        for row in selected_rows:
            if row.SelectedFamilyOption is None or row.SelectedFamilyOption.Symbol is None:
                rows_without_family.append(row)

        if rows_without_family:
            sample_ids = ", ".join([row.ElementIdText for row in rows_without_family[:5]])
            forms.alert(
                "Select a family type for each checked Room or Space.\n\nMissing family on element ids: {}".format(sample_ids),
                warn_icon=True
            )
            return

        for row in selected_rows:
            is_valid_symbol, reason = validate_selected_symbol(row.SelectedFamilyOption.Symbol)
            if not is_valid_symbol:
                forms.alert(
                    "Selected family type is not compatible for element id {}:\n\n{}".format(
                        row.ElementIdText,
                        reason
                    ),
                    warn_icon=True
                )
                return

        try:
            x_offset = parse_offset_value(doc, self.x_offset_tb.Text, "X")
            y_offset = parse_offset_value(doc, self.y_offset_tb.Text, "Y")
            z_offset = parse_offset_value(doc, self.z_offset_tb.Text, "Z")
        except ValueError as parse_error:
            forms.alert(str(parse_error), warn_icon=True)
            return

        self.result = {
            "rows": selected_rows,
            "offset_xyz": build_offset_xyz(x_offset, y_offset, z_offset),
        }
        self.Close()

    def on_cancel(self, sender, args):
        self.result = None
        self.Close()


# -----------------------------------------------------------------------------
# Placement execution
# -----------------------------------------------------------------------------


def place_instances(document, levels, selected_rows, offset_xyz):
    results = []

    transaction = Transaction(document, "Place In Rooms / Spaces - PYLAB")
    transaction.Start()

    try:
        symbols_to_activate = []
        seen_symbol_ids = set()
        for row in selected_rows:
            symbol = row.SelectedFamilyOption.Symbol
            symbol_id = symbol.Id.IntegerValue
            if symbol_id not in seen_symbol_ids:
                seen_symbol_ids.add(symbol_id)
                symbols_to_activate.append(symbol)

        did_activate_symbol = False
        for symbol in symbols_to_activate:
            if not symbol.IsActive:
                symbol.Activate()
                did_activate_symbol = True
        if did_activate_symbol:
            document.Regenerate()

        for row in selected_rows:
            subtransaction = SubTransaction(document)
            subtransaction.Start()

            try:
                symbol = row.SelectedFamilyOption.Symbol
                family_name = row.SelectedFamilyOption.DisplayName
                target_point, reference_point, error_message = get_target_center_point(row.ElementRef, offset_xyz)
                if target_point is None:
                    raise Exception(error_message)

                level = get_best_level(document, row.ElementRef, levels, reference_point or target_point)
                if level is None:
                    raise Exception("Could not determine a placement level.")

                instance, placement_status, warning_message = place_and_center_instance(
                    document,
                    row.ElementRef,
                    symbol,
                    level,
                    target_point
                )
                write_instance_parameters(instance, row)

                subtransaction.Commit()
                results.append(
                    PlacementResult(
                        row=row,
                        family_name=family_name,
                        status=placement_status,
                        instance_id=instance.Id.IntegerValue,
                        error_message="",
                        warning_message=warning_message
                    )
                )
            except Exception as row_error:
                subtransaction.RollBack()
                results.append(
                    PlacementResult(
                        row=row,
                        family_name=row.SelectedFamilyOption.DisplayName,
                        status="Failed",
                        instance_id=None,
                        error_message=str(row_error)
                    )
                )

        transaction.Commit()
    except Exception:
        transaction.RollBack()
        raise

    return results


# -----------------------------------------------------------------------------
# Output summary
# -----------------------------------------------------------------------------


def print_results_table(title_text, columns, table_data):
    if not table_data:
        return

    output.print_md("### {}".format(title_text))
    try:
        output.print_table(table_data=table_data, columns=columns)
    except Exception:
        for row_data in table_data:
            output.print_md("- {}".format(" | ".join([str(value) for value in row_data])))


def print_summary(selected_rows, results):
    placed_results = [result for result in results if result.status in ["Placed", "Placed with warning"]]
    placed_clean_results = [result for result in results if result.status == "Placed"]
    placed_warning_results = [result for result in results if result.status == "Placed with warning"]
    failed_results = [result for result in results if result.status == "Failed"]
    selected_family_names = sorted(set([
        row.SelectedFamilyOption.DisplayName
        for row in selected_rows
        if row.SelectedFamilyOption is not None
    ]))

    output.print_md("## Place in Rooms / Spaces")
    output.print_md("**Selected family types:** {}".format(", ".join(selected_family_names)))
    output.print_md("**Total selected:** {}".format(len(selected_rows)))
    output.print_md("**Total placed:** {}".format(len(placed_results)))
    output.print_md("**Total placed cleanly:** {}".format(len(placed_clean_results)))
    output.print_md("**Total placed with warning:** {}".format(len(placed_warning_results)))
    output.print_md("**Total failed:** {}".format(len(failed_results)))

    success_rows = []
    for result in placed_results:
        success_rows.append([
            result.row.SpatialType,
            result.row.Number,
            result.row.Name,
            result.family_name,
            result.row.LevelName,
            result.row.ElementIdValue,
            result.instance_id,
            result.status,
            result.warning_message,
        ])

    failure_rows = []
    for result in failed_results:
        failure_rows.append([
            result.row.SpatialType,
            result.row.Number,
            result.row.Name,
            result.family_name,
            result.row.LevelName,
            result.row.ElementIdValue,
            result.status,
            result.error_message,
        ])

    print_results_table(
        "Successful Placements",
        ["Type", "Number", "Name", "Family Type", "Level", "Spatial Id", "Placed Instance Id", "Status", "Warning"],
        success_rows
    )
    print_results_table(
        "Failed Placements",
        ["Type", "Number", "Name", "Family Type", "Level", "Spatial Id", "Status", "Error"],
        failure_rows
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main():
    levels = get_sorted_levels(doc)
    spatial_rows = collect_spatial_rows(doc, levels)
    if not spatial_rows:
        forms.alert(
            "No placed Rooms or MEP Spaces with usable insertion points were found in the active model.",
            exitscript=True
        )
        return

    family_options = get_compatible_family_symbol_options(doc)
    if not family_options:
        forms.alert(
            "No compatible non-hosted, one-level-based model family types were found in the active model.",
            exitscript=True
        )
        return

    xaml_file = os.path.join(os.path.dirname(__file__), "PlaceInRoomsSpacesWindow.xaml")
    window = PlaceInRoomsSpacesWindow(
        xaml_file=xaml_file,
        rows=spatial_rows,
        family_options=family_options,
        units_label=get_project_length_units_label(doc),
    )
    window.ShowDialog()

    if not window.result:
        return

    selected_rows = window.result["rows"]
    offset_xyz = window.result["offset_xyz"]

    try:
        results = place_instances(doc, levels, selected_rows, offset_xyz)
    except Exception as execution_error:
        forms.alert(
            "Placement failed before completion:\n\n{}".format(execution_error),
            warn_icon=True,
            exitscript=True
        )
        return

    print_summary(selected_rows, results)


if __name__ == "__main__":
    main()
