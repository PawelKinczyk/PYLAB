"""Shortcut capture window for FamilyShortcut."""

import os

from pyrevit import forms

from family_shortcut_store import ShortcutStore, normalize_shortcut


class FamilyShortcutRuntimeWindow(forms.WPFWindow):
    def __init__(self, xaml_file, store):
        forms.WPFWindow.__init__(self, xaml_file)

        self._store = store
        self._assignments = []
        self.result_assignment = None
        self._load_assignments()

        self.input_tb.Focus()
        self.input_tb.SelectAll()
        self.input_tb.PreviewTextInput += self.on_preview_text_input
        self.input_tb.TextChanged += self.on_text_changed
        self.input_tb.KeyDown += self.on_key_down

    def _load_assignments(self):
        self._assignments = [item for item in self._store.load() if item.enabled]
        self.set_status(
            "Ready. Type a configured 2-letter shortcut.",
            "{} active shortcut{}".format(
                len(self._assignments), "" if len(self._assignments) == 1 else "s"
            ),
        )

    def set_status(self, text, details=""):
        self.status_tb.Text = text or ""
        self.details_tb.Text = details or ""

    def set_input_value(self, value):
        self.input_tb.Text = value
        self.input_tb.SelectionStart = len(value)

    def on_preview_text_input(self, sender, args):
        text = str(args.Text or "")
        if not text.isalpha():
            args.Handled = True

    def on_text_changed(self, sender, args):
        normalized = normalize_shortcut(self.input_tb.Text)
        if self.input_tb.Text != normalized:
            self.set_input_value(normalized)
            return

        self.update_match_status(normalized)
        if len(normalized) == 2:
            self.try_submit_shortcut(normalized)

    def on_key_down(self, sender, args):
        key_name = str(args.Key)

        if key_name == "Escape":
            self.result_assignment = None
            self.Close()
            return

        if key_name == "Return":
            args.Handled = True
            self.try_submit_shortcut(normalize_shortcut(self.input_tb.Text))
            return

    def update_match_status(self, shortcut):
        if not shortcut:
            self.set_status(
                "Ready. Type a configured 2-letter shortcut.",
                "{} active shortcut{}".format(
                    len(self._assignments), "" if len(self._assignments) == 1 else "s"
                ),
            )
            return

        exact_match = self.find_exact_match(shortcut)
        if exact_match:
            self.set_status(
                "Shortcut ready: {}".format(shortcut),
                "{}{}".format(
                    exact_match.display_name(),
                    " [{}]".format(exact_match.category_name) if exact_match.category_name else "",
                ),
            )
            return

        possible_count = 0
        for assignment in self._assignments:
            if assignment.shortcut.startswith(shortcut):
                possible_count += 1

        if possible_count:
            self.set_status(
                "Shortcut prefix: {}".format(shortcut),
                "Type one more letter to complete the 2-letter shortcut.",
            )
        else:
            self.set_status(
                "Shortcut not configured: {}".format(shortcut),
                "No active mapping matches this input.",
            )

    def find_exact_match(self, shortcut):
        for assignment in self._assignments:
            if assignment.shortcut == shortcut:
                return assignment
        return None

    def try_submit_shortcut(self, shortcut):
        if len(shortcut) != 2:
            self.set_status(
                "Shortcut incomplete.",
                "Type exactly 2 letters.",
            )
            return

        assignment = self.find_exact_match(shortcut)
        if assignment is None:
            self.set_status(
                "Shortcut not configured: {}".format(shortcut),
                "Use Shift-click on the button to manage assignments.",
            )
            return

        self.result_assignment = assignment
        self.DialogResult = True
        self.Close()


def prompt_for_assignment():
    xaml_file = os.path.join(os.path.dirname(__file__), "FamilyShortcutRuntime.xaml")
    store = ShortcutStore()
    window = FamilyShortcutRuntimeWindow(xaml_file, store)
    window.ShowDialog()
    return window.result_assignment
