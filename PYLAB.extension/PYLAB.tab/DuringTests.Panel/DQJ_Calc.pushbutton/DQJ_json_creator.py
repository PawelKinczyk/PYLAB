import json
import os


dict_schacko_DQJ_sq_supply = {150:(("NW=310", "dP=14", "dB=24", "x=0.84"),("NW=400", "dP=10", "dB=20", "x=0.59")),
                       200:(("NW=310", "dP=25", "dB=32", "x=1.32"),("NW=400", "dP=19", "dB=28", "x=0.96"))}
json_object = json.dumps(dict_schacko_DQJ_sq_supply, indent = 1) 
print(json_object)

with open("PYLAB.extension\PYLAB.tab\DuringTests.Panel\DQJ_Calc.pushbutton\schacko_DQJ_sq_supply.json", "w") as outfile:
    json.dump(dict_schacko_DQJ_sq_supply, outfile,indent=1)