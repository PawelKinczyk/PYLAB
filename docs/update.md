# Update PYLAB to Latest Changes

Official update source is `origin/main`.

## If installed from pyRevit extension source
```powershell
pyrevit extensions update
pyrevit reload
```

## If you use a local git clone
```powershell
git checkout main
git pull --ff-only
pyrevit reload
```

If command changes are not visible immediately, restart Revit.
