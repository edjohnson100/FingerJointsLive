# Author: Florian Pommerening
# Description: An Add-In for making finger joints.

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

# Global state to hold selections (since HTML cannot hold Fusion BRep objects)
active_selections = {
    'body0': [],
    'body1': [],
    'direction': None
}

# Global state to hold payload data so the invisible command can execute it
joint_payload_to_execute = None

PRESETS_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'presets.json')

def load_presets_dict():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {}

def save_presets_dict(d):
    with open(PRESETS_FILE, 'w') as f: json.dump(d, f, indent=4)

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

# --- HIDDEN COMMAND FOR UNDO GROUPING ---
class GenerateJointsExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        global joint_payload_to_execute
        if joint_payload_to_execute:
            execute_joints(joint_payload_to_execute)
            joint_payload_to_execute = None

class GenerateJointsCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
        onExecute = GenerateJointsExecuteHandler()
        args.command.execute.add(onExecute)
        handlers.append(onExecute)

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


def preview_joints(payload):
    """Calculates tool bodies and displays them as temporary red blocks."""
    clear_preview()
    inputs = options.FingerJointFeatureInput()
    
    inputs.body0 = active_selections['body0']
    inputs.body1 = active_selections['body1']
    inputs.direction = active_selections['direction']
    
    inputs.dynamicSizeType = payload.get('dynamicSizeType')
    inputs.placementType = payload.get('placementType')
    inputs.isNumberOfFingersFixed = payload.get('isNumberOfFingersFixed', False)
    
    if payload.get('fixedNumFingers'): inputs.fixedNumFingers = int(payload.get('fixedNumFingers'))
    if payload.get('fixedNotchSize'): inputs.fixedNotchSize.expression = payload.get('fixedNotchSize')
    if payload.get('fixedFingerSize'): inputs.fixedFingerSize.expression = payload.get('fixedFingerSize')
    if payload.get('minNotchSize'): inputs.minNotchSize.expression = payload.get('minNotchSize')
    if payload.get('minFingerSize'): inputs.minFingerSize.expression = payload.get('minFingerSize')
    if payload.get('gap'): inputs.gap.expression = payload.get('gap')
    if payload.get('gapToPart'): inputs.gapToPart.expression = payload.get('gapToPart')

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
        
    return True


def execute_joints(payload):
    """Parses HTML settings, merges with active selections, and generates the joints."""
    try:
        clear_preview()
        inputs = options.FingerJointFeatureInput()
        
        inputs.body0 = active_selections['body0']
        inputs.body1 = active_selections['body1']
        inputs.direction = active_selections['direction']
        
        inputs.dynamicSizeType = payload.get('dynamicSizeType')
        inputs.placementType = payload.get('placementType')
        inputs.isNumberOfFingersFixed = payload.get('isNumberOfFingersFixed', False)
        
        if payload.get('fixedNumFingers'): inputs.fixedNumFingers = int(payload.get('fixedNumFingers'))
        if payload.get('fixedNotchSize'): inputs.fixedNotchSize.expression = payload.get('fixedNotchSize')
        if payload.get('fixedFingerSize'): inputs.fixedFingerSize.expression = payload.get('fixedFingerSize')
        if payload.get('minNotchSize'): inputs.minNotchSize.expression = payload.get('minNotchSize')
        if payload.get('minFingerSize'): inputs.minFingerSize.expression = payload.get('minFingerSize')
        if payload.get('gap'): inputs.gap.expression = payload.get('gap')
        if payload.get('gapToPart'): inputs.gapToPart.expression = payload.get('gapToPart')

        bodies0 = inputs.body0
        bodies1 = inputs.body1

        if not bodies0 or not bodies1:
            ui.messageBox("Please select at least one First Body and one Second Body.")
            return False

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
            ui.messageBox("Could not compute some joints. Double-check dimensions and overlaps.")
            return False
            
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
        
        if self.target == 'direction':
            active_selections['direction'] = selections[0] if selections else None
        else:
            active_selections[self.target] = selections
            
        # Tell the HTML to update the button text
        palette = ui.palettes.itemById(palette_id)
        if palette:
            count = len(selections)
            palette.sendInfoToHTML('selection_updated', json.dumps({'target': self.target, 'count': count}))

class SelectionCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, target):
        super().__init__()
        self.target = target
        
    def notify(self, args):
        cmd = args.command
        
        prompt = ''
        if self.target == 'body0':
            prompt = 'Select one or more 1st bodies (e.g., opposite box walls), then click OK.'
        elif self.target == 'body1':
            prompt = 'Select one or more 2nd bodies (e.g., opposite box walls), then click OK.'
        elif self.target == 'direction':
            prompt = 'Select a linear edge to set direction, or click OK to auto-detect.'
            
        selInput = cmd.commandInputs.addSelectionInput(f'sel_{self.target}', f'Select {self.target}', prompt)
        
        if self.target == 'direction':
            selInput.addSelectionFilter('LinearEdges')
            selInput.addSelectionFilter('SketchLines')
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
                
            elif action == 'generate':
                global joint_payload_to_execute
                joint_payload_to_execute = data.get('payload')
                cmd_def = ui.commandDefinitions.itemById('FJL_Generate_Joints_Cmd')
                if cmd_def:
                    cmd_def.execute()
                
            elif action == 'preview':
                preview_joints(data.get('payload'))
                
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
                    'isNumberOfFingersFixed': defaults.isNumberOfFingersFixed,
                    'fixedNumFingers': defaults.fixedNumFingers,
                    'fixedNotchSize': defaults.fixedNotchSize.expression,
                    'fixedFingerSize': defaults.fixedFingerSize.expression,
                    'minNotchSize': defaults.minNotchSize.expression,
                    'minFingerSize': defaults.minFingerSize.expression,
                    'gap': defaults.gap.expression,
                    'gapToPart': defaults.gapToPart.expression,
                    'isPreviewEnabled': defaults.isPreviewEnabled,
                    'theme': defaults.theme
                }
                presets = load_presets_dict()
                defaults_dict['presets'] = list(presets.keys())
                defaults_dict['selectedPreset'] = ''
                palette = ui.palettes.itemById(palette_id)
                if palette: palette.sendInfoToHTML('load_defaults', json.dumps(defaults_dict))

            elif action == 'save_theme':
                inputs = options.FingerJointFeatureInput()
                inputs.theme = data.get('theme', 'default')
                inputs.writeDefaults()

            elif action == 'import_file':
                file_type = data.get('file_type')
                dlg = ui.createFileDialog()
                dlg.title = f"Import {file_type.upper()} Theme"
                dlg.filter = f"{file_type.upper()} Files (*.{file_type})"
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
                    'isNumberOfFingersFixed': defaults.isNumberOfFingersFixed,
                    'fixedNumFingers': defaults.fixedNumFingers,
                    'fixedNotchSize': defaults.fixedNotchSize.expression,
                    'fixedFingerSize': defaults.fixedFingerSize.expression,
                    'minNotchSize': defaults.minNotchSize.expression,
                    'minFingerSize': defaults.minFingerSize.expression,
                    'gap': defaults.gap.expression,
                    'gapToPart': defaults.gapToPart.expression,
                    'isPreviewEnabled': defaults.isPreviewEnabled,
                    'theme': defaults.theme
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
                
                palette = ui.palettes.itemById(palette_id)
                if palette:
                    palette.sendInfoToHTML('load_defaults', json.dumps(defaults_dict))

        except Exception as e:
            if ui: ui.messageBox(f'HTML Event Failed:\n{traceback.format_exc()}')


class MyPaletteCloseHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def __init__(self): super().__init__()
    def notify(self, args):
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
            
            palette = ui.palettes.add(palette_id, 'Finger Joints Live', url, True, True, True, 340, 600)
            palette.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
            
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
            cmdDef = ui.commandDefinitions.addButtonDefinition(command_id, 'Finger Joints Live', '', res_dir)
            
        onCreated = MyCommandCreatedHandler()
        cmdDef.commandCreated.add(onCreated)
        handlers.append(onCreated)
        
        # Pre-register Hidden Generate Command (Wraps action in a single Undo step)
        gen_cmd = ui.commandDefinitions.itemById('FJL_Generate_Joints_Cmd')
        if gen_cmd: gen_cmd.deleteMe()
        gen_cmd = ui.commandDefinitions.addButtonDefinition('FJL_Generate_Joints_Cmd', 'Generate Finger Joints', '')
        gen_handler = GenerateJointsCommandCreatedHandler()
        gen_cmd.commandCreated.add(gen_handler)
        handlers.append(gen_handler)
        
        # Pre-register Selection Commands
        for target in ['body0', 'body1', 'direction']:
            c_id = f'FJL_Select_{target}'
            cdef = ui.commandDefinitions.itemById(c_id)
            if cdef: cdef.deleteMe()
            cdef = ui.commandDefinitions.addButtonDefinition(c_id, f'Select {target}', '')
            handler = SelectionCommandCreatedHandler(target)
            cdef.commandCreated.add(handler)
            handlers.append(handler)

        panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        ctrl = panel.controls.addCommand(cmdDef)
        ctrl.isPromoted = True
    except:
        pass


def stop(context):
    clear_preview()
    try:
        if ui.palettes.itemById(palette_id): ui.palettes.itemById(palette_id).deleteMe()
        if ui.commandDefinitions.itemById(command_id): ui.commandDefinitions.itemById(command_id).deleteMe()
        if ui.commandDefinitions.itemById('FJL_Generate_Joints_Cmd'): ui.commandDefinitions.itemById('FJL_Generate_Joints_Cmd').deleteMe()
        for target in ['body0', 'body1', 'direction']:
            c_id = f'FJL_Select_{target}'
            if ui.commandDefinitions.itemById(c_id): ui.commandDefinitions.itemById(c_id).deleteMe()
        panel = ui.allToolbarPanels.itemById('SolidModifyPanel')
        if panel.controls.itemById(command_id): panel.controls.itemById(command_id).deleteMe()
    except: pass
