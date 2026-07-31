"""Generate a new rectangular Generic Model family from template, load and place it.

First run: user picks the Generic Model.rft template file (path stored in %APPDATA%).
Subsequent runs: reuses saved template path.

Creates a simple rectangular extrusion with X/Y/Z, loads into project, places at picked point.
"""

import json
import math
import os
import sys

import clr

clr.AddReference("System.Drawing")
clr.AddReference("System.Windows.Forms")

from Autodesk.Revit.DB import (
    CurveArray,
    CurveArrArray,
    Extrusion,
    Family,
    FamilyInstance,
    FamilySymbol,
    FilteredElementCollector,
    Line,
    Plane,
    SketchPlane,
    StructuralType,
    Transaction,
    XYZ,
)
from Autodesk.Revit.UI.Selection import ObjectType
from pyrevit import forms
from pyrevit import revit
from pyrevit import script

from System.Drawing import Point, Size
from System.Windows.Forms import (
    Application,
    Button,
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
app = revit.app
output = script.get_output()

APP_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "pyRevit",
    "PYLAB",
    "QuickFamily",
)
TEMPLATE_PATH_FILE = os.path.join(APP_DATA_DIR, "template_path.json")


def load_template_path():
    """Load saved template path from %APPDATA%."""
    try:
        if os.path.isfile(TEMPLATE_PATH_FILE):
            with open(TEMPLATE_PATH_FILE, "r") as fh:
                data = json.load(fh)
                return data.get("template_path", "")
    except Exception:
        pass
    return ""


def save_template_path(path):
    """Save template path to %APPDATA%."""
    try:
        if not os.path.isdir(APP_DATA_DIR):
            os.makedirs(APP_DATA_DIR)
        with open(TEMPLATE_PATH_FILE, "w") as fh:
            json.dump({"template_path": path}, fh, indent=2)
    except Exception:
        pass


def convert_mm_to_feet(mm_val):
    """Convert millimeters to feet (Revit internal units)."""
    return float(mm_val) / 304.8


class QuickFamilyGenerateForm(Form):
    """WinForms dialog for Generate new family."""

    def __init__(self, template_path):
        Form.__init__(self)
        self.Text = "Quick Family Generate"
        self.Size = Size(400, 240)
        self.StartPosition = FormStartPosition.CenterParent
        self.FormBorderStyle = FormBorderStyle.FixedDialog
        self.MinimizeBox = False
        self.MaximizeBox = False

        self._template_path = template_path
        self._build_ui()

    def _build_ui(self):
        y = 12

        # Template path
        lbl = Label()
        lbl.Text = "Template:"
        lbl.Location = Point(12, y + 3)
        lbl.Size = Size(60, 20)
        self.Controls.Add(lbl)

        self._template_label = Label()
        self._template_label.Text = self._template_path if self._template_path else "(not set)"
        self._template_label.Location = Point(75, y + 3)
        self._template_label.Size = Size(280, 20)
        self.Controls.Add(self._template_label)

        pick_btn = Button()
        pick_btn.Text = "Pick template..."
        pick_btn.Location = Point(75, y + 25)
        pick_btn.Size = Size(120, 23)
        pick_btn.Click += self._on_pick_template
        self.Controls.Add(pick_btn)
        y += 60

        # Dimensions
        self._add_dim("Width X (mm):", y, "_x_text")
        y += 30
        self._add_dim("Depth Y (mm):", y, "_y_text")
        y += 30
        self._add_dim("Height Z (mm):", y, "_z_text")
        y += 45

        # Generate button
        gen_btn = Button()
        gen_btn.Text = "Generate and Place"
        gen_btn.Location = Point(120, y)
        gen_btn.Size = Size(130, 30)
        gen_btn.Click += self._on_generate
        self.Controls.Add(gen_btn)

        close_btn = Button()
        close_btn.Text = "Close"
        close_btn.Location = Point(260, y)
        close_btn.Size = Size(80, 30)
        close_btn.Click += lambda s, e: self.Close()
        self.Controls.Add(close_btn)

    def _add_dim(self, label_text, y, attr):
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
        setattr(self, attr, tb)

    def _on_pick_template(self, sender, event_args):
        try:
            path = forms.pick_file(file_ext="rft")
            if path:
                self._template_path = path
                self._template_label.Text = os.path.basename(path)
                save_template_path(path)
        except Exception as exc:
            MessageBox.Show(
                self, "Error picking template: {}".format(exc),
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error,
            )

    def _get_dim(self, textbox, label):
        try:
            val_mm = float(textbox.Text)
            if val_mm <= 0:
                raise ValueError("Must be positive")
            return convert_mm_to_feet(val_mm)
        except (ValueError, TypeError):
            MessageBox.Show(
                self,
                "{} must be a positive number.".format(label),
                "Invalid input",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return None

    def _on_generate(self, sender, event_args):
        if not self._template_path or not os.path.isfile(self._template_path):
            MessageBox.Show(
                self,
                "Pick a Generic Model template (.rft) file first.",
                "No template",
                MessageBoxButtons.OK,
                MessageBoxIcon.Warning,
            )
            return

        w = self._get_dim(self._x_text, "Width X")
        if w is None:
            return
        d = self._get_dim(self._y_text, "Depth Y")
        if d is None:
            return
        h = self._get_dim(self._z_text, "Height Z")
        if h is None:
            return

        self.Hide()

        try:
            # 1. Open family document from template
            family_doc = app.NewFamilyDocument(self._template_path)
            if family_doc is None:
                output.print_md("**Error**: Could not open template.")
                self.Close()
                return
        except Exception as exc:
            output.print_md("**Error** opening template: {}".format(exc))
            self.Close()
            return

        try:
            # 2. Create rectangular extrusion
            with Transaction(family_doc, "Create Extrusion") as t:
                t.Start()

                # Create rectangle profile (4 lines)
                half_w = w / 2.0
                half_d = d / 2.0

                p1 = XYZ(-half_w, -half_d, 0)
                p2 = XYZ(half_w, -half_d, 0)
                p3 = XYZ(half_w, half_d, 0)
                p4 = XYZ(-half_w, half_d, 0)

                curve_array = CurveArray()
                curve_array.Append(Line.CreateBound(p1, p2))
                curve_array.Append(Line.CreateBound(p2, p3))
                curve_array.Append(Line.CreateBound(p3, p4))
                curve_array.Append(Line.CreateBound(p4, p1))

                curve_arr_array = CurveArrArray()
                curve_arr_array.Append(curve_array)

                # Sketch plane — XY plane at Z=0
                plane = Plane.CreateByNormalAndOrigin(XYZ(0, 0, 1), XYZ(0, 0, 0))
                sketch_plane = SketchPlane.Create(family_doc, plane)

                # Create extrusion
                extrusion = family_doc.FamilyCreate.NewExtrusion(
                    True,  # is solid
                    curve_arr_array,
                    sketch_plane,
                    h,  # height
                )

                t.Commit()

            # 3. Load family into project
            family = family_doc.LoadFamily(doc)
            if family is None:
                output.print_md("**Error**: Failed to load family into project.")
                family_doc.Close(False)
                self.Close()
                return

            # 4. Get symbol and activate
            symbols = family.GetFamilySymbolIds()
            if not symbols or symbols.Count == 0:
                output.print_md("**Error**: Family has no symbols.")
                family_doc.Close(False)
                self.Close()
                return

            first_sym_id = list(symbols)[0]
            symbol = doc.GetElement(first_sym_id)
            if symbol is not None:
                symbol.Activate()
                doc.Regenerate()

            # 5. Close family document
            family_doc.Close(False)

            # 6. Pick placement point
            try:
                with forms.WarningBar(title="Pick insertion point for new family"):
                    point_ref = uidoc.Selection.PickObject(
                        ObjectType.PointOnElement, "Pick insertion point"
                    )
                    point = point_ref.GlobalPoint
            except Exception:
                output.print_md("Placement cancelled. Family **{}** is loaded and ready.".format(family.Name))
                self.Close()
                return

            # 7. Place instance
            level = doc.ActiveView.GenLevel
            if level is None:
                output.print_md("**Error**: Active view has no level.")
                self.Close()
                return

            with Transaction(doc, "Place Generated Family") as t:
                t.Start()
                instance = doc.Create.NewFamilyInstance(
                    point, symbol, level, StructuralType.NonStructural
                )
                t.Commit()

            output.print_md(
                "# Quick Family Generated\n"
                "Family: **{}**\n"
                "Size: {}×{}×{} mm\n"
                "Placed at selected point.".format(
                    family.Name,
                    int(w * 304.8),
                    int(d * 304.8),
                    int(h * 304.8),
                )
            )

        except Exception as exc:
            output.print_md("**Error** during family generation: {}".format(exc))
            try:
                family_doc.Close(False)
            except Exception:
                pass

        self.Close()


def main():
    template_path = load_template_path()
    form = QuickFamilyGenerateForm(template_path)
    form.ShowDialog()


if __name__ == "__main__":
    main()
