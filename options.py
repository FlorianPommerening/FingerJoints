import json
import os
from typing import Optional, Union

import adsk.core
import adsk.fusion

from . import util

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


class FusionExpression(object):
    def __init__(self, expression):
        self._expression = expression

    @property
    def expression(self):
        return self._expression

    @expression.setter
    def expression(self, value):
        self._expression = value

    @property
    def value(self):
        unitsManager = adsk.core.Application.get().activeProduct.unitsManager
        return unitsManager.evaluateExpression(self._expression)

    @property
    def isValid(self):
        unitsManager = adsk.core.Application.get().activeProduct.unitsManager
        return unitsManager.isValidExpression(self._expression, unitsManager.defaultLengthUnits)


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
        self.body0: Optional[adsk.fusion.BRepBody] = None
        self.body1: Optional[adsk.fusion.BRepBody] = None
        self.direction: Optional[Union[adsk.fusion.SketchLine]] = None
        # Settings
        self.dynamicSizeType = DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE
        self.placementType = PlacementType.FINGERS_OUTSIDE
        # Values
        self.isNumberOfFingersFixed = False
        self.fixedFingerSize = FusionExpression("20 mm")
        self.fixedNotchSize = FusionExpression("20 mm")
        self.minFingerSize = FusionExpression("20 mm")
        self.minNotchSize = FusionExpression("20 mm")
        self.fixedNumFingers = 3
        self.gap = FusionExpression("0 mm")
        self.gapToPart = FusionExpression("0 mm")
        self.isPreviewEnabled = True
        self.readDefaults()

    def writeDefaults(self):
        with open(self.DEFAULTS_FILENAME, 'w', encoding='UTF-8') as json_file:
            json.dump(self.data(), json_file, ensure_ascii=False)

    def asJson(self) -> str:
        return json.dumps(self.data())

    @classmethod
    def fromJson(cls, data: str) -> "FingerJointFeatureInput":
        data = json.loads(data)

        input = FingerJointFeatureInput()
        input.dynamicSizeType = data['dynamicSizeType']
        input.placementType = data['placementType']
        input.isNumberOfFingersFixed = data['isNumberOfFingersFixed']
        input.fixedFingerSize = FusionExpression(data['fixedFingerSize'])
        input.fixedNotchSize = FusionExpression(data['fixedNotchSize'])
        input.minFingerSize = FusionExpression(data['minFingerSize'])
        input.minNotchSize = FusionExpression(data['minNotchSize'])
        input.fixedNumFingers = data['fixedNumFingers']
        input.gap = FusionExpression(data['gap'])
        input.gapToPart = FusionExpression(data['gapToPart'])
        input.isPreviewEnabled = data['isPreviewEnabled']

        return input

    def data(self):
        return {
            'dynamicSizeType': self.dynamicSizeType,
            'placementType': self.placementType,
            'isNumberOfFingersFixed': self.isNumberOfFingersFixed,
            'fixedFingerSize': self.fixedFingerSize.expression,
            'fixedNotchSize': self.fixedNotchSize.expression,
            'minFingerSize': self.minFingerSize.expression,
            'minNotchSize': self.minNotchSize.expression,
            'fixedNumFingers': self.fixedNumFingers,
            'gap': self.gap.expression,
            'gapToPart': self.gapToPart.expression,
            'isPreviewEnabled': self.isPreviewEnabled,
        }

    def readDefaults(self):
        def expressionOrDefault(value, default):
            expression = FusionExpression(value)
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
                util.reportError('Cannot read default options. Invalid JSON in "%s":' % self.DEFAULTS_FILENAME)

        self.dynamicSizeType = defaultData.get('dynamicSizeType', self.dynamicSizeType)
        self.placementType = defaultData.get('placementType', self.placementType)
        self.isNumberOfFingersFixed = defaultData.get('isNumberOfFingersFixed', self.isNumberOfFingersFixed)
        self.fixedFingerSize = expressionOrDefault(defaultData.get('fixedFingerSize'), self.fixedFingerSize)
        self.fixedNotchSize = expressionOrDefault(defaultData.get('fixedNotchSize'), self.fixedNotchSize)
        self.minFingerSize = expressionOrDefault(defaultData.get('minFingerSize'), self.minFingerSize)
        self.minNotchSize = expressionOrDefault(defaultData.get('minNotchSize'), self.minNotchSize)
        self.fixedNumFingers = defaultData.get('fixedNumFingers', self.fixedNumFingers)
        self.gap = expressionOrDefault(defaultData.get('gap'), self.gap)
        self.gapToPart = expressionOrDefault(defaultData.get('gapToPart'), self.gapToPart)
        self.isPreviewEnabled = defaultData.get('isPreviewEnabled', self.isPreviewEnabled)
