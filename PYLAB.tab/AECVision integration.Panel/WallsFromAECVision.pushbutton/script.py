## Imports
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
import csv

## Get revit model
doc = __revit__.ActiveUIDocument.Document

## def / class

### Change string to float in dict
def float_values(trips):
    for key, value in trips.items():
        try:
            if key in ["ymin", "ymax", "xmin", "xmax"]:
                trips[key] = float(value)
        except ValueError:
            continue


## Pick file with csv
try:
    csv_file_path = forms.pick_file(title="Pick file with exported csv")
except:
    forms.alert(title="Program Error", msg="You didn't pick csv file", exitscript=True)

## Ask for measured lenght in jpg image
lenght_real_centimeters = forms.ask_for_string(
    default="Set value",
    prompt="Write what is the real lenght of measure object in centimeters",
    title="Real lenght",
)

lenght_pixels = forms.ask_for_string(
    default="Set value",
    prompt="Write what is the lenght of measure object in pixels",
    title="Pixels lenght",
)

## Calculate scale
try:
    scale = float(lenght_real_centimeters) / float(lenght_pixels)
except ValueError:
    forms.alert(
        title="Program Error",
        msg="You wrote wrong lenght in centimeters or pixels (maybe you used letters?)",
        exitscript=True,
    )
except:
    forms.alert(
        title="Program Error",
        msg="You wrote wrong lenght value in centimeters or pixels",
        exitscript=True,
    )

## Create walls

### Import csv
data_file = []
with open(csv_file_path) as csvfile:
    data = csv.DictReader(csvfile, delimiter=",")
    for row in data:
        data_file.append(row)

### Change strings to float
for dict in data_file:
    float_values(dict)

## Create walls

### Collect levels and walls types
levels = (
    FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Levels)
    .WhereElementIsNotElementType()
    .ToElements()
)
walls = (
    FilteredElementCollector(doc)
    .OfCategory(BuiltInCategory.OST_Walls)
    .WhereElementIsElementType()
    .ToElements()
)

### Ask which wall(s) use
try:
    walls_dict = {Element.Name.GetValue(x): x for x in walls}
    selected_walls = forms.SelectFromList.show(
        walls_dict.keys(),
        title="Select walls to use",
        multiselect=True,
        button_name="Select walls to use",
    )
    if len(selected_walls) == 0:
        raise Exception
except:
    forms.alert(
        title="Program Error",
        msg="You canceled wall choosing or didn't pick anything",
        exitscript=True,
    )

walls_list = []
for wall_name in selected_walls:
    walls_list.append((walls_dict[wall_name], walls_dict[wall_name].Width))

### Ask for level
try:
    levels_dict = {x.Name: x for x in levels}
    selected_level = forms.SelectFromList.show(
        levels_dict.keys(),
        title="Select level",
        multiselect=False,
        button_name="Select level",
    )
    if len(selected_level) == 0:
        raise Exception
except:
    forms.alert(
        title="Program Error",
        msg="You canceled level choosing or didn't pick anything",
        exitscript=True,
    )

### Ask for hight of import walls
height_of_walls = forms.ask_for_string(
    default="Set value",
    prompt="Write height of walls in centimeters",
    title="Walls height",
)
try:
    height_of_walls = float(height_of_walls) / 30.48
except:
    forms.alert(
        title="Program Error",
        msg="You wrote wrong height in centimeters (maybe you used letters?)",
        exitscript=True,
    )

### Collect walls curves
curves_list = []
for dict in data_file:
    a = dict["xmax"] - dict["xmin"]
    b = abs(dict["ymax"] - dict["ymin"])
    if (
        a >= b
    ):  # measure which side is longer this tell us which dimension is lenght and width
        x1 = dict["xmin"]
        x2 = dict["xmax"]
        y1 = dict["ymin"] + (dict["ymax"] - dict["ymin"]) / 2
        y2 = dict["ymin"] + (dict["ymax"] - dict["ymin"]) / 2
        wall_thickness = b * scale
    else:
        x1 = dict["xmin"] + (dict["xmax"] - dict["xmin"]) / 2
        x2 = dict["xmin"] + (dict["xmax"] - dict["xmin"]) / 2
        y1 = dict["ymin"]
        y2 = dict["ymax"]
        wall_thickness = a * scale

    # We must division by 30.48 because we need to translate centimeters to inches
    point_1 = XYZ(
        (x1 * scale) / 30.48,
        (y1 * scale) / 30.48,
        levels_dict[selected_level].Elevation,
    )
    point_2 = XYZ(
        (x2 * scale) / 30.48,
        (y2 * scale) / 30.48,
        levels_dict[selected_level].Elevation,
    )
    # Create and collect revit curves with detected walls thickness
    wall_line = Line.CreateBound(point_1, point_2)
    curves_list.append((wall_line, wall_thickness / 30.48))

### Unzip picked walls with their thickness
walls, walls_thickness = map(list, zip(*walls_list))

### Start placing walls
t = Transaction(doc, "Walls from AECVision - PYLAB")
t.Start()
try:
    #### Iterate throught lines
    for line, thickness in curves_list:
        #### Get closest wall thickness
        wall_index = min(
            range(len(walls_thickness)),
            key=lambda i: abs(walls_thickness[i] - thickness),
        )
        #### Create wall
        Wall.Create(
            doc,
            line,
            walls[wall_index].Id,
            levels_dict[selected_level].Id,
            height_of_walls,
            0,
            False,
            True,
        )
except Exception as e:
    forms.alert(title="Program Error", msg=e, exitscript=True)
t.Commit()
