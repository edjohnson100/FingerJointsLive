import json
import os

import adsk.core

APP_PATH = os.path.dirname(os.path.abspath(__file__))

class DynamicSizeType:
    FIXED_NOTCH_SIZE = 'fixed notch size'
    FIXED_FINGER_SIZE = 'fixed finger size'
    EQUAL_NOTCH_AND_FINGER_SIZE = 'equal notch and finger size'

class PlacementType:
    FINGERS_OUTSIDE = 'fingers outside'
    NOTCHES_OUTSIDE = 'notches outside'
    SAME_NUMBER_START_FINGER = 'same number of fingers and notches (start with finger)'
    SAME_NUMBER_START_NOTCH = 'same number of fingers and notches (start with notch)'

class JointType:
    BOX = 'box'
    DOVETAIL = 'through dovetail'
    # Half-blind dovetails are a deferred follow-on; any shoulder-depth-style
    # fields they need attach here as new additive values, not a rework of this enum.

class DogBoneStyle:
    CORNER = 'corner'
    MINIMAL_CORNER = 'minimal corner'
    LONG_SIDE = 'long side'
    SHORT_SIDE = 'short side'

class DogBoneSelectionMode:
    BODY = 'body'
    FACE = 'face'
    EDGE = 'edge'

class FusionExpression(object):
    def __init__(self, expression, unitType=None):
        # unitType defaults to the design's length units (e.g. "mm"); pass "deg"
        # for angle expressions like dovetailAngle so validation checks the right dimension.
        self._expression = expression
        self._unitType = unitType

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, value):
        self._expression = value

    @property
    def value(self):
        unitsManager = adsk.core.Application.get().activeProduct.unitsManager
        unitType = self._unitType or unitsManager.defaultLengthUnits
        return unitsManager.evaluateExpression(self._expression, unitType)

    @property
    def isValid(self):
        unitsManager = adsk.core.Application.get().activeProduct.unitsManager
        unitType = self._unitType or unitsManager.defaultLengthUnits
        return unitsManager.isValidExpression(self._expression, unitType)


# Fusion distinguishes three types of parameters:
#  (1) Entities (objects in the design) are saved as dependencies.
#  (2) Values (numerical parameters, booleans?) are saved as custom parameters.
#  (3) Settings (choices in select boxes) are saved as named values.
# We want to keep track of all of them and store default values for values and settings.
class FingerJointFeatureInput(object):
    DEFAULTS_FILENAME = os.path.join(APP_PATH, 'defaults.json')
    DEFAULTS_DATA = {}

    def __init__(self):
        # Entities
        self.body0 = None
        self.body1 = None
        self.direction = None
        # Settings
        self.dynamicSizeType = DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE
        self.placementType = PlacementType.FINGERS_OUTSIDE
        self.jointType = JointType.BOX
        # Values
        self.dovetailAngle = FusionExpression("10 deg", unitType="deg")
        # Which face of the taper's depth axis ends up wide vs. narrow. The "right" direction
        # depends on the joint's physical context (corner vs. inline splice, which body is
        # body0/body1, direction-edge orientation) - not something the geometry can infer, so
        # it's a user-facing toggle rather than a hardcoded sign.
        self.reverseTaper = False
        self.isNumberOfFingersFixed = False
        self.fixedFingerSize = FusionExpression("20 mm")
        self.fixedNotchSize = FusionExpression("20 mm")
        self.minFingerSize = FusionExpression("20 mm")
        self.minNotchSize = FusionExpression("20 mm")
        self.fixedNumFingers = 3
        self.gap = FusionExpression("0 mm")
        self.gapToPart = FusionExpression("0 mm")
        self.isPreviewEnabled = True
        # How strongly the live preview washes the selected bodies in body0's/body1's
        # highlight colors (see FingerJointsLive.py's preview_joints) - purely a display
        # setting, doesn't affect the generated joint. Mapped to a custom-graphics alpha
        # value there since "dark" needs to stay usable against a wide range of material
        # appearances, not just Fusion's default light gray.
        self.previewOpacity = 'medium'
        self.theme = 'default'
        self.collapsedSections = {}
        # Palette window geometry (remembered across sessions).
        self.paletteDockingState = int(adsk.core.PaletteDockingStates.PaletteDockStateRight)
        self.paletteWidth = 340
        self.paletteHeight = 600
        self.paletteLeft = 100
        self.paletteTop = 100
        # Monitor arrangement at the time left/top were saved (see display_utils.py) -
        # lets a restore tell "still on the same monitors" from "layout changed since".
        self.paletteDisplayLayout = ''
        self.readDefaults()

    def writeDefaults(self):
        defaultData = {
            'dynamicSizeType': self.dynamicSizeType,
            'placementType': self.placementType,
            'jointType': self.jointType,
            'dovetailAngle': self.dovetailAngle.expression,
            'reverseTaper': self.reverseTaper,
            'isNumberOfFingersFixed': self.isNumberOfFingersFixed,
            'fixedFingerSize': self.fixedFingerSize.expression,
            'fixedNotchSize': self.fixedNotchSize.expression,
            'minFingerSize': self.minFingerSize.expression,
            'minNotchSize': self.minNotchSize.expression,
            'fixedNumFingers': self.fixedNumFingers,
            'gap': self.gap.expression,
            'gapToPart': self.gapToPart.expression,
            'isPreviewEnabled': self.isPreviewEnabled,
            'previewOpacity': self.previewOpacity,
            'theme': self.theme,
            'collapsedSections': self.collapsedSections,
            'paletteDockingState': self.paletteDockingState,
            'paletteWidth': self.paletteWidth,
            'paletteHeight': self.paletteHeight,
            'paletteLeft': self.paletteLeft,
            'paletteTop': self.paletteTop,
            'paletteDisplayLayout': self.paletteDisplayLayout,
        }
        with open(self.DEFAULTS_FILENAME, 'w', encoding='UTF-8') as json_file:
            json.dump(defaultData, json_file, ensure_ascii=False)
    
    def readDefaults(self):
        def expressionOrDefault(value, default, unitType=None):
            expression = FusionExpression(value, unitType=unitType)
            if value and expression.isValid:
                return expression
            else:
                return default

        if not os.path.isfile(self.DEFAULTS_FILENAME):
            return
        with open(self.DEFAULTS_FILENAME, 'r', encoding='UTF-8') as json_file:
            try:
                defaultData = json.load(json_file)
            except ValueError:
                app = adsk.core.Application.get()
                if app and app.userInterface:
                    app.userInterface.messageBox('Cannot read default options. Invalid JSON in "%s":' % self.DEFAULTS_FILENAME)

        self.dynamicSizeType = defaultData.get('dynamicSizeType', self.dynamicSizeType)
        self.placementType = defaultData.get('placementType', self.placementType)
        self.jointType = defaultData.get('jointType', self.jointType)
        self.dovetailAngle = expressionOrDefault(defaultData.get('dovetailAngle'), self.dovetailAngle, unitType="deg")
        self.reverseTaper = defaultData.get('reverseTaper', self.reverseTaper)
        self.isNumberOfFingersFixed = defaultData.get('isNumberOfFingersFixed', self.isNumberOfFingersFixed)
        self.fixedFingerSize = expressionOrDefault(defaultData.get('fixedFingerSize'), self.fixedFingerSize)
        self.fixedNotchSize = expressionOrDefault(defaultData.get('fixedNotchSize'), self.fixedNotchSize)
        self.minFingerSize = expressionOrDefault(defaultData.get('minFingerSize'), self.minFingerSize)
        self.minNotchSize = expressionOrDefault(defaultData.get('minNotchSize'), self.minNotchSize)
        self.fixedNumFingers = defaultData.get('fixedNumFingers', self.fixedNumFingers)
        self.gap = expressionOrDefault(defaultData.get('gap'), self.gap)
        self.gapToPart = expressionOrDefault(defaultData.get('gapToPart'), self.gapToPart)
        self.isPreviewEnabled = defaultData.get('isPreviewEnabled', self.isPreviewEnabled)
        self.previewOpacity = defaultData.get('previewOpacity', self.previewOpacity)
        self.theme = defaultData.get('theme', self.theme)
        self.collapsedSections = defaultData.get('collapsedSections', self.collapsedSections)
        self.paletteDockingState = defaultData.get('paletteDockingState', self.paletteDockingState)
        self.paletteWidth = defaultData.get('paletteWidth', self.paletteWidth)
        self.paletteHeight = defaultData.get('paletteHeight', self.paletteHeight)
        self.paletteLeft = defaultData.get('paletteLeft', self.paletteLeft)
        self.paletteTop = defaultData.get('paletteTop', self.paletteTop)
        self.paletteDisplayLayout = defaultData.get('paletteDisplayLayout', self.paletteDisplayLayout)


# Settings for the standalone "Dog Bone" operation, applied as a post-process to an
# already-cut body's real B-Rep topology rather than baked into finger-joint generation
# (see geometry.py's detectPlungeAxis/enumerateDogBoneCandidates/etc.). Kept as its own
# class/JSON file (not folded into FingerJointFeatureInput/defaults.json) since it has its
# own independent selection state and settings, and FingerJointFeatureInput.writeDefaults()
# overwrites its whole file wholesale on every save - sharing a file would mean each class's
# save silently clobbers the other's keys.
class DogBoneFeatureInput(object):
    DEFAULTS_FILENAME = os.path.join(APP_PATH, 'dogbone_defaults.json')

    def __init__(self):
        # Entities (not persisted - live selections, same convention as body0/body1/direction).
        # body/face are lists (Phase 4: multi-select, like body0/body1) even though Body/Face
        # mode only ever needs one axis-detection heuristic per entity, not per selection.
        self.body = []
        self.face = []
        self.edges = []
        # Settings
        self.selectionMode = DogBoneSelectionMode.BODY
        self.style = DogBoneStyle.CORNER
        # Values
        self.diameter = FusionExpression("3 mm")
        # Safety margin subtracted from the bit radius when positioning a Corner/Long/Short
        # relief circle (see geometry.py's computeDogBoneOffset): without it, a circle placed
        # to just barely touch the true corner point can compute as marginally short of it due
        # to floating-point error, which some CAM tool-path generators reject as a feature
        # smaller than the bit. A small clearance pushes the circle slightly past the corner
        # instead, so it unambiguously clears.
        self.clearance = FusionExpression("0.1 mm")
        # Minimal Corner style only: how much material is deliberately left short of the
        # corner (the opposite sign of clearance) for a tight forced fit with a less visually
        # obvious relief than a fully-cleared corner.
        self.interference = FusionExpression("0.05 mm")
        # How close to 90 degrees the angle between two adjacent faces must be for that edge
        # to qualify as a dogbone candidate at all, in Body/Face selection mode.
        self.angleTolerance = FusionExpression("5 deg", unitType="deg")
        self.readDefaults()

    def writeDefaults(self):
        defaultData = {
            'selectionMode': self.selectionMode,
            'style': self.style,
            'diameter': self.diameter.expression,
            'clearance': self.clearance.expression,
            'interference': self.interference.expression,
            'angleTolerance': self.angleTolerance.expression,
        }
        with open(self.DEFAULTS_FILENAME, 'w', encoding='UTF-8') as json_file:
            json.dump(defaultData, json_file, ensure_ascii=False)

    def readDefaults(self):
        def expressionOrDefault(value, default, unitType=None):
            expression = FusionExpression(value, unitType=unitType)
            if value and expression.isValid:
                return expression
            else:
                return default

        if not os.path.isfile(self.DEFAULTS_FILENAME):
            return
        with open(self.DEFAULTS_FILENAME, 'r', encoding='UTF-8') as json_file:
            try:
                defaultData = json.load(json_file)
            except ValueError:
                app = adsk.core.Application.get()
                if app and app.userInterface:
                    app.userInterface.messageBox('Cannot read default options. Invalid JSON in "%s":' % self.DEFAULTS_FILENAME)
                return

        self.selectionMode = defaultData.get('selectionMode', self.selectionMode)
        self.style = defaultData.get('style', self.style)
        self.diameter = expressionOrDefault(defaultData.get('diameter'), self.diameter)
        self.clearance = expressionOrDefault(defaultData.get('clearance'), self.clearance)
        self.interference = expressionOrDefault(defaultData.get('interference'), self.interference)
        self.angleTolerance = expressionOrDefault(defaultData.get('angleTolerance'), self.angleTolerance, unitType="deg")
