import System
import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output
import csv
import math

doc = __revit__.ActiveUIDocument.Document

## def / class


### Change string to float and dict
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
    forms.alert(title="Program Error",
                msg="You didn't pick csv file", exitscript=True)

## Ask for measured lenght in jpg image
try:
    lenght_real_centimeters = forms.ask_for_string(
        default="Write what is the real lenght of measure object in centimeters",
        prompt="Set value",
        title="Real lenght",
    )
except:
    forms.alert(title="Program Error",
                msg="You didn't write anything", exitscript=True)

try:
    lenght_pixels = forms.ask_for_string(
        default="Write what is the lenght of measure object in pixels",
        prompt="Set value",
        title="Pixels lenght",
    )
except:
    forms.alert(title="Program Error",
                msg="You didn't choose anything", exitscript=True)

## Calculate scale
try:
    scale = float(lenght_real_centimeters) / float(lenght_pixels)
except ValueError:
        forms.alert(title="Program Error",
                msg="You wrote wrong lenght in centimeters or pixels (maybe you used letters?)", exitscript=True)
except:
        forms.alert(title="Program Error",
                msg="You wrote wrong lenght value in centimeters or pixels", exitscript=True)   
## Create walls

### Import csv
data_file = []
with open(csv_file_path) as csvfile:
    data = csv.DictReader(csvfile, delimiter=",")  # , quotechar='|'
    for row in data:
        data_file.append(row)

print(data_file)

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
except:
    forms.alert(title="Program Error",
                msg="You canceled wall choosing", exitscript=True)
walls_list = []
try:
    for wall_name in selected_walls:
        walls_list.append((walls_dict[wall_name], walls_dict[wall_name].Width))
except:
    forms.alert(title="Program Error",
                msg="The wall(s) list is empty", exitscript=True)
### Ask for level
try:
    levels_dict = {x.Name: x for x in levels}
    selected_level = forms.SelectFromList.show(
        levels_dict.keys(),
        title="Select level",
        multiselect=False,
        button_name="Select level",
    )
except:
    forms.alert(title="Program Error",
                msg="You canceled level choosing", exitscript=True)
### Collect walls curves
curves_list = []
for dict in data_file:
    a = dict["xmax"] - dict["xmin"]
    b = abs(dict["ymax"] - dict["ymin"])
    if a >= b:
        x1 = dict["xmin"]
        x2 = dict["xmax"]
        y1 = dict["ymin"] + (dict["ymax"] - dict["ymin"]) / 2
        y2 = dict["ymin"] + (dict["ymax"] - dict["ymin"]) / 2
        wall_thickness = b
    else:
        x1 = dict["xmin"] + (dict["xmax"] - dict["xmin"]) / 2
        x2 = dict["xmin"] + (dict["xmax"] - dict["xmin"]) / 2
        y1 = dict["ymin"]
        y2 = dict["ymax"]
        wall_thickness = a
    print("{},{},{},{},{}".format(x1, y1, x2, y2, wall_thickness))
    point_1 = XYZ(
        (x1 / 30.48) * scale,
        (y1 / 30.48) * scale,
        levels_dict[selected_level].Elevation,
    )
    point_2 = XYZ(
        (x2 / 30.48) * scale,
        (y2 / 30.48) * scale,
        levels_dict[selected_level].Elevation,
    )
    wall_line = Line.CreateBound(point_1, point_2)
    curves_list.append((wall_line, wall_thickness))

walls, walls_thickness = map(list, zip(*walls_list))
print(walls)
print(walls_thickness)
t = Transaction(doc, "Wall import - PYLAB")
t.Start()
for line, thickness in curves_list:
    print(thickness)
    wall_index = min(
        range(len(walls_thickness)), key=lambda i: abs(walls_thickness[i] - thickness)
    )

    Wall.Create(
        doc,
        line,
        walls[wall_index].Id,
        levels_dict[selected_level].Id,
        3000 / 304.8,
        0,
        False,
        True,
    )
t.Commit()
