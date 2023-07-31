import System
import os
from rpw import revit
from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from pyrevit import output
import csv

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
csv_file_path = forms.pick_file(title="Pick file with exported csv")


## Ask for measured lenght in jpg image

lenght_pixels = forms.ask_for_string(
    default='Write what is the lenght of measure object in pixels',
    prompt='Set value',
    title='Pixels lenght'
)

lenght_real_centimeters = forms.ask_for_string(
    default='Write what is the real lenght of measure object in centimeters',
    prompt='Set value',
    title='Real lenght'
)

## Calculate scale

scale = float(lenght_real_centimeters) / float(lenght_pixels)

## Create walls

### Import csv
data_file = []
with open(csv_file_path) as csvfile:
    data = csv.DictReader(csvfile, delimiter=',') #, quotechar='|'
    for row in data:
        data_file.append(row)

print(data_file)

for dict in data_file:
    float_values(dict)



## Create walls

### Collect levels and walls types
levels = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()
walls = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls).WhereElementIsElementType().ToElements()

### Ask which wall(s) use
walls_dict = {x.Name : x for x in walls}
selected_walls = forms.SelectFromList.show(walls_dict.keys(), title = "Select walls to use", multiselect=True,button_name='Select walls to use')

### Ask for level
levels_dict = {x.Name : x for x in levels}
selected_level = forms.SelectFromList.show(levels_dict.keys(), title = "Select level", multiselect=False,button_name='Select level')

### Collect walls curves
curves_list = []
for dict in data_file:
    a = dict["xmax"] - dict["xmin"]
    b = abs(dict["ymax"] - dict["ymin"])
    if a>=b:
        x1 = dict["xmin"]
        x2 = dict["xmax"]
        y1 = dict["ymin"] + (dict["ymax"]-dict["ymin"])/2
        y2 = dict["ymin"] + (dict["ymax"]-dict["ymin"])/2
    else:
        x1 = dict["xmin"] + (dict["xmax"]-dict["xmin"])/2
        x2 = dict["xmin"] + (dict["xmax"]-dict["xmin"])/2
        y1 = dict["ymin"]
        y2 = dict["ymax"]
    print("{},{},{},{}".format(x1, y1, x2, y2))
    point_1 = XYZ(x1/30.48 , y1/30.48 , levels[0].Elevation)
    point_2 = XYZ(x2/30.48 , y2/30.48 , levels[0].Elevation)
    wall_line = Line.CreateBound(point_1, point_2)
    curves_list.append(wall_line)



t = Transaction(doc, "Wall import - PYLAB")
t.Start()
# point_1 = XYZ(100, 100, levels[0].Elevation)
# point_2 = XYZ(300, 100, levels[0].Elevation)
# wall_line = Line.CreateBound(point_1, point_2)
# Wall.Create(doc, wall_line, walls[0].Id, levels[0].Id, 3000/304.8, 0, False, True)
for line in curves_list:
    Wall.Create(doc, line, walls[0].Id, levels[0].Id, 3000/304.8, 0, False, True)
t.Commit()
