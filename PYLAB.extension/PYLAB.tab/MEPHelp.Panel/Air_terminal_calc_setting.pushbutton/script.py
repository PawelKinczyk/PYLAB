from Autodesk.Revit.UI.Selection import *
from Autodesk.Revit.DB import *
from pyrevit import forms
from rpw import revit
import json
import os


doc = revit.doc
uidoc = revit.uidoc


def json_load(path=""):
    with open(path, "r") as file_json:
        data = json.load(file_json)
        return data


def json_update(path="", record=[]):
    with open(path, "r") as file_json:
        data = json.load(file_json)

    data.append(record)
    print(data)
    with open(path, "w") as file_json:
        json.dump(data, file_json, indent=1)


class Ask_for_inputs():
    def __init__(self, title):
        self.title = title

    def __ask_string(self, message=""):
        string = forms.ask_for_string(prompt=message, title=self.title)
        return string

    def ask_for_air_flow(self):
        air_flow_min = self.__ask_string(message="Write min air flow")
        air_flow_max = self.__ask_string(message="Write max air flow")
        air_flow = [air_flow_min, air_flow_max]
        position = 0
        for air in air_flow:
            if len(air) < 4 and air.isnumeric() == True and air_flow_min < air_flow_max:
                air = "0"*(4-len(air))+air
            elif len(air) == 4 and air.isnumeric() == True and air_flow_min < air_flow_max:
                continue
            else:
                forms.alert(title="Program Error",
                            msg="Problem with your input air flow. Maybe you use non numeric value?", exitscript=True)
            air_flow[position] = air
            position += 1
        self.air_flow = air_flow

    def ask_for_other_parameters(self, params_list=[]):
        position = 0
        for parameter in parameter_list:
            answer = self.__ask_string(parameter)
            parameter_list[position] = answer
            position += 1
        self.other_parameters = parameter_list

    def join_all_inputs(self):
        self.air_flow_minmax = "-".join(self.air_flow)
        self.json_structure = [self.air_flow_minmax, self.other_parameters]
        return self.json_structure


class Delete_setting_from_json():
    def __init__(self, title, path):
        self.title = title
        self.path = path

    def get_list_of_records(self):
        self.data = json_load(self.path)
        self.selected_terminal = forms.SelectFromList.show(
            self.data, title=self.title, multiselect=True, button_name='Select air terminal', width=800, height=400)

    def delete_record_from_json(self):
        data_new = []
        for number, element in enumerate(self.data, start=-1):
            if element not in self.selected_terminal:
                data_new.append(element)
        with open(self.path, 'w') as file:
            file.write(json.dumps(data_new, indent=1))

# Select what user want to do
selected_function, selected_system = forms.CommandSwitchWindow.show(
    ['Add air terminal', 'Delete air terminal'],
    switches=["Supply(left)/Return(right)"],
    message='Select Option:',
    recognize_access_key=True
)

# Exception if nothing was pick
if selected_function == None or selected_system == None:
    forms.alert(title="Program Error",
                msg="You didn't pick any option", exitscript=True)

# Set path to json with settings
path_to_json = os.path.dirname(os.path.abspath(os.path.join(__file__, "../")))
if selected_system["Supply(left)/Return(right)"] == False:
    path_to_json = os.path.join(
        path_to_json, "Air_terminal_calc_supply.pushbutton/air_terminals_supply_settings.json")
elif selected_system["Supply(left)/Return(right)"] == True:
    path_to_json = os.path.join(
        path_to_json, "Air_terminal_calc_return.pushbutton/air_terminals_return_settings.json")
else:
    pass

# Main program
if selected_function == "Add air terminal":
    # Create add terminal class
    add_air_terminal = Ask_for_inputs("Air terminal setting")
    try:
        add_air_terminal.ask_for_air_flow()
    except:
        forms.alert(title="Program Error",
                    msg="Problem with your input", exitscript=True)

    parameter_list = ["Family type name",
                      "Device volume in decibels", "Description", "Comment"]
    add_air_terminal.ask_for_other_parameters(parameter_list)

    # Save new setting
    try:
        data_update = add_air_terminal.join_all_inputs()
        json_update(path_to_json, data_update)
    except:
        forms.alert(title="Program Error",
                    msg="Problem with saving new settings", exitscript=True)

# List with air terminal to delete
elif selected_function == "Delete air terminal":
    # Create delete settings class
    new_setting = Delete_setting_from_json(
        "Air terminal setting", path_to_json)

    try:
        new_setting.get_list_of_records()
    except:
        forms.alert(title="Program Error",
                    msg="Problem with get records from settings", exitscript=True)

    try:
        new_setting.delete_record_from_json()
    except:
        forms.alert(title="Program Error",
                    msg="Problem with delete records from settings", exitscript=True)
