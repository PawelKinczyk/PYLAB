from collections import defaultdict

import clr
from Autodesk.Revit.DB import BuiltInParameter
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms
from pyrevit import revit

clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import Clipboard


doc = revit.doc
uidoc = revit.uidoc


ALLOWED_CATEGORIES = set([
    "Pipes",
    "Pipe Fittings",
    "Pipe Accessories",
    "Ducts",
    "Duct Fittings",
    "Duct Accessories",
    "Walls",
    "Windows",
    "Doors",
    "Mechanical Equipment",
    "Generic Models",
])

NEUTRAL_CATEGORIES = set(["Mechanical Equipment", "Generic Models"])

PIPE_MAIN = set(["Pipes", "Pipe Fittings", "Pipe Accessories"])
DUCT_MAIN = set(["Ducts", "Duct Fittings", "Duct Accessories"])
WALL_MAIN = set(["Walls", "Windows", "Doors"])


class MultiCategorySelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not element or not element.Category:
            return False
        return element.Category.Name in ALLOWED_CATEGORIES

    def AllowReference(self, reference, point):
        return True


def get_category_name(element):
    if not element or not element.Category:
        return None
    return element.Category.Name


def get_detected_families(categories):
    families = set()
    for category_name in categories:
        if category_name in NEUTRAL_CATEGORIES:
            continue
        if category_name in PIPE_MAIN:
            families.add("Pipe")
        elif category_name in DUCT_MAIN:
            families.add("Duct")
        elif category_name in WALL_MAIN:
            families.add("Wall")
    return families


def get_main_family(categories):
    families = get_detected_families(categories)
    if len(families) == 1:
        return list(families)[0]
    return None


def to_meters(length_feet):
    return length_feet * 0.3048


def to_mm(value_feet):
    return int(round(value_feet * 304.8))


def get_param_double(element, bip):
    param = element.get_Parameter(bip)
    if param:
        try:
            return param.AsDouble()
        except Exception:
            return None
    return None


def get_length_feet(element):
    length_val = get_param_double(element, BuiltInParameter.CURVE_ELEM_LENGTH)
    if length_val is not None:
        return length_val

    length_param = element.LookupParameter("Length")
    if length_param:
        try:
            return length_param.AsDouble()
        except Exception:
            return None
    return None


def get_type_name(element):
    try:
        element_type = doc.GetElement(element.GetTypeId())
        if element_type:
            return element_type.FamilyName + " : " + element_type.get_Name()
    except Exception:
        pass
    return element.Name


def pipe_group_key(element):
    type_name = get_type_name(element)
    diameter = get_param_double(element, BuiltInParameter.RBS_PIPE_DIAMETER_PARAM)
    if diameter is None:
        diameter = get_param_double(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)

    if diameter is None or diameter <= 0:
        return "{} | Unknown Size".format(type_name)

    return "{} | Dia {} mm".format(type_name, to_mm(diameter))


def duct_group_key(element):
    type_name = get_type_name(element)
    diameter = get_param_double(element, BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
    if diameter is not None and diameter > 0:
        return "{} | Dia {} mm".format(type_name, to_mm(diameter))

    width = get_param_double(element, BuiltInParameter.RBS_CURVE_WIDTH_PARAM)
    height = get_param_double(element, BuiltInParameter.RBS_CURVE_HEIGHT_PARAM)
    if width is None or height is None or width <= 0 or height <= 0:
        return "{} | Unknown Size".format(type_name)

    return "{} | {}x{} mm".format(type_name, to_mm(width), to_mm(height))


def wall_group_key(element):
    type_name = get_type_name(element)
    width = None
    try:
        wall_type = doc.GetElement(element.GetTypeId())
        if wall_type:
            width = get_param_double(wall_type, BuiltInParameter.WALL_ATTR_WIDTH_PARAM)
    except Exception:
        width = None

    if width is None or width <= 0:
        return "{} | Unknown Size".format(type_name)

    return "{} | {} mm".format(type_name, to_mm(width))


def build_report(family_name, grouped_lengths_m, grand_total_m, measured_count, skipped_count):
    lines = []
    lines.append("MeasureElem results")
    lines.append("Family: {}".format(family_name))
    lines.append("")
    lines.append("Grouped totals:")

    sorted_items = sorted(grouped_lengths_m.items(), key=lambda x: x[1], reverse=True)
    for key, length_m in sorted_items:
        lines.append("- {} = {:.2f} m".format(key, length_m))

    lines.append("")
    lines.append("Measured elements: {}".format(measured_count))
    lines.append("Skipped elements: {}".format(skipped_count))
    lines.append("TOTAL LENGTH: {:.2f} m".format(grand_total_m))
    return "\n".join(lines)


def copy_to_clipboard(text):
    try:
        Clipboard.SetText(text)
        return True
    except Exception:
        return False


def main():
    try:
        with forms.WarningBar(title="Pick elements to measure"):
            references = uidoc.Selection.PickObjects(ObjectType.Element, MultiCategorySelectionFilter())
    except Exception:
        print("No elements selected")
        return

    if not references:
        print("No elements selected")
        return

    elements = []
    categories = set()
    for reference in references:
        element = doc.GetElement(reference.ElementId)
        if not element:
            continue
        category_name = get_category_name(element)
        if not category_name:
            continue
        if category_name not in ALLOWED_CATEGORIES:
            continue
        elements.append(element)
        categories.add(category_name)

    if not elements:
        print("No elements selected")
        return

    detected_families = get_detected_families(categories)
    if len(detected_families) > 1:
        print("Select only one category")
        return
    if len(detected_families) == 0:
        print("No measurable elements selected")
        return

    family_name = list(detected_families)[0]

    grouped_lengths_m = defaultdict(float)
    skipped_count = 0
    measured_count = 0

    for element in elements:
        category_name = get_category_name(element)
        should_measure = (
            (family_name == "Pipe" and category_name == "Pipes") or
            (family_name == "Duct" and category_name == "Ducts") or
            (family_name == "Wall" and category_name == "Walls")
        )
        if not should_measure:
            continue

        try:
            length_feet = get_length_feet(element)
            if length_feet is None:
                skipped_count += 1
                continue

            if family_name == "Pipe":
                key = pipe_group_key(element)
            elif family_name == "Duct":
                key = duct_group_key(element)
            else:
                key = wall_group_key(element)

            length_m = to_meters(length_feet)
            grouped_lengths_m[key] += length_m
            measured_count += 1
        except Exception:
            skipped_count += 1

    if measured_count == 0:
        print("No measurable elements selected")
        return

    grand_total_m = sum(grouped_lengths_m.values())
    report = build_report(
        family_name=family_name,
        grouped_lengths_m=grouped_lengths_m,
        grand_total_m=grand_total_m,
        measured_count=measured_count,
        skipped_count=skipped_count,
    )

    print(report)

    if not copy_to_clipboard(report):
        print("Clipboard copy failed")


if __name__ == "__main__":
    main()
