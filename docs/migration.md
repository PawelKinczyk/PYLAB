# Migrate from Legacy PYLAB Layout

This migration is for users already registered against the old structure.

## 1. Remove old registration
```powershell
pyrevit extensions
pyrevit extensions remove PYLAB
```

## 2. Re-register with current extension structure
From GitHub:
```powershell
pyrevit extend ui PYLAB https://github.com/PawelKinczyk/PYLAB.git
```

From local clone:
```powershell
pyrevit extend ui PYLAB "C:\path\to\PYLAB\PYLAB.extension"
```

## 3. Reload
```powershell
pyrevit reload
```

If reload is not enough, restart Revit.
