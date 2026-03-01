# Add-on Authoring Guide (Panel-per-Addon)

PYLAB uses a panel-per-addon model under `PYLAB.extension/PYLAB.tab`.

## Add a new addon panel
1. Create a panel folder:
- `PYLAB.extension/PYLAB.tab/MyAddon.Panel/`

2. Create panel manifest:
- `PYLAB.extension/PYLAB.tab/MyAddon.Panel/bundle.yaml`

Example:
```yaml
title: My Addon
layout:
  - RunMyTool
```

3. Add panel to tab layout:
- Edit `PYLAB.extension/PYLAB.tab/bundle.yaml`
- Add `MyAddon` entry in the `layout` list where needed.

## Add a command button
Inside your panel create:
- `RunMyTool.pushbutton/bundle.yaml`
- `RunMyTool.pushbutton/script.py`
- `RunMyTool.pushbutton/icon.png` (optional, recommended)

Example button manifest:
```yaml
title: Run My Tool
tooltip: Short description of what this command does.
author: Pawel Kinczyk
```

## Naming rules
- Use ASCII-safe technical IDs in folder names (no spaces).
- Use readable UI names in `title` fields.
- Keep one functional area per panel.
