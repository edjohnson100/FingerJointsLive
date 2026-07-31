# FingerJointsLive
# Author: Ed Johnson (Making With An EdJ)
# A live, palette-based remix of Florian Pommerening's original Finger Joints
# add-in (https://github.com/FlorianPommerening/FingerJoints) — his core
# finger-joint math is still in here doing the heavy lifting, wrapped in a
# persistent HTML palette with live preview, presets, theming, a Close Butt
# Joint loop, full Through Dovetail joint support, and multi-body selection
# (pick several 1st/2nd bodies at once and generate every resulting joint in
# one pass instead of repeating the whole workflow per pair).

# Select two overlapping bodies and a direction. The overlap is cut along the
# direction multiple times resulting in the individual fingers/notches. We
# then remove every second finger from the first body and the other fingers
# from the second body. The remaining bodies then do not overlap anymore.

# Some inspiration was taken from the dogbone add-in developed by Peter
# Ludikar, Gary Singer, Patrick Rainsberry, David Liu, and Casey Rogers.

import adsk.core
import adsk.fusion
import traceback
import os
import json
import time

from . import options
from . import geometry

app = None
ui = None
handlers = []
palette_id = 'FingerJointsLive_Palette'
command_id = 'FingerJointsLive_Launcher'
preview_group_id = 'FingerJointsLive_Preview'
undo_group_command_id = 'FingerJointsLive_UndoGroup'

def _read_manifest_version():
    manifest_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'FingerJointsLive.manifest')
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            return json.load(f).get('version', '')
    except Exception:
        return ''

ADDIN_VERSION = _read_manifest_version()

# Human-readable labels for the internal selection-target keys (body0/body1/direction/
# extendSource/extendTargetFace), used for both the FJL_Select_* command's title bar and its
# selection input's in-dialog label - Fusion shows the raw camelCase key otherwise (e.g.
# "SELECT BODY0", "Select extendTargetFace"), which reads like an internal variable name.
TARGET_LABELS = {
    'body0': '1st Body/Bodies',
    'body1': '2nd Body/Bodies',
    'direction': 'Joint Direction',
    'extendSource': 'Face to Extend',
    'extendTargetFace': 'Target Face',
}

# Zero-arg callable currently pending execution inside the hidden undo-group command
# (see _run_grouped). Only ever set/consumed synchronously within a single call stack.
_pending_grouped_work = None

# Global state to hold selections (since HTML cannot hold Fusion BRep objects)
active_selections = {
    'body0': [],
    'body1': [],
    'direction': None,
    'extendSource': None,
    'extendTargetFace': None
}

# Timeline index the "Close Butt Joint" loop started at, and whether the next
# selection command's destroy event is an internal chain step (not a real loop end).
extend_loop_start_index = None
extend_loop_chaining = False

PRESETS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'presets.json')

def load_presets_dict():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {}

def save_presets_dict(d):
    with open(PRESETS_FILE, 'w') as f: json.dump(d, f, indent=4)

# Host-side store for user-imported/edited themes -- separate from the built-in
# themes baked into resources/style.css. Per-machine, gitignored (same split as
# GridfinityGeneratorPlus/LiveUtilities): survives a restart or a localStorage
# wipe without polluting resources/, which holds only what ships with the add-in.
IMPORTED_THEMES_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'imported_themes.json')

def load_imported_themes():
    if not os.path.exists(IMPORTED_THEMES_FILE):
        return {}
    try:
        with open(IMPORTED_THEMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_imported_theme(theme_id, theme_vars):
    themes = load_imported_themes()
    themes[theme_id] = theme_vars
    with open(IMPORTED_THEMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(themes, f, indent=2)

def delete_imported_theme(theme_id):
    themes = load_imported_themes()
    if theme_id in themes:
        del themes[theme_id]
        with open(IMPORTED_THEMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(themes, f, indent=2)

def clear_imported_themes():
    """Used by the Theme Manager's Factory Reset -- wipes every host-persisted
    imported theme, not just localStorage, so a reset actually resets."""
    if os.path.exists(IMPORTED_THEMES_FILE):
        os.remove(IMPORTED_THEMES_FILE)

def _themes_dialog_dir():
    """Standard theme import/export dialog location: resources/themes/ if it
    exists (shipped presets), else fall back to resources/."""
    root = os.path.dirname(os.path.realpath(__file__))
    themes_dir = os.path.join(root, 'resources', 'themes')
    return themes_dir if os.path.isdir(themes_dir) else os.path.join(root, 'resources')

def createBaseFeature(parentComponent, bRepBody, name):
    feature = parentComponent.features.baseFeatures.add()
    feature.startEdit()
    parentComponent.bRepBodies.add(bRepBody, feature)
    feature.name = name
    feature.finishEdit()
    return feature

def createCutFeature(parentComponent, targetBody, toolBodyFeature):
    if toolBodyFeature.bodies.count == 0: return None
    toolBodies = adsk.core.ObjectCollection.create()
    toolBodies.add(toolBodyFeature.bodies.item(0))
    cutInput = parentComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    cutInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    cutInput.isNewComponent = False
    return parentComponent.features.combineFeatures.add(cutInput)

def _run_grouped(work, name):
    """Runs `work` (a zero-arg callable) inside the hidden undo-group command's execute handler
    so every Fusion API call it makes gets bundled by Fusion into that one execute's Undo
    transaction, instead of one Undo entry per feature. `name` becomes the label shown in the
    Undo dropdown. Safe with a single global slot because this is only ever called synchronously
    from UI-triggered code (e.g. the Generate button), and a command with no dialog inputs
    auto-executes synchronously on creation, so the pending-work variable is set and consumed
    within the same call stack before any other call could stomp it."""
    global _pending_grouped_work
    cmd_def = ui.commandDefinitions.itemById(undo_group_command_id)
    if not cmd_def:
        work()
        return
    _pending_grouped_work = work
    cmd_def.name = name
    cmd_def.execute()


class UndoGroupExecuteHandler(adsk.core.CommandEventHandler):
    """Runs whatever callable is currently stashed in _pending_grouped_work. Fusion bundles every
    API call the callable makes into this execute's single Undo transaction."""
    def notify(self, args):
        global _pending_grouped_work
        work = _pending_grouped_work
        _pending_grouped_work = None
        if work:
            work()


class UndoGroupCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Attaches the execute handler to each instance of the hidden undo-group command. The
    command has no dialog inputs, so it auto-executes immediately upon creation with no UI ever
    shown; it exists purely to get Fusion's automatic per-Command Undo-transaction bundling for
    work triggered from non-command code (e.g. the HTML router)."""
    def notify(self, args):
        try:
            cmd = args.command
            onExecute = UndoGroupExecuteHandler()
            cmd.execute.add(onExecute)
            handlers.append(onExecute)
        except Exception:
            if ui: ui.messageBox(f'Could not set up undo-group command:\n{traceback.format_exc()}')


def createExtensionFeature(parentComponent, face, length):
    """Extrudes the given face outward along its own normal and joins the result onto
    its owning body, closing a butt-joint gap. participantBodies is restricted to the
    face's own owning body so the Join cannot merge with some other unrelated body that
    the extension happens to touch or pass through along the way."""
    extrudes = parentComponent.features.extrudeFeatures
    extInput = extrudes.createInput(face, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    extInput.setDistanceExtent(False, adsk.core.ValueInput.createByReal(length))
    extInput.participantBodies = [face.body]
    return extrudes.add(extInput)

def extend_face_to_close_butt_joint():
    """Extends the user-selected source face (or the smallest planar face touching a
    selected edge/vertex) outward until it reaches the user-selected target face,
    closing a butt joint so the existing overlap-based finger-joint pipeline can run."""
    sourceEntity = active_selections.get('extendSource')
    targetFace = active_selections.get('extendTargetFace')
    if sourceEntity is None or targetFace is None:
        ui.messageBox("Please select both a source (edge, corner, or face) and a target face to extend to.")
        return False

    sourceFace = geometry.resolveSourceFace(sourceEntity)
    if sourceFace is None:
        ui.messageBox("Could not find a planar face to extend from that selection.")
        return False

    try:
        direction = geometry.getFaceOutwardNormal(sourceFace)
        length = geometry.extensionLengthToFace(sourceFace, direction, targetFace)
    except Exception:
        ui.messageBox(f'Could not compute the extension:\n{traceback.format_exc()}')
        return False

    if length <= 0:
        ui.messageBox("The target face is on the wrong side of the source face - check your selections.")
        return False

    activeComponent = app.activeProduct.activeComponent
    design = activeComponent.parentDesign
    prevType = design.designType
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    try:
        try:
            extFeat = createExtensionFeature(activeComponent, sourceFace, length)
        except Exception:
            ui.messageBox(f'Could not create the extension feature:\n{traceback.format_exc()}')
            return False
        adsk.doEvents()
    finally:
        design.designType = prevType

    active_selections['extendSource'] = None
    active_selections['extendTargetFace'] = None
    palette = ui.palettes.itemById(palette_id)
    if palette:
        palette.sendInfoToHTML('selection_updated', json.dumps({'target': 'extendSource', 'count': 0}))
        palette.sendInfoToHTML('selection_updated', json.dumps({'target': 'extendTargetFace', 'count': 0}))

    return True


def close_extend_loop_group():
    """Wraps every feature created since the "Close Butt Joint" loop started (extend_loop_start_index)
    into a single CFG_Extend_XXX timeline group, covering all iterations of the select/select/extend
    cycle rather than one group per extension. No-ops if the loop never created a feature.
    This is purely organizational (timeline display) — each extension is still its own native Undo
    step, since the loop is built from repeated Selection Commands and Fusion gives each completed
    Command its own Undo entry; there's no public API to merge separate Commands into one Ctrl+Z."""
    global extend_loop_start_index
    start_idx = extend_loop_start_index
    extend_loop_start_index = None
    if start_idx is None:
        return
    try:
        design = app.activeProduct.activeComponent.parentDesign
        end_idx = design.timeline.count - 1
        if end_idx < start_idx:
            return
        # extend_face_to_close_butt_joint() reverts designType to whatever it was before each
        # extension, so by the time the loop ends we may be back in Direct Design mode, where
        # timelineGroups.add() fails; force Parametric for the duration of the grouping call.
        prevType = design.designType
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        try:
            max_num = 0
            for group in design.timeline.timelineGroups:
                if group.name.startswith("CFG_Extend_"):
                    try: max_num = max(max_num, int(group.name.split("_")[-1]))
                    except ValueError: pass
            new_group = design.timeline.timelineGroups.add(start_idx, end_idx)
            new_group.name = f"CFG_Extend_{max_num + 1:03d}"
        finally:
            design.designType = prevType
    except: pass


def clear_preview():
    """Removes any temporary red preview graphics from the canvas."""
    try:
        if app and app.activeProduct:
            root = app.activeProduct.rootComponent
            groups_to_delete = [grp for grp in root.customGraphicsGroups if grp.id == preview_group_id]
            for grp in groups_to_delete:
                grp.deleteMe()
            app.activeViewport.refresh()
    except:
        pass


def apply_payload_settings(inputs, payload):
    """Copies the joint-parameter fields of an HTML payload onto a FingerJointFeatureInput."""
    inputs.dynamicSizeType = payload.get('dynamicSizeType', inputs.dynamicSizeType)
    inputs.placementType = payload.get('placementType', inputs.placementType)
    inputs.jointType = payload.get('jointType', inputs.jointType)
    inputs.reverseTaper = payload.get('reverseTaper', False)
    inputs.isNumberOfFingersFixed = payload.get('isNumberOfFingersFixed', False)

    if payload.get('fixedNumFingers'): inputs.fixedNumFingers = int(payload.get('fixedNumFingers'))
    if payload.get('fixedNotchSize'): inputs.fixedNotchSize.expression = payload.get('fixedNotchSize')
    if payload.get('fixedFingerSize'): inputs.fixedFingerSize.expression = payload.get('fixedFingerSize')
    if payload.get('minNotchSize'): inputs.minNotchSize.expression = payload.get('minNotchSize')
    if payload.get('minFingerSize'): inputs.minFingerSize.expression = payload.get('minFingerSize')
    if payload.get('gap'): inputs.gap.expression = payload.get('gap')
    if payload.get('gapToPart'): inputs.gapToPart.expression = payload.get('gapToPart')
    if payload.get('dovetailAngle'): inputs.dovetailAngle.expression = payload.get('dovetailAngle')


def preview_joints(payload):
    """Calculates tool bodies and displays them as temporary red blocks."""
    clear_preview()
    inputs = options.FingerJointFeatureInput()

    inputs.body0 = active_selections['body0']
    inputs.body1 = active_selections['body1']
    inputs.direction = active_selections['direction']

    apply_payload_settings(inputs, payload)

    bodies0 = inputs.body0
    bodies1 = inputs.body1

    if not bodies0 or not bodies1:
        ui.messageBox("Please select at least one First Body and one Second Body to preview.")
        return False

    success = True
    all_tool_bodies = []
    
    for b0 in bodies0:
        for b1 in bodies1:
            inputs.body0 = b0
            inputs.body1 = b1
            toolBodies = geometry.createToolBodies(inputs)
            if toolBodies is True: continue
            elif toolBodies is False: success = False
            else: all_tool_bodies.append((toolBodies[0], toolBodies[1]))
            
    if all_tool_bodies:
        des = app.activeProduct
        root = des.rootComponent
        cgGroup = root.customGraphicsGroups.add()
        cgGroup.id = preview_group_id
        
        face_color = adsk.core.Color.create(255, 255, 0, 150) # Translucent Yellow
        face_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(face_color)
        
        edge_color = adsk.core.Color.create(255, 0, 0, 255) # Solid Red
        edge_effect = adsk.fusion.CustomGraphicsSolidColorEffect.create(edge_color)
        
        for t0, t1 in all_tool_bodies:
            cg0 = cgGroup.addBRepBody(t0)
            cg0.color = face_effect
            cg1 = cgGroup.addBRepBody(t1)
            cg1.color = face_effect
            
            # Explicitly draw thick red edges
            for tool_body in (t0, t1):
                for edge in tool_body.edges:
                    try:
                        crv = cgGroup.addCurve(edge.geometry)
                        crv.color = edge_effect
                        crv.weight = 2
                    except: pass
            
        app.activeViewport.refresh()

    if not success:
        ui.messageBox("Could not compute some joints. Double-check dimensions and overlaps.")
        return False

    return True


def _create_joint_features(inputs, bodies0, bodies1, result):
    """Computes tool bodies and creates the base/cut features for every body0 x body1 pair.
    Runs entirely inside the hidden undo-group command's execute handler (see _run_grouped), so
    Fusion bundles every feature created here - across every pair - into a single native Undo
    entry instead of one entry per feature."""
    success = True
    computed_any = False

    tempBRep = adsk.fusion.TemporaryBRepManager.get()
    master_tools_0 = {b.entityToken: None for b in bodies0}
    master_tools_1 = {b.entityToken: None for b in bodies1}

    for b0 in bodies0:
        for b1 in bodies1:
            inputs.body0 = b0
            inputs.body1 = b1
            toolBodies = geometry.createToolBodies(inputs)
            if toolBodies is True:
                continue
            elif toolBodies is False:
                success = False
            else:
                computed_any = True
                t0, t1 = toolBodies
                if master_tools_0[b0.entityToken] is None:
                    master_tools_0[b0.entityToken] = t0
                else:
                    tempBRep.booleanOperation(master_tools_0[b0.entityToken], t0, adsk.fusion.BooleanTypes.UnionBooleanType)

                if master_tools_1[b1.entityToken] is None:
                    master_tools_1[b1.entityToken] = t1
                else:
                    tempBRep.booleanOperation(master_tools_1[b1.entityToken], t1, adsk.fusion.BooleanTypes.UnionBooleanType)

    if not success:
        result['success'] = False
        return

    if computed_any:
        activeComponent = app.activeProduct.activeComponent
        design = activeComponent.parentDesign
        prevType = design.designType
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        created_features = []

        for b0 in bodies0:
            tool = master_tools_0[b0.entityToken]
            if tool:
                tFeat = createBaseFeature(activeComponent, tool, "FJL_Fingers")
                if tFeat:
                    created_features.append(tFeat)
                    cFeat = createCutFeature(activeComponent, b0, tFeat)
                    if cFeat: created_features.append(cFeat)

        for b1 in bodies1:
            tool = master_tools_1[b1.entityToken]
            if tool:
                tFeat = createBaseFeature(activeComponent, tool, "FJL_Notches")
                if tFeat:
                    created_features.append(tFeat)
                    cFeat = createCutFeature(activeComponent, b1, tFeat)
                    if cFeat: created_features.append(cFeat)

        if created_features and design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
            valid_indices = []
            for f in created_features:
                try:
                    if f and hasattr(f, 'timelineObject') and f.timelineObject and f.timelineObject.isValid:
                        valid_indices.append(f.timelineObject.index)
                except:
                    pass

            if valid_indices:
                first_idx = min(valid_indices)
                last_idx = max(valid_indices)

                max_num = 0
                for group in design.timeline.timelineGroups:
                    if group.name.startswith("CFG_Joint_"):
                        try: max_num = max(max_num, int(group.name.split("_")[-1]))
                        except ValueError: pass

                try:
                    new_group = design.timeline.timelineGroups.add(first_idx, last_idx)
                    new_group.name = f"CFG_Joint_{max_num + 1:03d}"
                except: pass

        design.designType = prevType

    result['success'] = True


def execute_joints(payload):
    """Parses HTML settings, merges with active selections, and generates the joints."""
    try:
        clear_preview()
        inputs = options.FingerJointFeatureInput()

        inputs.body0 = active_selections['body0']
        inputs.body1 = active_selections['body1']
        inputs.direction = active_selections['direction']

        apply_payload_settings(inputs, payload)

        bodies0 = inputs.body0
        bodies1 = inputs.body1

        if not bodies0 or not bodies1:
            ui.messageBox("Please select at least one First Body and one Second Body.")
            return False

        result = {'success': True}
        _run_grouped(lambda: _create_joint_features(inputs, bodies0, bodies1, result), 'FJL Generate Joints')

        if not result['success']:
            ui.messageBox("Could not compute some joints. Double-check dimensions and overlaps.")
            return False

        inputs.writeDefaults()

        try:
            doc = app.activeDocument
            if doc: doc.attributes.add('FingerJointsLive', 'LastUsedInDoc', json.dumps(payload))
        except: pass

        return True
    except:
        if ui: ui.messageBox(f'Joint Generation Failed:\n{traceback.format_exc()}')
        return False


# --- NATIVE SELECTION HANDLERS ---
class SelectionCommandExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, target, sel_input):
        super().__init__()
        self.target = target
        self.sel_input = sel_input
        
    def notify(self, args):
        clear_preview() # Clear preview if selections change
        global active_selections
        selections = [self.sel_input.selection(i).entity for i in range(self.sel_input.selectionCount)]

        if self.target in ('direction', 'extendSource', 'extendTargetFace'):
            active_selections[self.target] = selections[0] if selections else None
        else:
            active_selections[self.target] = selections
            
        # Tell the HTML to update the button text
        palette = ui.palettes.itemById(palette_id)
        if palette:
            count = len(selections)
            palette.sendInfoToHTML('selection_updated', json.dumps({'target': self.target, 'count': count}))

        # Chain the "close butt joint" loop: source -> target face -> extend -> back to source.
        # An empty selection (OK clicked with nothing picked) ends the loop, same as Cancel; both
        # are caught by ExtendLoopDestroyHandler, which closes the loop's timeline group since
        # extend_loop_chaining is only set True (suppressing that close) on an actual chain step.
        global extend_loop_chaining
        if self.target == 'extendSource' and selections:
            cmd_def = ui.commandDefinitions.itemById('FJL_Select_extendTargetFace')
            if cmd_def:
                extend_loop_chaining = True
                cmd_def.execute()
        elif self.target == 'extendTargetFace' and selections:
            extend_face_to_close_butt_joint()
            cmd_def = ui.commandDefinitions.itemById('FJL_Select_extendSource')
            if cmd_def:
                extend_loop_chaining = True
                cmd_def.execute()

class SelectionCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, target):
        super().__init__()
        self.target = target
        
    def notify(self, args):
        try:
            cmd = args.command

            prompt = ''
            if self.target == 'body0':
                prompt = 'Select one or more 1st bodies (e.g., opposite box walls), then click OK.'
            elif self.target == 'body1':
                prompt = 'Select one or more 2nd bodies (e.g., opposite box walls), then click OK.'
            elif self.target == 'direction':
                prompt = 'Select a linear edge to set direction, or click OK to auto-detect.'
            elif self.target == 'extendSource':
                prompt = 'Select an edge, corner, or face on the body to extend, then click OK.'
            elif self.target == 'extendTargetFace':
                prompt = 'Select the face to extend to, then click OK.'

            selInput = cmd.commandInputs.addSelectionInput(f'sel_{self.target}', f'Select {TARGET_LABELS[self.target]}', prompt)

            if self.target == 'direction':
                selInput.addSelectionFilter('LinearEdges')
                selInput.addSelectionFilter('SketchLines')
                selInput.setSelectionLimits(0, 1)
            elif self.target == 'extendSource':
                selInput.addSelectionFilter('Vertices')
                selInput.addSelectionFilter('Edges')
                selInput.addSelectionFilter('PlanarFaces')
                selInput.setSelectionLimits(0, 1)
            elif self.target == 'extendTargetFace':
                selInput.addSelectionFilter('PlanarFaces')
                selInput.setSelectionLimits(0, 1)
            else:
                selInput.addSelectionFilter('SolidBodies')
                selInput.setSelectionLimits(0, 0) # 0 allows clearing selections

            # Pre-select existing entities so the user doesn't lose their previous picks
            global active_selections
            existing = active_selections.get(self.target)
            if existing:
                if isinstance(existing, list):
                    for ent in existing:
                        try: selInput.addSelection(ent)
                        except: pass
                else:
                    try: selInput.addSelection(existing)
                    except: pass

            self.onExecute = SelectionCommandExecuteHandler(self.target, selInput)
            cmd.execute.add(self.onExecute)

            # The extend loop ends whenever an extendSource/extendTargetFace command terminates
            # without immediately chaining to the next step (OK-with-nothing-selected, or Cancel).
            if self.target in ('extendSource', 'extendTargetFace'):
                self.onDestroy = ExtendLoopDestroyHandler()
                cmd.destroy.add(self.onDestroy)
        except Exception:
            if ui: ui.messageBox(f'Could not create selection dialog for "{self.target}":\n{traceback.format_exc()}')


class ExtendLoopDestroyHandler(adsk.core.CommandEventHandler):
    """Closes the extend loop's timeline group once the select/select/extend cycle truly ends.
    extend_loop_chaining is set True right before chaining to the next selection command, so a
    destroy event that finds it False means this termination (Cancel, or OK with nothing picked)
    is the real end of the loop rather than a step in the middle of it."""
    def notify(self, args):
        global extend_loop_chaining
        if extend_loop_chaining:
            extend_loop_chaining = False
            return
        close_extend_loop_group()


# --- HTML ROUTER ---
class MyHTMLEventHandler(adsk.core.HTMLEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        try:
            html_args = adsk.core.HTMLEventArgs.cast(args)
            data = json.loads(html_args.data)
            action = data.get('action')

            if action in ('select_body0', 'select_body1', 'select_direction'):
                target = action.replace('select_', '')
                cmd_def_id = f'FJL_Select_{target}'

                cmd_def = ui.commandDefinitions.itemById(cmd_def_id)
                if cmd_def:
                    cmd_def.execute()
                else:
                    ui.messageBox(f'Selection command "{cmd_def_id}" is not registered. '
                                  'Please fully Stop and Run the add-in again (a plain Reload may not re-register new commands).')

            elif action == 'generate':
                execute_joints(data.get('payload'))

            elif action == 'preview':
                preview_joints(data.get('payload'))

            elif action == 'extend_loop_start':
                global extend_loop_start_index
                try:
                    extend_loop_start_index = app.activeProduct.activeComponent.parentDesign.timeline.count
                except Exception:
                    extend_loop_start_index = None
                cmd_def = ui.commandDefinitions.itemById('FJL_Select_extendSource')
                if cmd_def:
                    cmd_def.execute()
                else:
                    ui.messageBox('Selection command "FJL_Select_extendSource" is not registered. '
                                  'Please fully Stop and Run the add-in again (a plain Reload may not re-register new commands).')

            elif action == 'save_settings':
                prefs = options.FingerJointFeatureInput()
                apply_payload_settings(prefs, data.get('payload', {}))
                prefs.collapsedSections = data.get('payload', {}).get('collapsedSections', {})
                prefs.writeDefaults()


            elif action == 'clear_selections':
                global active_selections
                active_selections['body0'] = []
                active_selections['body1'] = []
                active_selections['direction'] = None
                clear_preview()
                
                palette = ui.palettes.itemById(palette_id)
                if palette:
                    palette.sendInfoToHTML('selection_updated', json.dumps({'target': 'body0', 'count': 0}))
                    palette.sendInfoToHTML('selection_updated', json.dumps({'target': 'body1', 'count': 0}))
                    palette.sendInfoToHTML('selection_updated', json.dumps({'target': 'direction', 'count': 0}))
                
            elif action == 'save_preset':
                presets = load_presets_dict()
                presets[data.get('name')] = data.get('payload')
                save_presets_dict(presets)
                palette = ui.palettes.itemById(palette_id)
                if palette: palette.sendInfoToHTML('update_presets', json.dumps({'presets': list(presets.keys()), 'selected': data.get('name')}))

            elif action == 'load_preset':
                presets = load_presets_dict()
                name = data.get('name')
                if name in presets:
                    palette = ui.palettes.itemById(palette_id)
                    if palette: palette.sendInfoToHTML('load_defaults', json.dumps(presets[name]))

            elif action == 'delete_preset':
                presets = load_presets_dict()
                name = data.get('name')
                if name in presets:
                    del presets[name]
                    save_presets_dict(presets)
                    palette = ui.palettes.itemById(palette_id)
                    if palette: palette.sendInfoToHTML('update_presets', json.dumps({'presets': list(presets.keys()), 'selected': ''}))

            elif action == 'reset_defaults':
                try:
                    doc = app.activeDocument
                    if doc:
                        attr = doc.attributes.itemByName('FingerJointsLive', 'LastUsedInDoc')
                        if attr: attr.deleteMe()
                except: pass
                
                defaults = options.FingerJointFeatureInput()
                defaults_dict = {
                    'dynamicSizeType': defaults.dynamicSizeType,
                    'placementType': defaults.placementType,
                    'jointType': defaults.jointType,
                    'dovetailAngle': defaults.dovetailAngle.expression,
                    'reverseTaper': defaults.reverseTaper,
                    'isNumberOfFingersFixed': defaults.isNumberOfFingersFixed,
                    'fixedNumFingers': defaults.fixedNumFingers,
                    'fixedNotchSize': defaults.fixedNotchSize.expression,
                    'fixedFingerSize': defaults.fixedFingerSize.expression,
                    'minNotchSize': defaults.minNotchSize.expression,
                    'minFingerSize': defaults.minFingerSize.expression,
                    'gap': defaults.gap.expression,
                    'gapToPart': defaults.gapToPart.expression,
                    'isPreviewEnabled': defaults.isPreviewEnabled,
                    'theme': defaults.theme,
                    'collapsedSections': defaults.collapsedSections
                }
                presets = load_presets_dict()
                defaults_dict['presets'] = list(presets.keys())
                defaults_dict['selectedPreset'] = ''
                defaults_dict['imported_themes'] = load_imported_themes()
                defaults_dict['addin_version'] = ADDIN_VERSION
                palette = ui.palettes.itemById(palette_id)
                if palette: palette.sendInfoToHTML('load_defaults', json.dumps(defaults_dict))

            elif action == 'save_theme':
                inputs = options.FingerJointFeatureInput()
                inputs.theme = data.get('theme', 'default')
                inputs.writeDefaults()

            elif action == 'save_imported_theme':
                theme_id = data.get('id')
                theme_vars = data.get('vars')
                if theme_id and isinstance(theme_vars, dict):
                    save_imported_theme(theme_id, theme_vars)

            elif action == 'remove_imported_theme':
                theme_id = data.get('id')
                if theme_id:
                    delete_imported_theme(theme_id)

            elif action == 'reset_imported_themes':
                clear_imported_themes()

            elif action == 'import_file':
                file_type = data.get('file_type')
                dlg = ui.createFileDialog()
                dlg.title = f"Import {file_type.upper()} Theme"
                dlg.filter = f"{file_type.upper()} Files (*.{file_type})"
                dlg.initialDirectory = _themes_dialog_dir()
                if dlg.showOpen() == adsk.core.DialogResults.DialogOK:
                    try:
                        with open(dlg.filename, 'r', encoding='utf-8') as f:
                            content = f.read()
                        palette = ui.palettes.itemById(palette_id)
                        if palette:
                            palette.sendInfoToHTML('file_imported', json.dumps({'file_type': file_type, 'content': content}))
                    except Exception as e:
                        ui.messageBox(f"Error reading file:\n{e}")

            elif action == 'export_file':
                file_type = data.get('file_type')
                content = data.get('content')
                default_name = data.get('default_name', f'theme.{file_type}')
                dlg = ui.createFileDialog()
                dlg.title = f"Export {file_type.upper()} Theme"
                dlg.filter = f"{file_type.upper()} Files (*.{file_type})"
                dlg.initialDirectory = _themes_dialog_dir()
                dlg.initialFilename = default_name
                if dlg.showSave() == adsk.core.DialogResults.DialogOK:
                    try:
                        with open(dlg.filename, 'w', encoding='utf-8') as f: f.write(content)
                    except Exception as e: ui.messageBox(f"Error saving file:\n{e}")

            elif action == 'html_loaded':
                defaults = options.FingerJointFeatureInput()
                defaults_dict = {
                    'dynamicSizeType': defaults.dynamicSizeType,
                    'placementType': defaults.placementType,
                    'jointType': defaults.jointType,
                    'dovetailAngle': defaults.dovetailAngle.expression,
                    'reverseTaper': defaults.reverseTaper,
                    'isNumberOfFingersFixed': defaults.isNumberOfFingersFixed,
                    'fixedNumFingers': defaults.fixedNumFingers,
                    'fixedNotchSize': defaults.fixedNotchSize.expression,
                    'fixedFingerSize': defaults.fixedFingerSize.expression,
                    'minNotchSize': defaults.minNotchSize.expression,
                    'minFingerSize': defaults.minFingerSize.expression,
                    'gap': defaults.gap.expression,
                    'gapToPart': defaults.gapToPart.expression,
                    'isPreviewEnabled': defaults.isPreviewEnabled,
                    'theme': defaults.theme,
                    'collapsedSections': defaults.collapsedSections
                }

                # Check if this document has a saved preset attribute from a previous run
                try:
                    doc = app.activeDocument
                    if doc:
                        attr = doc.attributes.itemByName('FingerJointsLive', 'LastUsedInDoc')
                        if attr and attr.value:
                            doc_defaults = json.loads(attr.value)
                            defaults_dict.update(doc_defaults) # Override defaults with doc settings
                except: pass
                
                # Read the baseline style.css and pass it to HTML for parsing
                try:
                    script_folder = os.path.dirname(os.path.realpath(__file__))
                    style_path = os.path.join(script_folder, 'resources', 'style.css')
                    if os.path.exists(style_path):
                        with open(style_path, 'r', encoding='utf-8') as f: defaults_dict['style_css'] = f.read()
                except: pass

                # Merge presets into the same payload to avoid CEF dropping back-to-back messages
                presets = load_presets_dict()
                defaults_dict['presets'] = list(presets.keys())
                defaults_dict['selectedPreset'] = ''
                defaults_dict['imported_themes'] = load_imported_themes()
                defaults_dict['addin_version'] = ADDIN_VERSION

                palette = ui.palettes.itemById(palette_id)
                if palette:
                    palette.sendInfoToHTML('load_defaults', json.dumps(defaults_dict))

        except Exception as e:
            if ui: ui.messageBox(f'HTML Event Failed:\n{traceback.format_exc()}')


def save_palette_geometry():
    """Remembers the palette's current docking state, size, and (if floating) position
    so it can be restored the next time the palette is opened."""
    try:
        palette = ui.palettes.itemById(palette_id)
        if not palette:
            return
        prefs = options.FingerJointFeatureInput()
        prefs.paletteDockingState = int(palette.dockingState)
        prefs.paletteWidth = palette.width
        prefs.paletteHeight = palette.height
        prefs.paletteLeft = palette.left
        prefs.paletteTop = palette.top
        prefs.writeDefaults()
    except:
        pass


class MyPaletteCloseHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        save_palette_geometry()
        clear_preview()


class MyCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        try:
            old = ui.palettes.itemById(palette_id)
            if old: old.deleteMe()

            script_folder = os.path.dirname(os.path.realpath(__file__))
            html_path = os.path.join(script_folder, 'resources', 'fingerjointslive_index.html')
            url = 'file:///' + html_path.replace('\\', '/') + f'?t={time.time()}'

            prefs = options.FingerJointFeatureInput()
            palette = ui.palettes.add(palette_id, 'Finger Joints Live', url, True, True, True,
                                       prefs.paletteWidth, prefs.paletteHeight)
            palette.dockingState = prefs.paletteDockingState
            if prefs.paletteDockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
                palette.setPosition(prefs.paletteLeft, prefs.paletteTop)

            onHtmlEvent = MyHTMLEventHandler()
            palette.incomingFromHTML.add(onHtmlEvent)
            handlers.append(onHtmlEvent)
            
            onClose = MyPaletteCloseHandler()
            palette.closed.add(onClose)
            handlers.append(onClose)
            
            palette.isVisible = True
        except: pass


def run(context):
    global ui, app
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        
        cmdDef = ui.commandDefinitions.itemById(command_id)
        if not cmdDef:
            res_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'resources/ui/command_button')
            cmdDef = ui.commandDefinitions.addButtonDefinition(command_id, 'Finger Joints Live', 'An updated, palette-based UI, add-in for creating finger joints (box joints) from the overlap of two bodies.', res_dir)

            tool_clip_path = os.path.join(res_dir, 'FingerJointsLiveThumb.png')
            if os.path.exists(tool_clip_path):
                cmdDef.toolClipFilename = tool_clip_path
            
        onCreated = MyCommandCreatedHandler()
        cmdDef.commandCreated.add(onCreated)
        handlers.append(onCreated)
        
        # Hidden, UI-less command used purely to get Fusion's automatic per-Command Undo-transaction
        # bundling for work triggered from non-command code (see _run_grouped). Never added to a
        # toolbar/panel, so it's invisible to the user.
        undoGroupCmdDef = ui.commandDefinitions.itemById(undo_group_command_id)
        if undoGroupCmdDef: undoGroupCmdDef.deleteMe()
        undoGroupCmdDef = ui.commandDefinitions.addButtonDefinition(undo_group_command_id, 'FingerJointsLive Grouped Work', '')
        onUndoGroupCreated = UndoGroupCreatedHandler()
        undoGroupCmdDef.commandCreated.add(onUndoGroupCreated)
        handlers.append(onUndoGroupCreated)

        # Pre-register Selection Commands
        for target in ['body0', 'body1', 'direction', 'extendSource', 'extendTargetFace']:
            c_id = f'FJL_Select_{target}'
            cdef = ui.commandDefinitions.itemById(c_id)
            if cdef: cdef.deleteMe()
            cdef = ui.commandDefinitions.addButtonDefinition(c_id, f'Select {TARGET_LABELS[target]}', '')
            handler = SelectionCommandCreatedHandler(target)
            cdef.commandCreated.add(handler)
            handlers.append(handler)

        panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        ctrl = panel.controls.addCommand(cmdDef)
        ctrl.isPromoted = True
    except:
        pass


def stop(context):
    save_palette_geometry()
    clear_preview()
    try:
        if ui.palettes.itemById(palette_id): ui.palettes.itemById(palette_id).deleteMe()
        if ui.commandDefinitions.itemById(command_id): ui.commandDefinitions.itemById(command_id).deleteMe()
        if ui.commandDefinitions.itemById(undo_group_command_id): ui.commandDefinitions.itemById(undo_group_command_id).deleteMe()
        for target in ['body0', 'body1', 'direction', 'extendSource', 'extendTargetFace']:
            c_id = f'FJL_Select_{target}'
            if ui.commandDefinitions.itemById(c_id): ui.commandDefinitions.itemById(c_id).deleteMe()
        panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        if panel.controls.itemById(command_id): panel.controls.itemById(command_id).deleteMe()
    except: pass
