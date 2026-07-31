"""ModelHealth panel — shared infrastructure for D-series health checks.

Import pattern for pushbuttons inside this panel:

    import os
    import sys

    SCRIPT_DIR = os.path.dirname(__file__)
    PANEL_DIR = os.path.dirname(SCRIPT_DIR)
    if PANEL_DIR not in sys.path:
        sys.path.append(PANEL_DIR)

    from health_report import HealthReport
    from config_loader import load_team_config, load_user_config
"""
