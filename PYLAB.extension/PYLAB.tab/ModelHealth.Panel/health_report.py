"""Shared health-check report builder.

Used by all D-series pushbuttons. Builds a formatted output-window report
in the same style as MeasureElem / Bypass.
"""


class HealthReport(object):
    """Accumulate findings and print a structured report to pyRevit output."""

    def __init__(self, title, output=None):
        self.title = title
        self.sections = []  # list of (heading, entries)
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        if output is None:
            from pyrevit import script
            self._output = script.get_output()
        else:
            self._output = output

    def add_section(self, heading):
        """Start a new section. Returns index for add_entry()."""
        self.sections.append((heading, []))
        return len(self.sections) - 1

    def add_entry(self, section_index, status, element_name, detail=""):
        """Add one finding to a section.

        status: 'pass', 'fail', or 'warn'
        element_name: human-readable element label
        detail: optional extra info (expected value, reason, etc.)
        """
        if section_index < 0 or section_index >= len(self.sections):
            return
        self.sections[section_index][1].append((status, element_name, detail))
        if status == "pass":
            self.passed += 1
        elif status == "fail":
            self.failed += 1
        elif status == "warn":
            self.warnings += 1

    def print_report(self):
        """Render the full report to the output window."""
        out = self._output

        out.print_md("# {}".format(self.title))

        # Summary line
        parts = []
        if self.failed:
            parts.append("**{} FAILED**".format(self.failed))
        if self.warnings:
            parts.append("**{} WARNINGS**".format(self.warnings))
        if self.passed:
            parts.append("{} passed".format(self.passed))
        if not parts:
            parts.append("No elements checked")

        out.print_md(" | ".join(parts))
        out.print_md("---")

        # Sections
        for heading, entries in self.sections:
            if not entries:
                continue
            out.print_md("## {}".format(heading))

            # Sort: fails first, then warnings, then passes
            order = {"fail": 0, "warn": 1, "pass": 2}
            sorted_entries = sorted(entries, key=lambda e: order.get(e[0], 9))

            for status, name, detail in sorted_entries:
                if status == "fail":
                    icon = "FAIL"
                elif status == "warn":
                    icon = "WARN"
                else:
                    icon = "PASS"

                line = "- **{}** — `{}`".format(icon, name)
                if detail:
                    line += "  \n  {}".format(detail)
                out.print_md(line)

            out.print_md("")

        # Footer
        out.print_md("---")
        total = self.passed + self.failed + self.warnings
        out.print_md(
            "**Total**: {} checked | {} passed | {} failed | {} warnings".format(
                total, self.passed, self.failed, self.warnings
            )
        )

    def has_failures(self):
        return self.failed > 0

    def has_issues(self):
        return self.failed > 0 or self.warnings > 0
