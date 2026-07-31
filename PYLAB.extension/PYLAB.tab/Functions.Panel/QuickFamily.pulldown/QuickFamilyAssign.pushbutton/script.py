"""Place a Generic Model family instance with specified X/Y/Z dimensions.

Select family type, enter dimensions, pick insertion point.
Detects type-level dimension parameters and duplicates the symbol to avoid
mutating all instances of the same type.
"""

import json
import math
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    Family,
    FamilySymbol,
    FilteredElementCollector,
    StructuralType,
    Transaction,
    XYZ,
)
from Autodesk.Revit.UI.Selection import ObjectType

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
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

from pyrevit import forms
from pyrevit import revit
from pyrevit import script

doc = revit.doc
uidoc = revit.uidoc

SCRIPT_DIR = os.path.dirname(__file__)
PULLDOWN_DIR = os.path.dirname(SCRIPT_DIR)
if PULLDOWN_DIR not in sys.path:
    sys.path.append(PULLDOWN_DIR)

# Personal preference: last-used family symbol
APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "pyRevit",
    "PYLAB",
    "QuickFamily",
)
LAST_USED_FILE = os.path.join(APP_DATA_DIR, "last_used.json")


def load_last_used():
    """Load last-used family symbol name from %APPDATA%."""
    try:
        if os.path.isfile(LAST_USED_FILE):
            with open(LAST_USED_FILE, "r") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {}


def save_last_used(data):
    """Save last-used family symbol name to %APPDATA%."""
    try:
        if not os.path.isdir(APP_DATA_DIR):
            os.makedirs(APP_DATA_DIR)
        with open(LAST_USED_FILE, "w") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


def get_generic_model_symbols():
    """Get all GenericModel FamilySymbols loaded in the project."""
    symbols = []
    collector = (
        FilteredElementCollector(doc)
        .OfClass(FamilySymbol)
        .OfCategory(BuiltInCategory.OST_GenericModel)
    )
    for sym in collector:
        if sym is None:
            continue
        family_name = ""
        try:
            family = sym.Family
            family_name = family.Name if family else ""
        except Exception:
            pass
        display = "{} : {}".format(family_name, sym.get_Name())
        symbols.append((sym.Id, display, sym))
    return sorted(symbols, key=lambda s: s[1].lower())


def is_type_level_param(symbol, param_name):
    """Check if a parameter with the given name exists and is type-level on this symbol."""
    param = symbol.LookupParameter(param_name)
    if param is None:
        # Try looking up on the symbol itself
        for p in symbol.Parameters:
            if p.Definition.Name == param_name:
                param = p
                break
    if param is None:
        return False
    # Parameters on FamilySymbol are type-level by definition
    # Instance parameters would be on FamilyInstance
    return True


def duplicate_symbol_for_size(symbol, width, depth, height):
    """Duplicate the symbol (creates a new type) for the given dimensions.

    Returns the duplicated symbol. Sets WIDTH, DEPTH, HEIGHT params.
    """
    new_name = "{}_W{}_D{}_H{}".format(
        symbol.get_Name(),
        int(round(width * 304.8)),
        int(round(depth * 304.8)),
        int(round(height * 304.8)),
    )

    try:
        new_symbol = symbol.Duplicate(new_name)
    except Exception:
        # Duplicate failed — fall back to original symbol (will mutate all instances)
        return symbol, False

    # Set dimension parameters on the duplicated type
    dimension_params = ["WIDTH", "DEPTH", "HEIGHT", "Width", "Depth", "Height"]
    values = {"WIDTH": width, "Width": width, "DEPTH": depth, "Depth": depth, "HEIGHT": height, "Height": height}

    for param_name in dimension_params:
        param = new_symbol.LookupParameter(param_name)
        if param is not None and not param.IsReadOnly:
            try:
                param.Set(value=values.get(param_name, 0))
            except Exception:
                pass

    return new_symbol, True


def convert_mm_to_feet(mm_val):
    """Convert millimeters to Revit internal units (feet)."""
    return float(mm_val) / 304.8


class QuickFamilyAssignForm(Form):
    """WinForms dialog for Quick Family Assign."""

    def __init__(self, symbols):
        Form.__init__(self)
        self.Text = "Quick Family Assign"
        self.Size = Size(420, 270)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._symbols = symbols
        self._symbol_ids = [s[0] for s in symbols]
        self._symbol_objects = {s[0]: s[2] for s in symbols}
        self._selected_symbol_id = None

        self._build_ui()

    def _build_ui(self):
        y = 12

        # Family symbol dropdown
        sym_label = Label()
        sym_label.Text = "Family:"
        sym_label.Location = Point(12, y + 3)
        sym_label.Size = Size(50, 20)
        self.Controls.Add(sym_label)

        self._sym_combo = ComboBox()
        self._sym_combo.Location = Point(65, y)
        self._sym_combo.Size = Size(325, 23)
        self._sym_combo.DropDownStyle = ComboBoxStyle.DropDownList
        for sym_id, display, sym in self._symbols:
            self._sym_combo.Items.Add(display)
        self._sym_combo.SelectedIndexChanged += self._on_symbol_changed
        if self._symbols:
            # Pre-select last used
            last = load_last_used()
            last_name = last.get("symbol_name", "")
            last_idx = 0
            for i, (sid, disp, sym) in enumerate(self._symbols):
                if disp == last_name:
                    last_idx = i
                    break
            self._sym_combo.SelectedIndex = last_idx
        self.Controls.Add(self._sym_combo)
        y += 35

        # X dimension
        self._add_dim_field("Width X (mm):", y, "_x_text")
        y += 28

        # Y dimension
        self._add_dim_field("Depth Y (mm):", y, "_y_text")
        y += 28

        # Z dimension
        self._add_dim_field("Height Z (mm):", y, "_z_text")
        y += 40

        # Place button
        place_btn = Button()
        place_btn.Text = "Place"
        place_btn.Location = Point(200, y)
        place_btn.Size = Size(90, 30)
        place_btn.Click += self._on_place
        self.Controls.Add(place_btn)

        # Close button
        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(300, y)
        close_btn.Size = Size(90, 30)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

    def _add_dim_field(self, label_text, y, attr_name):
        lbl = Label()
        lbl.Text = label_text
        lbl.Location = Point(12, y + 3)
        lbl.Size = Size(100, 20)
        self.Controls.Add(lbl)

        tb = TextBox()
        tb.Location = Point(115, y)
        tb.Size = Size(80, 23)
        tb.Text = "600"
        self.Controls.Add(tb)
        setattr(self, attr_name, tb)

    def _on_symbol_changed(self, sender, event_args):
        idx = self._sym_combo.SelectedIndex
        if 0 <= idx < len(self._symbols):
            self._selected_symbol_id = self._symbols[idx][0]

    def _get_dimension_value(self, textbox, default_mm=600):
        """Parse dimension textbox to feet."""
        try:
            val_mm = float(textbox.Text)
            if val_mm <= 0:
                MessageBox.Show(
                    self,
                    "Dimensions must be positive.",
                    "Invalid input",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning,
                )
                return None
            return convert_mm_to_feet(val_mm)
        except (ValueError, TypeError):
            MessageBox.Show(
                self,
                "Enter valid numeric values for dimensions.",
                "Invalid input",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return None

    def _on_place(self, sender, event_args):
        if self._selected_symbol_id is None:
            if self._symbols:
                self._selected_symbol_id = self._symbols[0][0]
            else:
                MessageBox.Show(
                    self,
                    "No Generic Model families found.",
                    "No families",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning,
                )
                return

        width_ft = self._get_dimension_value(self._x_text)
        if width_ft is None:
            return
        depth_ft = self._get_dimension_value(self._y_text)
        if depth_ft is None:
            return
        height_ft = self._get_dimension_value(self._z_text)
        if height_ft is None:
            return

        symbol = self._symbol_objects.get(self._selected_symbol_id)
        if symbol is None:
            return

        # Activate the symbol
        try:
            symbol.Activate()
        except Exception:
            pass

        # Check for type-level dimension parameters → duplicate
        dimension_param_names = ["WIDTH", "DEPTH", "HEIGHT", "Width", "Depth", "Height"]
        has_type_level_params = any(
            is_type_level_param(symbol, name) for name in dimension_param_names
        )

        if has_type_level_params:
            symbol, was_duplicated = duplicate_symbol_for_size(
                symbol, width_ft, depth_ft, height_ft
            )
            if was_duplicated:
                doc.Regenerate()
            # Activate the (possibly duplicated) symbol
            try:
                symbol.Activate()
            except Exception:
                pass

        # Save last-used
        display_name = self._sym_combo.SelectedItem
        save_last_used({"symbol_name": display_name if display_name else ""})

        # Close dialog — user will now pick placement point
        self.DialogResult = DialogResult.OK
        self.Hide()

        # Pick insertion point
        try:
            with forms.WarningBar(title="Pick insertion point for family"):
                point_ref = uidoc.Selection.PickObject(
                    ObjectType.PointOnElement, "Pick insertion point"
                )
        except Exception:
            MessageBox.Show(
                Form.ActiveForm,
                "Placement cancelled — no point picked.",
                "Cancelled",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information,
            )
            self.Close()
            return

        # Place instance
        point = point_ref.GlobalPoint
        level = doc.ActiveView.GenLevel
        if level is None:
            MessageBox.Show(
                Form.ActiveForm,
                "Active view has no associated level.",
                "Error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error,
            )
            self.Close()
            return

        with Transaction(doc, "Quick Family Assign") as t:
            t.Start()
            try:
                instance = doc.Create.NewFamilyInstance(
                    point, symbol, level, StructuralType.NonStructural
                )
                # Set instance-level params if any
                for param_name in dimension_param_names:
                    param = instance.LookupParameter(param_name)
                    if param is not None and not param.IsReadOnly:
                        val_map = {
                            "WIDTH": width_ft,
                            "Width": width_ft,
                            "DEPTH": depth_ft,
                            "Depth": depth_ft,
                            "HEIGHT": height_ft,
                            "Height": height_ft,
                        }
                        try:
                            param.Set(value=val_map.get(param_name, 0))
                        except Exception:
                            pass
                t.Commit()
                script.get_output().print_md(
                    "Placed: **{}** at ({:.2f}, {:.2f}, {:.2f})".format(
                        symbol.get_Name(),
                        point.X * 304.8,
                        point.Y * 304.8,
                        point.Z * 304.8,
                    )
                )
            except Exception as exc:
                t.RollBack()
                MessageBox.Show(
                    Form.ActiveForm,
                    "Placement failed: {}".format(exc),
                    "Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error,
                )

        self.Close()


def main():
    symbols = get_generic_model_symbols()
    if not symbols:
        forms.alert(
            "No Generic Model families loaded in this project.\n"
            "Load a family first, then use Quick Family Assign.",
            title="Quick Family Assign",
        )
        return

    form = QuickFamilyAssignForm(symbols)
    form.ShowDialog()


if __name__ == "__main__":
    main()
