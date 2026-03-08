"""Shortcut manager window for FamilyShortcut."""

import os

import clr

clr.AddReference("System")
clr.AddReference("System.Core")
clr.AddReference("PresentationFramework")
clr.AddReference("WindowsBase")

from System import Object, Predicate
from System.Collections.ObjectModel import ObservableCollection
from System.Windows.Data import CollectionViewSource

from pyrevit import forms

from family_shortcut_revit import build_symbol_picker_rows, show_revit_warning
from family_shortcut_store import (
    ShortcutAssignment,
    ShortcutStore,
    normalize_shortcut,
    utc_now_text,
    validate_assignments,
)


class AssignmentRow(object):
    def __init__(self, assignment=None):
        source = assignment or ShortcutAssignment()
        self.Shortcut = source.shortcut
        self.FamilyName = source.family_name
        self.TypeName = source.type_name
        self.CategoryName = source.category_name
        self.Enabled = bool(source.enabled)
        self.CreatedUtc = source.created_utc
        self.UpdatedUtc = source.updated_utc
        self.Notes = source.notes

    def to_assignment(self):
        created_utc = self.CreatedUtc or utc_now_text()
        return ShortcutAssignment(
            shortcut=normalize_shortcut(self.Shortcut),
            family_name=self.FamilyName,
            type_name=self.TypeName,
            category_name=self.CategoryName,
            enabled=self.Enabled,
            created_utc=created_utc,
            updated_utc=utc_now_text(),
            notes=self.Notes,
        )


class PickerRow(object):
    def __init__(self, shortcut, family_name, type_name, category_name):
        self.Shortcut = shortcut
        self.FamilyName = family_name
        self.TypeName = type_name
        self.CategoryName = category_name


class FamilyShortcutManagerWindow(forms.WPFWindow):
    def __init__(self, xaml_file, store):
        forms.WPFWindow.__init__(self, xaml_file)

        self._store = store
        self._rows = ObservableCollection[Object]()
        self._picker_rows = ObservableCollection[Object]()
        self._view = None
        self._picker_view = None

        self.load_assignments()
        self.load_picker_rows()

        self.assignment_grid.ItemsSource = self._rows
        self._view = CollectionViewSource.GetDefaultView(self.assignment_grid.ItemsSource)
        self._view.Filter = Predicate[Object](self._filter_assignment_row)

        self.symbol_grid.ItemsSource = self._picker_rows
        self._picker_view = CollectionViewSource.GetDefaultView(self.symbol_grid.ItemsSource)
        self._picker_view.Filter = Predicate[Object](self._filter_picker_row)

        self.search_tb.TextChanged += self.on_search_changed
        self.picker_search_tb.TextChanged += self.on_picker_search_changed
        self.add_manual_btn.Click += self.on_add_manual
        self.remove_selected_btn.Click += self.on_remove_selected
        self.reload_doc_btn.Click += self.on_reload_doc
        self.add_from_doc_btn.Click += self.on_add_from_doc
        self.save_btn.Click += self.on_save
        self.close_btn.Click += self.on_close
        self.assignment_grid.CellEditEnding += self.on_cell_edit_ending
        self.assignment_grid.CurrentCellChanged += self.on_grid_changed

        self.refresh_validation_status()

    def load_assignments(self):
        existing_rows = list(self._rows)
        for row in existing_rows:
            self._rows.Remove(row)
        for assignment in self._store.load():
            self._rows.Add(AssignmentRow(assignment))

    def load_picker_rows(self):
        existing_rows = list(self._picker_rows)
        for row in existing_rows:
            self._picker_rows.Remove(row)
        for item in build_symbol_picker_rows():
            self._picker_rows.Add(
                PickerRow(
                    shortcut=item["shortcut"],
                    family_name=item["family_name"],
                    type_name=item["type_name"],
                    category_name=item["category_name"],
                )
            )

    def _filter_text(self, item, search_text):
        haystack = " ".join(
            [
                getattr(item, "Shortcut", ""),
                getattr(item, "FamilyName", ""),
                getattr(item, "TypeName", ""),
                getattr(item, "CategoryName", ""),
            ]
        ).lower()
        return search_text in haystack

    def _filter_assignment_row(self, item):
        search_text = str(self.search_tb.Text or "").strip().lower()
        if not search_text:
            return True
        return self._filter_text(item, search_text)

    def _filter_picker_row(self, item):
        search_text = str(self.picker_search_tb.Text or "").strip().lower()
        if not search_text:
            return True
        return self._filter_text(item, search_text)

    def on_search_changed(self, sender, args):
        self._view.Refresh()

    def on_picker_search_changed(self, sender, args):
        self._picker_view.Refresh()

    def on_add_manual(self, sender, args):
        self._rows.Add(AssignmentRow())
        self.refresh_validation_status()

    def on_remove_selected(self, sender, args):
        selected_rows = list(self.assignment_grid.SelectedItems)
        if not selected_rows:
            show_revit_warning("Select one or more assignment rows to remove.")
            return
        for row in selected_rows:
            self._rows.Remove(row)
        self.refresh_validation_status()

    def on_reload_doc(self, sender, args):
        try:
            self.load_picker_rows()
            self._picker_view.Refresh()
            self.set_status("Reloaded placeable family types from the active document.")
        except Exception as ex:
            show_revit_warning(str(ex))
            self.set_status("Could not reload active-document family types.")

    def on_add_from_doc(self, sender, args):
        selected_rows = list(self.symbol_grid.SelectedItems)
        if not selected_rows:
            show_revit_warning("Select one or more family types in the active-document list.")
            return

        for row in selected_rows:
            self._rows.Add(
                AssignmentRow(
                    ShortcutAssignment(
                        shortcut=normalize_shortcut(row.Shortcut),
                        family_name=row.FamilyName,
                        type_name=row.TypeName,
                        category_name=row.CategoryName,
                        enabled=True,
                    )
                )
            )

        self.refresh_validation_status()

    def on_cell_edit_ending(self, sender, args):
        row = args.Row.Item
        column_header = str(args.Column.Header or "")
        editor = args.EditingElement
        text_value = ""
        try:
            text_value = str(editor.Text or "")
        except Exception:
            return

        if column_header == "Shortcut":
            row.Shortcut = normalize_shortcut(text_value)
        elif column_header == "Family Name":
            row.FamilyName = text_value.strip()
        elif column_header == "Type Name":
            row.TypeName = text_value.strip()
        elif column_header == "Category":
            row.CategoryName = text_value.strip()

    def on_grid_changed(self, sender, args):
        self.refresh_validation_status()

    def set_status(self, message):
        self.status_tb.Text = message or ""

    def build_assignments(self):
        assignments = []
        for row in self._rows:
            assignments.append(row.to_assignment())
        return assignments

    def refresh_validation_status(self):
        assignments = self.build_assignments()
        errors = validate_assignments(assignments)
        if errors:
            self.validation_tb.Text = "\n".join(errors[:6])
            self.set_status("Resolve validation errors before saving.")
            self.save_btn.IsEnabled = False
        else:
            self.validation_tb.Text = "No validation errors."
            self.set_status(
                "{} assignment{}".format(
                    len(assignments), "" if len(assignments) == 1 else "s"
                )
            )
            self.save_btn.IsEnabled = True

    def on_save(self, sender, args):
        assignments = self.build_assignments()
        try:
            target_path = self._store.save(assignments)
            self.refresh_validation_status()
            self.set_status("Saved assignments to {}".format(target_path))
        except Exception as ex:
            show_revit_warning(str(ex))
            self.set_status("Save failed.")

    def on_close(self, sender, args):
        self.Close()


def show_manager_window():
    xaml_file = os.path.join(os.path.dirname(__file__), "FamilyShortcutManager.xaml")
    store = ShortcutStore()
    try:
        window = FamilyShortcutManagerWindow(xaml_file, store)
    except Exception as ex:
        forms.alert(
            str(ex),
            title="FamilyShortcut",
            warn_icon=True,
            exitscript=False,
        )
        return
    window.ShowDialog()
