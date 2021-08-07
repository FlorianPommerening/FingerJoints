import json
import os

import adsk.core

from . import ui

APP_PATH = os.path.dirname(os.path.abspath(__file__))

class DynamicSizeType:
    FIXED_NOTCH_SIZE = 'fixed notch size'
    FIXED_FINGER_SIZE = 'fixed finger size'
    EQUAL_NOTCH_AND_FINGER_SIZE = 'equal notch and finger size'

    # TODO: this is a hack to store the parameters and should eventually disappear.
    @staticmethod
    def to_int(v):
        return {
            DynamicSizeType.FIXED_NOTCH_SIZE : 0,
            DynamicSizeType.FIXED_FINGER_SIZE: 1,
            DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE: 2}.get(v, -1)
    @staticmethod
    def from_int(v):
        return {
            0: DynamicSizeType.FIXED_NOTCH_SIZE,
            1: DynamicSizeType.FIXED_FINGER_SIZE,
            2: DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE}.get(v, DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE)


class PlacementType:
    FINGERS_OUTSIDE = 'fingers outside'
    NOTCHES_OUTSIDE = 'notches outside'
    SAME_NUMBER_START_FINGER = 'same number of fingers and notches (start with finger)'
    SAME_NUMBER_START_NOTCH = 'same number of fingers and notches (start with notch)'

    # TODO: this is a hack to store the parameters and should eventually disappear.
    @staticmethod
    def to_int(v):
        return {
            PlacementType.FINGERS_OUTSIDE : 0,
            PlacementType.NOTCHES_OUTSIDE: 1,
            PlacementType.SAME_NUMBER_START_FINGER: 2,
            PlacementType.SAME_NUMBER_START_NOTCH: 3}.get(v, -1)
    @staticmethod
    def from_int(v):
        return {
            0: PlacementType.FINGERS_OUTSIDE,
            1: PlacementType.NOTCHES_OUTSIDE,
            2: PlacementType.SAME_NUMBER_START_FINGER,
            3: PlacementType.SAME_NUMBER_START_NOTCH}.get(v, PlacementType.FINGERS_OUTSIDE)


class FingerJointOptions(object):
    DEFAULTS_FILENAME = os.path.join(APP_PATH, 'defaults.json')
    DEFAULTS_DATA = {}

    def __init__(self):
        self.dynamicSizeType = DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE
        self.placementType = PlacementType.FINGERS_OUTSIDE
        self.isNumberOfFingersFixed = False
        self.fixedFingerSize = 2
        self.fixedNotchSize = 2
        self.minFingerSize = 2
        self.minNotchSize = 2
        self.fixedNumFingers = 3
        self.gap = 0
        self.isPreviewEnabled = True
        self.readDefaults()

    def writeDefaults(self):
        defaultData = {
            'dynamicSizeType': self.dynamicSizeType,
            'placementType': self.placementType,
            'isNumberOfFingersFixed': self.isNumberOfFingersFixed,
            'fixedFingerSize': self.fixedFingerSize,
            'fixedNotchSize': self.fixedNotchSize,
            'minFingerSize': self.minFingerSize,
            'minNotchSize': self.minNotchSize,
            'fixedNumFingers': self.fixedNumFingers,
            'gap': self.gap,
            'isPreviewEnabled': self.isPreviewEnabled,
        }
        with open(self.DEFAULTS_FILENAME, 'w', encoding='UTF-8') as json_file:
            json.dump(defaultData, json_file, ensure_ascii=False)
    
    def readDefaults(self): 
        if not os.path.isfile(self.DEFAULTS_FILENAME):
            return
        with open(self.DEFAULTS_FILENAME, 'r', encoding='UTF-8') as json_file:
            try:
                defaultData = json.load(json_file)
            except ValueError:
                ui.reportError('Cannot read default options. Invalid JSON in "%s":' % self.DEFAULTS_FILENAME)

        self.dynamicSizeType = defaultData.get('dynamicSizeType', self.dynamicSizeType)
        self.placementType = defaultData.get('placementType', self.placementType)
        self.isNumberOfFingersFixed = defaultData.get('isNumberOfFingersFixed', self.isNumberOfFingersFixed)
        self.fixedFingerSize = defaultData.get('fixedFingerSize', self.fixedFingerSize)
        self.fixedNotchSize = defaultData.get('fixedNotchSize', self.fixedNotchSize)
        self.minFingerSize = defaultData.get('minFingerSize', self.minFingerSize)
        self.minNotchSize = defaultData.get('minNotchSize', self.minNotchSize)
        self.fixedNumFingers = defaultData.get('fixedNumFingers', self.fixedNumFingers)
        self.gap = defaultData.get('gap', self.gap)
        self.isPreviewEnabled = defaultData.get('isPreviewEnabled', self.isPreviewEnabled)

    def readFromParameters(self, parameters):
        self.dynamicSizeType = DynamicSizeType.from_int(parameters.itemById('dynamicSizeType').value)
        self.placementType = PlacementType.from_int(parameters.itemById('placementType').value)
        self.isNumberOfFingersFixed = bool(parameters.itemById('isNumberOfFingersFixed').value)
        self.fixedFingerSize = parameters.itemById('fixedFingerSize').value
        self.fixedNotchSize = parameters.itemById('fixedNotchSize').value
        self.minFingerSize = parameters.itemById('minFingerSize').value
        self.minNotchSize = parameters.itemById('minNotchSize').value
        self.fixedNumFingers = int(parameters.itemById('fixedNumFingers').value)
        self.gap = parameters.itemById('gap').value

    def storeInParameters(self, customFeatureInput):
        app = adsk.core.Application.get()
        defLengthUnits = app.activeProduct.unitsManager.defaultLengthUnits

        dynamicSizeTypeInput = adsk.core.ValueInput.createByReal(DynamicSizeType.to_int(self.dynamicSizeType))
        customFeatureInput.addCustomParameter('dynamicSizeType', 'Should the size of the fingers or notches be fixed?', dynamicSizeTypeInput, 'pcs', True)

        placementTypeInput = adsk.core.ValueInput.createByReal(PlacementType.to_int(self.placementType))
        customFeatureInput.addCustomParameter('placementType', 'Should fingers or notches be at the end of the piece?', placementTypeInput, 'pcs', True)

        isNumberOfFingersFixedInput = adsk.core.ValueInput.createByReal(int(self.isNumberOfFingersFixed))
        customFeatureInput.addCustomParameter('isNumberOfFingersFixed', 'Is the number of fingers fixed?', isNumberOfFingersFixedInput, 'pcs', True)

        fixedFingerSizeInput = adsk.core.ValueInput.createByReal(self.fixedFingerSize)
        customFeatureInput.addCustomParameter('fixedFingerSize', 'Size of a finger (if it is fixed)', fixedFingerSizeInput, defLengthUnits, True)

        fixedNotchSizeInput = adsk.core.ValueInput.createByReal(self.fixedNotchSize)
        customFeatureInput.addCustomParameter('fixedNotchSize', 'Size of a notch (if it is fixed)', fixedNotchSizeInput, defLengthUnits, True)

        minFingerSizeInput = adsk.core.ValueInput.createByReal(self.minFingerSize)
        customFeatureInput.addCustomParameter('minFingerSize', 'Minimal size of a finger (if it is not fixed)', minFingerSizeInput, defLengthUnits, True)

        minNotchSizeInput = adsk.core.ValueInput.createByReal(self.minNotchSize)
        customFeatureInput.addCustomParameter('minNotchSize', 'Minimal size of a notch (if it is not fixed)', minNotchSizeInput, defLengthUnits, True)

        fixedNumFingersInput = adsk.core.ValueInput.createByReal(self.fixedNumFingers)
        customFeatureInput.addCustomParameter('fixedNumFingers', 'Number of fingers or notches (if it is fixed)', fixedNumFingersInput, 'pcs', True)

        gapInput = adsk.core.ValueInput.createByReal(self.gap)
        customFeatureInput.addCustomParameter('gap', 'Gap size', gapInput, defLengthUnits, True)

    def updateInParameters(self, customFeature):
        parameters = customFeature.parameters
        parameters.itemById('dynamicSizeType').value = DynamicSizeType.to_int(self.dynamicSizeType)
        parameters.itemById('placementType').value = PlacementType.to_int(self.placementType)
        parameters.itemById('isNumberOfFingersFixed').value = int(self.isNumberOfFingersFixed)
        parameters.itemById('fixedFingerSize').value = self.fixedFingerSize
        parameters.itemById('fixedNotchSize').value = self.fixedNotchSize
        parameters.itemById('minFingerSize').value = self.minFingerSize
        parameters.itemById('minNotchSize').value = self.minNotchSize
        parameters.itemById('fixedNumFingers').value = self.fixedNumFingers
        parameters.itemById('gap').value = self.gap
