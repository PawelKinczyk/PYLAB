# PYLAB Button Guide

This guide explains what each PYLAB button is for, how it can improve productivity, how to use it, what it does internally, and whether it has settings you can change.

## Information Panel

### About Author
**Purpose and productivity**
Opens the author website. It is useful when you want to learn more about the extension source or contact the author outside GitHub.

**How to use**
Click the button once. Your default web browser opens the author page.

**What it does**
This is a URL button. It does not modify the Revit model.

**Settings**
No user settings.

### Report Bug
**Purpose and productivity**
Opens the GitHub bug report form so issues can be reported quickly with the correct template.

**How to use**
Click the button once and fill out the GitHub issue form in your browser.

**What it does**
This is a URL button that opens the repository bug-report template.

**Settings**
No user settings.

### Feature Idea
**Purpose and productivity**
Opens the GitHub feature request form so you can send improvement ideas without searching for the repository manually.

**How to use**
Click the button once and complete the feature request form in your browser.

**What it does**
This is a URL button that opens the repository feature-request template.

**Settings**
No user settings.

## General Panel

### Active Workset
**Purpose and productivity**
Sets the active workset to match a picked element. This saves time when you are editing elements from different worksets and want the correct workset active before creating new content.

**How to use**
1. Click `Active Workset`.
2. Pick one element in the model.
3. The command switches the active workset to that element's workset.

**What it does**
Reads the selected element's `WorksetId` and updates the active workset through the Revit workset table.

**Settings**
No user settings.

### Copy Filter
**Purpose and productivity**
Copies filter overrides from the active view to selected view templates. This speeds up view setup and keeps graphics consistent across templates.

**How to use**
1. Open the source view that already has the filter overrides you want.
2. Click `Copy Filter`.
3. Select one or more filters from the active view.
4. Select one or more target view templates.
5. Confirm to apply the same overrides to those templates.

**What it does**
Reads the selected filters and their override settings from the active view, then writes those overrides into the chosen view templates.

**Settings**
No persistent settings.

### Copy Parameters
**Purpose and productivity**
Copies one parameter value into another parameter for all instances of the same family and type as a picked element. This is useful when standardizing data or filling shared parameters in bulk.

**How to use**
1. Click `Copy Parameters`.
2. Pick one representative element.
3. Select the source parameter to copy from.
4. Select the destination parameter to write into.
5. Review the printed results in the pyRevit output window.

**What it does**
The command finds all instances with the same `Family and Type` as the picked element, filters destination parameters to writable and storage-type-compatible options, and then copies the value instance by instance.

**Settings**
No persistent settings.

### Element IDs
**Purpose and productivity**
Reports IDs for both current-model elements and linked-model elements. This helps when coordinating issues, creating filters, or locating linked content.

**How to use**
1. Click `Element IDs`.
2. Optionally pick one or more elements in the active model.
3. Optionally pick one or more elements in a linked model.
4. Read the IDs and family/type names in the pyRevit output window.

**What it does**
Prints model element IDs and linked element IDs together with the `Family and Type` label for the selected elements.

**Settings**
No user settings.

### Element 3D Focus
**Purpose and productivity**
Opens or reuses a 3D view, zooms to an element by ID, and creates a section box around it. This is useful when QA checking element locations, troubleshooting clashes, or reviewing issue tracker IDs.

**How to use**
1. Click `Element 3D Focus`.
2. Type the Revit element ID.
3. The command opens `{3D}` if available, or creates a fallback 3D view if needed.
4. The section box is resized around the element and the element is selected.

**What it does**
It looks up the element by ID, gets its bounding box, expands that box by a configurable offset, activates a 3D view, and applies the new section box. It can also temporarily isolate the element.

**Settings**
Use **Shift-click** on the button to open settings:
- Section box offset in meters
- Optional temporary isolate in the 3D view

### Family Shortcut
**Purpose and productivity**
Lets you launch native Revit family placement by typing a 2-letter shortcut instead of searching through the ribbon or Type Selector. This is especially useful for repetitive placement of a small set of commonly used families.

**How to use**
1. Click `Family Shortcut`.
2. Type a configured 2-letter shortcut.
3. If the shortcut matches a saved mapping, native Revit placement starts for that family type.

**What it does**
The runtime window loads enabled shortcut assignments, validates your typed input, resolves the mapped family/type in the active document, and starts Revit's normal placement mode for that type.

**Settings**
Use **Shift-click** to open the shortcut manager:
- Add mappings manually
- Load placeable family types from the current model
- Remove mappings
- Enable or disable mappings
- Save mappings to `%APPDATA%\pyRevit\PYLAB\FamilyShortcut\shortcuts.json`

Shortcuts must contain exactly 2 letters, and enabled shortcuts must be unique.

### Measure Elem
**Purpose and productivity**
Measures the total length of selected pipes, ducts, or walls and groups the result by type and size. It is useful for quick quantity checks without building a schedule.

**How to use**
1. Click `Measure Elem`.
2. Select elements from one family group only:
   `Pipes`, `Ducts`, or `Walls`.
3. Finish selection.
4. Review the grouped totals and grand total in the pyRevit output window.

**What it does**
The command reads element lengths, converts them to meters, groups them by type and size, prints a report, and attempts to copy that report to the clipboard.

**Settings**
No user settings.

### Place in Rooms/Spaces
**Purpose and productivity**
Places one non-hosted model family instance into multiple rooms and/or MEP spaces in one run. This is useful for placing repeated content such as markers, equipment placeholders, or coordination families across many spaces.

**How to use**
1. Click `Place in Rooms/Spaces`.
2. Choose whether to work with `Rooms only`, `Spaces only`, or `Both`.
3. Filter the list using the search box if needed.
4. Select rows with the checkbox column.
5. Assign a family type per row, or multi-select rows with `Shift` or `Ctrl` and use `Assign Family`.
6. Optionally set X, Y, and Z offsets in project units.
7. Click `Place`.
8. Review the success and failure summary in the pyRevit output window.

**What it does**
The tool collects placed Rooms and Spaces from the active model, computes a target center point for each one, finds a compatible non-hosted one-level-based family type, places the instance, tries to center and rotate it to fit, writes room/space metadata to supported instance parameters, and prints a summary table.

Supported target parameters include:
- `Room/Space Number`
- `Room/Space Name`
- `Source Spatial Element Id`
- `Source Spatial Type`

**Settings**
No Shift-click settings, but the window provides working options:
- Room or Space mode
- Search filter
- Bulk family assignment
- X/Y/Z placement offsets in project units
- Excel export and import support for family assignment workflows

### SectionReset
**Purpose and productivity**
Resets a rotated 3D section box back to project axes or rotates it in fixed increments. This helps when a working 3D view becomes hard to control after repeated rotations.

**How to use**
1. Open a 3D view with Section Box enabled.
2. Click `SectionReset`.
3. Choose one action:
   `Reset rotation`, `Rotate +45`, `Rotate -45`, `Rotate +90`, or `Rotate -90`.

**What it does**
For reset, it rebuilds the section box as a world-aligned box around the current extents. For rotate actions, it rotates the current section box around its center point.

**Settings**
No persistent settings.

### Space Search
**Purpose and productivity**
Finds an MEP space by number and selects it in the model. This is useful for quick coordination or checking data tied to a specific space.

**How to use**
1. Click `Space Search`.
2. Enter the space number.
3. The matching MEP space becomes selected.

**What it does**
Searches all MEP spaces in the active model and selects the first space whose `Number` matches your input.

**Settings**
No user settings.

## MEP Panel

### Add Insulation
**Purpose and productivity**
Applies pipe insulation to multiple selected pipes and pipe fittings in one workflow. This is faster than assigning insulation element by element.

**How to use**
1. Click `Add Insulation`.
2. Select pipes and/or pipe fittings.
3. Choose the insulation type.
4. For each detected family/type-size group, enter the insulation thickness.
5. Review the results in the pyRevit output window.

**What it does**
The tool groups the selected elements by family/type and size, asks for thickness per group, and creates Revit pipe insulation elements with the chosen insulation type and entered thickness.

**Settings**
No persistent settings. Thickness is entered each run.

### Batch Change Pipe Type
**Purpose and productivity**
Changes many pipes and compatible pipe fittings to a selected pipe type in one run. This is useful when redesigning a system and wanting fittings to follow the target routing preferences where possible.

**How to use**
1. Click `Batch change pipe type`.
2. Select pipes and pipe fittings.
3. Choose the target pipe type.
4. Let the command process the elements.
5. Review messages in the pyRevit output window for pipes and fittings that could not change.

**What it does**
The tool changes pipe instances directly to the selected type. For fittings, it checks connector sizes and uses the selected pipe type's routing preferences to swap elbows, tees, crosses, and transitions to matching fitting types when available.

**Settings**
No user settings.

### Bypass
**Purpose and productivity**
This button appears to be an unfinished or placeholder workflow for wall-related linked-model selection. It is not currently a full bypass creation tool in the checked-in script.

**How to use**
At present, the script only prompts you to pick linked-model walls and then stops.

**What it does**
It validates linked-model wall picks. It does not currently create geometry or complete a bypass workflow.

**Settings**
No user settings.

### Pipe/duct Offset
**Purpose and productivity**
Moves one parallel pipe or duct so the edge-to-edge horizontal offset from another pipe or duct matches a saved target value. This is useful for standardizing spacing in coordination and production work.

**How to use**
1. Click `Pipe/duct offset`.
2. Pick the reference pipe or duct.
3. Pick the pipe or duct to move.
4. Repeat for more pairs, or press `Esc` to finish.

**What it does**
The command reads the element centerlines, checks that the pair is parallel in plan, calculates the current center-to-center distance, converts the saved target edge distance into the required center distance using element sizes, optionally includes insulation thickness, and moves the second element in the XY plane only.

**Settings**
Use **Shift-click** to open settings:
- Target edge offset in millimeters
- Whether insulation thickness is included in the spacing calculation

### Parallel Pipe Connect
**Purpose and productivity**
Creates a new pipe between two selected pipes and connects them with elbow fittings. This speeds up simple bridge connections between parallel pipes.

**How to use**
1. Click `Parallel pipe Connect`.
2. Select exactly 2 pipes.
3. The command creates a bridging pipe and elbow fittings between the closest open connectors.

**What it does**
It collects unconnected pipe connectors, finds the closest pair, creates a new parallel pipe using the first pipe's system and type, and then attempts to place elbow fittings between the new pipe and the original pipes.

**Settings**
No persistent settings.

### Air Terminal Calculator Settings
**Purpose and productivity**
Maintains the lookup tables used by the air terminal calculator commands. This lets you adapt the recommended family/type choices to your own product library.

**How to use**
1. Click `Air terminal calculator settings`.
2. Choose whether to `Add air terminal` or `Delete air terminal`.
3. Choose whether you are editing `Supply` or `Return` records.
4. For add:
   enter minimum and maximum air flow, family type name, sound level, description, and comment.
5. For delete:
   select one or more records to remove.

**What it does**
The command edits the JSON lookup files used by the supply and return calculator tools.

**Settings**
This button is itself the settings editor. It updates:
- `air_terminals_supply_settings.json`
- `air_terminals_return_settings.json`

### Air Terminal Calculator (Supply)
**Purpose and productivity**
Suggests and applies a suitable supply air terminal type for selected air terminals based on entered air flow and the configured lookup table.

**How to use**
1. Click `Air terminal calculator (supply)`.
2. Select one or more supply air terminals.
3. Enter the required air supply value.
4. Choose one of the matching terminal options from the list.
5. The family instances are changed to matching similar types.

**What it does**
It loads the supply settings JSON, filters configured options by the entered flow range, shows the matching records, and changes the selected family instances to a similar type whose name contains the selected configured type token.

**Settings**
Use `Air terminal calculator settings` to edit available records.

### Air Terminal Calculator (Return)
**Purpose and productivity**
Works like the supply calculator, but for return air terminals. It speeds up terminal selection when sizing return devices from airflow requirements.

**How to use**
1. Click `Air terminal calculator (return)`.
2. Select one or more return air terminals.
3. Enter the required return air flow.
4. Pick one matching option from the filtered list.
5. The selected instances are changed to the matching type.

**What it does**
It uses the return settings JSON and applies the same lookup-and-change workflow as the supply version.

**Settings**
Use `Air terminal calculator settings` to edit available records.

## AECVision Integration Panel

### Walls from AECVision
**Purpose and productivity**
Creates Revit walls from a CSV exported by AECVision. This can accelerate early model creation from image-based wall detection or external preprocessing.

**How to use**
1. Click `Walls from AECVision`.
2. Select the exported CSV file.
3. Enter a known real-world measurement in centimeters.
4. Enter the same measurement in source-image pixels.
5. Select one or more Revit wall types that may be used.
6. Select the target level.
7. Enter the target wall height in centimeters.
8. Let the command generate walls.

**What it does**
The tool reads bounding-box style coordinates from the CSV, calculates the image-to-model scale, converts the longest side of each rectangle into a wall centerline, estimates wall thickness from the shorter side, picks the closest available Revit wall type by thickness, and creates the walls on the chosen level with the entered height.

**Settings**
No persistent settings. Scale, level, allowed wall types, and height are entered each run.

## Notes
- Most commands act immediately on the active Revit document. Save your model before running batch-modification tools.
- Commands that print a report use the pyRevit output window rather than a custom dialog.
- Some older commands are lightweight scripts and may have limited validation compared with the newer tools.
