"""Auto-create openings in walls/floors for pipes, ducts, and fittings.

Replaces the Dynamo IND script set (RECT_WALL_MULTI, ROUND_RECT_WALL_amber)
with native Revit API:
- BoundingBoxIntersectsFilter for clash detection (no BimorphNodes)
- element.get_BoundingBox for dimensions (no Dynamo Solid/Cuboid pipeline)
- HostObjectUtils for face references
- SubTransaction per host (Bypass pattern) — individual failures don't abort batch
"""

import datetime
import json
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from Autodesk.Revit.DB import (
    BoundingBoxIntersectsFilter,
    BoundingBoxXYZ,
    BuiltInCategory,
    BuiltInParameter,
    Element,
    ElementId,
    Family,
    FamilyInstance,
    FamilySymbol,
    FilteredElementCollector,
    HostObjectUtils,
    Outline,
    RevitLinkInstance,
    StructuralType,
    SubTransaction,
    Transaction,
    TransactionGroup,
    XYZ,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
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

SCRIPT_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "openings_config.json")

MEP_CATEGORIES = set([
    "Pipes",
    "Pipe Fittings",
    "Pipe Accessories",
    "Ducts",
    "Duct Fittings",
    "Duct Accessories",
    "Cable Trays",
    "Conduits",
])

ROUND_PIPE_PARAMS = [
    BuiltInParameter.RBS_PIPE_OUTER_DIAMETER,
    BuiltInParameter.RBS_PIPE_DIAMETER_PARAM,
]

DUCT_DIAMETER_PARAMS = [
    BuiltInParameter.RBS_CURVE_DIAMETER_PARAM,
]

DUCT_RECT_PARAMS = {
    "width": BuiltInParameter.RBS_CURVE_WIDTH_PARAM,
    "height": BuiltInParameter.RBS_CURVE_HEIGHT_PARAM,
}

DEFAULT_CONFIG = {
    "margin_rect_mm": 10,
    "margin_round_mm": 90,
    "mark_prefix": "-K-",
    "insulation_default": True,
    "default_round_family_name": "",
    "default_rect_family_name": "",
}


def load_config():
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as fh:
                return json.load(fh)
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


class MEPSelectionFilter(ISelectionFilter):
    def AllowElement(self, elem):
        if not elem or not elem.Category:
            return False
        return elem.Category.Name in MEP_CATEGORIES

    def AllowReference(self, ref, point):
        return True


# ---------------------------------------------------------------------------
# Element queries
# ---------------------------------------------------------------------------

def is_round_element(elem):
    """Determine if a pipe/duct element needs a round opening."""
    cat = elem.Category.Name if elem.Category else ""
    if "Pipe" in cat:
        return True
    if "Duct" in cat:
        # Check if duct has diameter param (round/oval) vs width/height (rect)
        for bip in DUCT_DIAMETER_PARAMS:
            p = elem.get_Parameter(bip)
            if p is not None and p.HasValue and p.AsDouble() > 0:
                return True
        return False
    return False


def get_element_diameter(elem):
    """Get outer diameter (feet) of a pipe or round duct."""
    for bip in ROUND_PIPE_PARAMS:
        p = elem.get_Parameter(bip)
        if p is not None and p.HasValue:
            val = p.AsDouble()
            if val > 0:
                return val
    for bip in DUCT_DIAMETER_PARAMS:
        p = elem.get_Parameter(bip)
        if p is not None and p.HasValue:
            val = p.AsDouble()
            if val > 0:
                return val
    return None


def get_element_width_height(elem):
    """Get width and height (feet) of a rectangular duct. Returns (w, h) or None."""
    w_param = elem.get_Parameter(DUCT_RECT_PARAMS["width"])
    h_param = elem.get_Parameter(DUCT_RECT_PARAMS["height"])
    if (
        w_param is not None
        and h_param is not None
        and w_param.HasValue
        and h_param.HasValue
    ):
        return w_param.AsDouble(), h_param.AsDouble()
    return None


def get_element_bbox(elem):
    """Get element bounding box. Returns (min_xyz, max_xyz) or None."""
    bbox = elem.get_BoundingBox(None)
    if bbox is None:
        return None
    return bbox.Min, bbox.Max


def get_insulation_thickness(elem):
    """Get insulation thickness (feet). Returns 0 if none."""
    try:
        p = elem.get_Parameter(BuiltInParameter.RBS_INSULATION_THICKNESS)
        if p is not None and p.HasValue:
            return p.AsDouble()
    except Exception:
        pass
    return 0.0


def get_element_center(elem):
    """Get approximate center point of an element."""
    bbox = elem.get_BoundingBox(None)
    if bbox is None:
        loc = elem.Location
        if hasattr(loc, "Origin"):
            return loc.Origin
        if hasattr(loc, "Curve"):
            curve = loc.Curve
            return (curve.GetEndPoint(0) + curve.GetEndPoint(1)) / 2.0
        return XYZ(0, 0, 0)
    return (bbox.Min + bbox.Max) / 2.0


def mm_to_feet(mm_val):
    return float(mm_val) / 304.8


def feet_to_mm(ft_val):
    return int(round(ft_val * 304.8))


# ---------------------------------------------------------------------------
# Host detection
# ---------------------------------------------------------------------------

def find_wall_hosts(elem_center, elem_bbox, tolerance_ft, include_linked):
    """Find walls that intersect with the element's expanded bounding box."""
    return _find_hosts(
        elem_center,
        elem_bbox,
        tolerance_ft,
        BuiltInCategory.OST_Walls,
        include_linked,
    )


def find_floor_hosts(elem_center, elem_bbox, tolerance_ft, include_linked):
    """Find floors that intersect with the element's expanded bounding box."""
    return _find_hosts(
        elem_center,
        elem_bbox,
        tolerance_ft,
        BuiltInCategory.OST_Floors,
        include_linked,
    )


def _find_hosts(elem_center, elem_bbox, tolerance_ft, category, include_linked):
    """Generic host detection via BoundingBoxIntersectsFilter."""
    if elem_bbox is None:
        return []

    min_pt = elem_bbox[0] - XYZ(tolerance_ft, tolerance_ft, tolerance_ft)
    max_pt = elem_bbox[1] + XYZ(tolerance_ft, tolerance_ft, tolerance_ft)
    outline = Outline(min_pt, max_pt)
    bbox_filter = BoundingBoxIntersectsFilter(outline)

    hosts = []

    # Local document
    collector = (
        FilteredElementCollector(doc)
        .OfCategory(category)
        .OfClass(Element)
        .WherePasses(bbox_filter)
    )
    for host in collector:
        if host is not None:
            hosts.append(("local", doc, host))

    # Linked models
    if include_linked:
        links = FilteredElementCollector(doc).OfClass(RevitLinkInstance)
        for link in links:
            try:
                link_doc = link.GetLinkDocument()
                if link_doc is None:
                    continue
                link_collector = (
                    FilteredElementCollector(link_doc)
                    .OfCategory(category)
                    .OfClass(Element)
                    .WherePasses(bbox_filter)
                )
                for host in link_collector:
                    if host is not None:
                        hosts.append(("link", link_doc, host))
            except Exception:
                pass

    return hosts


# ---------------------------------------------------------------------------
# Opening dimension calculation
# ---------------------------------------------------------------------------

def calc_round_opening(elem, margin_mm, include_insulation):
    """Calculate round opening diameter (feet)."""
    diam_ft = get_element_diameter(elem)
    if diam_ft is None:
        return None

    margin_ft = mm_to_feet(margin_mm)
    total = diam_ft + margin_ft * 2

    if include_insulation:
        insul = get_insulation_thickness(elem)
        total += insul * 2  # both sides

    return total


def calc_rect_opening(elem, margin_mm, include_insulation):
    """Calculate rectangular opening dimensions (width_ft, height_ft)."""
    wh = get_element_width_height(elem)
    if wh is not None:
        w_ft, h_ft = wh
    else:
        bbox = get_element_bbox(elem)
        if bbox is None:
            return None
        w_ft = (bbox[1].X - bbox[0].X)
        h_ft = (bbox[1].Z - bbox[0].Z)
        if w_ft <= 0:
            # Try Y direction
            w_ft = (bbox[1].Y - bbox[0].Y)

    margin_ft = mm_to_feet(margin_mm)

    if include_insulation:
        insul = get_insulation_thickness(elem)
        # Dynamo formula: x + i/10 + 2*it where i=insulation in mm, it=insulation thickness
        insul_mm = feet_to_mm(insul)
        extra = mm_to_feet(insul_mm / 10.0) + insul * 2
    else:
        extra = 0

    w_ft = w_ft + margin_ft * 2 + extra
    h_ft = h_ft + margin_ft * 2 + extra

    return w_ft, h_ft


# ---------------------------------------------------------------------------
# Opening placement
# ---------------------------------------------------------------------------

def get_host_thickness(host):
    """Get wall or floor thickness (feet)."""
    # Wall
    try:
        wall_type = doc.GetElement(host.GetTypeId())
        if wall_type:
            p = wall_type.get_Parameter(BuiltInParameter.WALL_ATTR_WIDTH_PARAM)
            if p is not None and p.HasValue:
                return p.AsDouble()
    except Exception:
        pass

    # Floor
    try:
        p = host.get_Parameter(BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM)
        if p is not None and p.HasValue:
            return p.AsDouble()
    except Exception:
        pass

    return 0.5  # fallback ~150mm


def get_host_face_reference(host, point):
    """Get a face reference on the host closest to the given point."""
    try:
        cat = host.Category
        cat_id = cat.Id.IntegerValue if cat else 0

        # Floor → top face
        wall_cat = int(BuiltInCategory.OST_Walls)
        floor_cat = int(BuiltInCategory.OST_Floors)

        if cat_id == floor_cat:
            faces = HostObjectUtils.GetTopFaces(host)
            if faces and faces.Count > 0:
                return faces[0]

        # Wall → closest side face
        if cat_id == wall_cat:
            faces = HostObjectUtils.GetSideFaces(host)
            if faces and faces.Count > 0:
                # Return first face (simplest) — family rotation handles alignment
                return faces[0]
    except Exception:
        pass

    return None


def place_opening_family(host_doc, host, elem_center, symbol, width_ft, height_ft,
                         diameter_ft, thickness_ft, is_round, mark_prefix):
    """Place a face-based opening family instance on the host.

    Returns the FamilyInstance or raises exception.
    """
    face_ref = get_host_face_reference(host, elem_center)
    if face_ref is None:
        raise Exception("Could not find host face reference")

    # Project the element center onto the face
    point = elem_center

    # Reference direction (X axis by default, rotation handled below)
    ref_dir = XYZ(1, 0, 0)

    instance = host_doc.Create.NewFamilyInstance(
        face_ref, point, ref_dir, symbol
    )

    if instance is None:
        raise Exception("FamilyInstance creation returned None")

    # Set IND_ parameters
    if is_round:
        _set_param(instance, "IND_Diameter", diameter_ft)
    else:
        _set_param(instance, "IND_Width", width_ft)
        _set_param(instance, "IND_Height", height_ft)

    _set_param(instance, "IND_Thickness", thickness_ft)
    _set_param(instance, "IND_STATUS", str(datetime.date.today().isocalendar()[1]))

    # Mark
    _set_param(instance, "Mark", mark_prefix)

    return instance


def _set_param(elem, param_name, value):
    """Set a parameter by name. Silently ignores missing params."""
    param = elem.LookupParameter(param_name)
    if param is not None and not param.IsReadOnly:
        try:
            if isinstance(value, float):
                param.Set(value)
            else:
                param.SetValueString(str(value))
        except Exception:
            try:
                param.SetValueString(str(value))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

class OpeningsCreatorForm(Form):
    def __init__(self, round_symbols, rect_symbols, config):
        Form.__init__(self)
        self.Text = "Openings Creator"
        self.Size = Size(500, 520)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._round_symbols = round_symbols  # [(id, display, symbol), ...]
        self._rect_symbols = rect_symbols
        self._config = config
        self._selected_elements = []

        self._build_ui()

    def _build_ui(self):
        y = 12

        # Pick elements button
        self._pick_btn = Button()
        self._pick_btn.Text = "Pick Pipes/Ducts..."
        self._pick_btn.Location = Point(12, y)
        self._pick_btn.Size = Size(150, 28)
        self._pick_btn.Click += self._on_pick_elements
        self.Controls.Add(self._pick_btn)

        self._pick_label = Label()
        self._pick_label.Text = "0 elements selected"
        self._pick_label.Location = Point(172, y + 5)
        self._pick_label.Size = Size(300, 20)
        self.Controls.Add(self._pick_label)
        y += 40

        # Round family dropdown
        lbl = Label()
        lbl.Text = "Round opening family:"
        lbl.Location = Point(12, y + 3)
        lbl.Size = Size(140, 20)
        self.Controls.Add(lbl)

        self._round_combo = ComboBox()
        self._round_combo.Location = Point(155, y)
        self._round_combo.Size = Size(320, 23)
        self._round_combo.DropDownStyle = ComboBoxStyle.DropDownList
        for sid, display, sym in self._round_symbols:
            self._round_combo.Items.Add(display)
        if self._round_combo.Items.Count > 0:
            default_name = self._config.get("default_round_family_name", "")
            idx = 0
            for i, (sid, disp, sym) in enumerate(self._round_symbols):
                if disp == default_name:
                    idx = i
                    break
            self._round_combo.SelectedIndex = idx
        self.Controls.Add(self._round_combo)
        y += 32

        # Rect family dropdown
        lbl2 = Label()
        lbl2.Text = "Rect opening family:"
        lbl2.Location = Point(12, y + 3)
        lbl2.Size = Size(140, 20)
        self.Controls.Add(lbl2)

        self._rect_combo = ComboBox()
        self._rect_combo.Location = Point(155, y)
        self._rect_combo.Size = Size(320, 23)
        self._rect_combo.DropDownStyle = ComboBoxStyle.DropDownList
        for sid, display, sym in self._rect_symbols:
            self._rect_combo.Items.Add(display)
        if self._rect_combo.Items.Count > 0:
            default_name = self._config.get("default_rect_family_name", "")
            idx = 0
            for i, (sid, disp, sym) in enumerate(self._rect_symbols):
                if disp == default_name:
                    idx = i
                    break
            self._rect_combo.SelectedIndex = idx
        self.Controls.Add(self._rect_combo)
        y += 38

        # Categories
        cat_lbl = Label()
        cat_lbl.Text = "Host categories:"
        cat_lbl.Location = Point(12, y + 3)
        cat_lbl.Size = Size(110, 20)
        self.Controls.Add(cat_lbl)

        self._walls_cb = CheckBox()
        self._walls_cb.Text = "Walls"
        self._walls_cb.Location = Point(125, y)
        self._walls_cb.Size = Size(80, 23)
        self._walls_cb.Checked = True
        self.Controls.Add(self._walls_cb)

        self._floors_cb = CheckBox()
        self._floors_cb.Text = "Floors"
        self._floors_cb.Location = Point(210, y)
        self._floors_cb.Size = Size(80, 23)
        self.Controls.Add(self._floors_cb)

        self._linked_cb = CheckBox()
        self._linked_cb.Text = "Include linked models"
        self._linked_cb.Location = Point(300, y)
        self._linked_cb.Size = Size(180, 23)
        self.Controls.Add(self._linked_cb)
        y += 30

        # Margin
        margin_lbl = Label()
        margin_lbl.Text = "Margin round [mm]:"
        margin_lbl.Location = Point(12, y + 3)
        margin_lbl.Size = Size(120, 20)
        self.Controls.Add(margin_lbl)

        self._margin_round = TextBox()
        self._margin_round.Location = Point(135, y)
        self._margin_round.Size = Size(60, 23)
        self._margin_round.Text = str(self._config.get("margin_round_mm", 90))
        self.Controls.Add(self._margin_round)

        margin2_lbl = Label()
        margin2_lbl.Text = "rect [mm]:"
        margin2_lbl.Location = Point(205, y + 3)
        margin2_lbl.Size = Size(60, 20)
        self.Controls.Add(margin2_lbl)

        self._margin_rect = TextBox()
        self._margin_rect.Location = Point(270, y)
        self._margin_rect.Size = Size(60, 23)
        self._margin_rect.Text = str(self._config.get("margin_rect_mm", 10))
        self.Controls.Add(self._margin_rect)
        y += 30

        # Insulation checkbox
        self._insul_cb = CheckBox()
        self._insul_cb.Text = "Include pipe/duct insulation thickness"
        self._insul_cb.Location = Point(12, y)
        self._insul_cb.Size = Size(250, 23)
        self._insul_cb.Checked = self._config.get("insulation_default", True)
        self.Controls.Add(self._insul_cb)
        y += 30

        # Mark prefix
        mark_lbl = Label()
        mark_lbl.Text = "Mark prefix:"
        mark_lbl.Location = Point(12, y + 3)
        mark_lbl.Size = Size(80, 20)
        self.Controls.Add(mark_lbl)

        self._mark_prefix = TextBox()
        self._mark_prefix.Location = Point(95, y)
        self._mark_prefix.Size = Size(80, 23)
        self._mark_prefix.Text = str(self._config.get("mark_prefix", "-K-"))
        self.Controls.Add(self._mark_prefix)
        y += 38

        # Generate button
        gen_btn = Button()
        gen_btn.Text = "Generate Openings"
        gen_btn.Location = Point(250, y)
        gen_btn.Size = Size(130, 32)
        gen_btn.Click += self._on_generate
        self.Controls.Add(gen_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(390, y)
        close_btn.Size = Size(80, 32)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

    def _on_pick_elements(self, sender, event_args):
        try:
            with forms.WarningBar(title="Pick pipes/ducts for opening creation"):
                refs = uidoc.Selection.PickObjects(
                    ObjectType.Element, MEPSelectionFilter()
                )
            self._selected_elements = [doc.GetElement(r.ElementId) for r in refs]
            self._selected_elements = [e for e in self._selected_elements if e is not None]
            self._pick_label.Text = "{} elements selected".format(
                len(self._selected_elements)
            )
        except Exception:
            pass

    def _get_symbol(self, combo, symbols):
        idx = combo.SelectedIndex
        if idx < 0 or idx >= len(symbols):
            return None
        return symbols[idx][2]

    def _on_generate(self, sender, event_args):
        if not self._selected_elements:
            MessageBox.Show(
                self, "Pick pipes/ducts first.",
                "No elements", MessageBoxButtons.OK, MessageBoxIcon.Warning,
            )
            return

        round_sym = self._get_symbol(self._round_combo, self._round_symbols)
        rect_sym = self._get_symbol(self._rect_combo, self._rect_symbols)

        if round_sym is None and rect_sym is None:
            MessageBox.Show(
                self, "Select at least one opening family.",
                "No family", MessageBoxButtons.OK, MessageBoxIcon.Warning,
            )
            return

        margin_round_mm = int(self._margin_round.Text) if self._margin_round.Text.isdigit() else 90
        margin_rect_mm = int(self._margin_rect.Text) if self._margin_rect.Text.isdigit() else 10
        include_insul = self._insul_cb.Checked
        check_walls = self._walls_cb.Checked
        check_floors = self._floors_cb.Checked
        include_linked = self._linked_cb.Checked
        mark_prefix = self._mark_prefix.Text or "-K-"

        if not check_walls and not check_floors:
            MessageBox.Show(
                self, "Select at least one host category (Walls/Floors).",
                "No categories", MessageBoxButtons.OK, MessageBoxIcon.Warning,
            )
            return

        self.Hide()

        created = 0
        skipped = 0
        errors = 0

        with TransactionGroup(doc, "Openings Creator") as tg:
            tg.Start()

            for elem in self._selected_elements:
                elem_center = get_element_center(elem)
                elem_bbox = get_element_bbox(elem)
                is_round = is_round_element(elem)

                # Determine symbol
                symbol = round_sym if is_round else rect_sym
                if symbol is None:
                    skipped += 1
                    continue

                # Collect hosts
                hosts = []
                if check_walls:
                    hosts.extend(
                        find_wall_hosts(elem_center, elem_bbox, mm_to_feet(50), include_linked)
                    )
                if check_floors:
                    hosts.extend(
                        find_floor_hosts(elem_center, elem_bbox, mm_to_feet(50), include_linked)
                    )

                # Deduplicate hosts by id
                seen = set()
                unique_hosts = []
                for source, hdoc, host in hosts:
                    key = (source, host.Id.IntegerValue)
                    if key not in seen:
                        seen.add(key)
                        unique_hosts.append((source, hdoc, host))

                for source, hdoc, host in unique_hosts:
                    with SubTransaction(doc) as st:
                        st.Start()
                        try:
                            # Calculate dimensions
                            thickness_ft = get_host_thickness(host)

                            if is_round:
                                diam_ft = calc_round_opening(
                                    elem, margin_round_mm, include_insul
                                )
                                if diam_ft is None:
                                    st.RollBack()
                                    skipped += 1
                                    continue
                                instance = place_opening_family(
                                    hdoc, host, elem_center, symbol,
                                    None, None, diam_ft, thickness_ft,
                                    True, mark_prefix,
                                )
                            else:
                                wh = calc_rect_opening(
                                    elem, margin_rect_mm, include_insul
                                )
                                if wh is None:
                                    st.RollBack()
                                    skipped += 1
                                    continue
                                w_ft, h_ft = wh
                                instance = place_opening_family(
                                    hdoc, host, elem_center, symbol,
                                    w_ft, h_ft, None, thickness_ft,
                                    False, mark_prefix,
                                )

                            st.Commit()
                            created += 1
                        except Exception as exc:
                            st.RollBack()
                            errors += 1

            if errors > 0 and created == 0:
                tg.RollBack()
                output.print_md("**Rolled back** — all operations failed.")
            else:
                tg.Assimilate()

        output.print_md("# Openings Creator — Results")
        output.print_md(
            "**{} created** | {} skipped | {} errors".format(created, skipped, errors)
        )
        self.Close()


def get_opening_families(category_keyword):
    """Find face-based family symbols matching a keyword in the name."""
    symbols = FilteredElementCollector(doc).OfClass(FamilySymbol)
    results = []
    for sym in symbols:
        if sym is None:
            continue
        try:
            family = sym.Family
            fam_name = family.Name.lower() if family else ""
            if category_keyword in fam_name:
                display = "{} : {}".format(
                    family.Name if family else "?",
                    sym.get_Name(),
                )
                results.append((sym.Id, display, sym))
        except Exception:
            pass
    return sorted(results, key=lambda s: s[1].lower())


def main():
    config = load_config()

    round_symbols = get_opening_families("round") or get_opening_families("okr")
    rect_symbols = get_opening_families("rect") or get_opening_families("prost")

    # Fallback: if no filtered results, show all GenericModel face-based families
    if not round_symbols or not rect_symbols:
        all_symbols = get_opening_families("")
        if not round_symbols:
            round_symbols = all_symbols
        if not rect_symbols:
            rect_symbols = all_symbols

    if not round_symbols and not rect_symbols:
        forms.alert(
            "No opening families loaded in this project.\n"
            "Load a face-based family with IND_Diameter/IND_Width/IND_Height parameters.",
            title="Openings Creator",
        )
        return

    form = OpeningsCreatorForm(round_symbols, rect_symbols, config)
    form.ShowDialog()


if __name__ == "__main__":
    main()
