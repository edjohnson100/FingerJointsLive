# PaletteDisplayCheck.py
#
# Standalone Fusion script (Scripts and Add-Ins > Scripts) that reports where
# the Finger Joints Live palette would open and why. Run it when the palette
# is missing: it works whether or not the palette is actually visible, and it
# needs the add-in to be installed but not running.
#
# Move the Fusion window between monitors and run it again -- the "Fusion's
# window" line follows it, and the verdict flips from "ok" to "remapped"
# exactly in the situation where a stale saved position would have made the
# palette invisible.

import adsk.core
import importlib.util
import os
import traceback

PALETTE_ID = 'FingerJointsLive_Palette'
CONFIG_RELATIVE = 'defaults.json'


def _find_addin_dir():
    # Both the add-in and this script live under the Fusion API folder, with
    # the script nested two levels inside the add-in in a source checkout.
    here = os.path.dirname(os.path.realpath(__file__))
    candidates = [os.path.abspath(os.path.join(here, '..', '..'))]
    api = os.path.abspath(os.path.join(here, '..', '..', '..'))
    candidates.append(os.path.join(api, 'AddIns', 'FingerJointsLive'))
    for path in candidates:
        if os.path.exists(os.path.join(path, 'display_utils.py')):
            return path
    return None


def _load_display_utils(addin_dir):
    spec = importlib.util.spec_from_file_location(
        'fingerjointslive_display_utils', os.path.join(addin_dir, 'display_utils.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        addin_dir = _find_addin_dir()
        if not addin_dir:
            ui.messageBox('Could not locate the Finger Joints Live add-in folder '
                          '(display_utils.py not found).')
            return

        display_utils = _load_display_utils(addin_dir)

        geometry = {}
        config_path = os.path.join(addin_dir, CONFIG_RELATIVE)
        if os.path.exists(config_path):
            import json
            with open(config_path, 'r') as f:
                data = json.load(f)
            geometry = {
                'left': data.get('paletteLeft'),
                'top': data.get('paletteTop'),
                'width': data.get('paletteWidth'),
                'height': data.get('paletteHeight'),
                'docking_state': data.get('paletteDockingState'),
                'display_layout': data.get('paletteDisplayLayout'),
            }

        palette = ui.palettes.itemById(PALETTE_ID)

        report = display_utils.describe(geometry)
        report += '\n\nPalette currently loaded: {}'.format(
            'yes (visible={})'.format(palette.isVisible) if palette else 'no')

        ui.messageBox(report, 'Finger Joints Live - Palette Display Check')
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
