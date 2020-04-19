import json
import os

import adsk.core

from . import ui

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
        self.isPreviewEnabled = defaultData.get('isPreviewEnabled', self.isPreviewEnabled)

