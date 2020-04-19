import traceback

import adsk.core

from .options import PlacementType, DynamicSizeType

class FingerJointUI(object):
    def __init__(self, inputs, defaults):
        app = adsk.core.Application.get()
        unitsManager = app.activeProduct.unitsManager
        defaultUnit = unitsManager.defaultLengthUnits

        self._inputs = inputs

        self._inputBody0 = inputs.addSelectionInput(
            'inputBody0', 'First Body',
            'Select the body that should contain the first finger.')
        self._inputBody0.tooltip ='Select the body that contains the fingers.' 
        self._inputBody0.addSelectionFilter('SolidBodies')
        # TODO allow to select more than one body here and below and do the cuts for all combinations?
        self._inputBody0.setSelectionLimits(1,1)

        self._inputBody1 = inputs.addSelectionInput(
            'inputBody1', 'Second Body',
            'Select the body that should contain the first notch.')
        self._inputBody1.tooltip ='Select the body that contains the notches.' 
        self._inputBody1.addSelectionFilter('SolidBodies')
        self._inputBody1.setSelectionLimits(1,1)

        self._inputDirection = inputs.addSelectionInput(
            'inputDirection', 'Direction of the Joint',
            'Select edge along the direction of the joint.')
        self._inputDirection.tooltip = ('Select an edge or sketch line along the direction of the joint. Normally, this should be defined '
            'by an edge where the two bodies intersect. The planes separating fingers from notches will be perpendicular to this direction.')
        self._inputDirection.addSelectionFilter('LinearEdges')
        self._inputDirection.addSelectionFilter('SketchLines')
        self._inputDirection.setSelectionLimits(1,1)

        self._inputPlacementType = inputs.addButtonRowCommandInput('inputPlacementType', 'Finger Placement', False)
        self._inputPlacementType.listItems.add('Fingers outside', defaults.placementType == PlacementType.FINGERS_OUTSIDE, 'resources/ui/placement_fingers_outside' )
        self._inputPlacementType.listItems.add('Notches outside', defaults.placementType == PlacementType.NOTCHES_OUTSIDE, 'resources/ui/placement_notches_outside' )
        self._inputPlacementType.listItems.add('Start with finger, end with notch', defaults.placementType == PlacementType.SAME_NUMBER_START_FINGER, 'resources/ui/placement_same_number_start_finger' )
        self._inputPlacementType.listItems.add('Start with notch, end with finger', defaults.placementType == PlacementType.SAME_NUMBER_START_NOTCH, 'resources/ui/placement_same_number_start_notch' )
        self._inputPlacementType.tooltipDescription = "Should the first selected body start/end with a finger or a notch?"
        self._placementTypesByIndex = [
             PlacementType.FINGERS_OUTSIDE,
             PlacementType.NOTCHES_OUTSIDE,
             PlacementType.SAME_NUMBER_START_FINGER,
             PlacementType.SAME_NUMBER_START_NOTCH
        ]

        self._inputIsNumberOfFingersFixed = inputs.addDropDownCommandInput('inputIsNumberOfFingersFixed', 'Number', adsk.core.DropDownStyles.LabeledIconDropDownStyle)
        self._inputIsNumberOfFingersFixed.tooltipDescription = "Should the number of fingers be a fixed number or determined from the size of fingers/notches and the size of the overlap?"
        dropdownItems = self._inputIsNumberOfFingersFixed.listItems
        dropdownItems.add('Fixed', defaults.isNumberOfFingersFixed, 'resources/ui/finger_number_fixed')
        dropdownItems.add('Dynamic', not defaults.isNumberOfFingersFixed, 'resources/ui/finger_number_dynamic')
        self._numberOfFingersFixedByIndex = [True, False]

        # Looks like a spinner has to have a maximum but 100000 seems reasonable. Creating that much fingers will likely run into memory or performance issues anyway.
        self._inputFixedNumFingers = inputs.addIntegerSpinnerCommandInput('inputFixedNumFingers', 'Number of Fingers', 1 , 100000 , 1, defaults.fixedNumFingers)

        self._inputDynamicSizeType = inputs.addButtonRowCommandInput('inputDynamicSizeType', 'Size', False)
        self._inputDynamicSizeType.listItems.add('Fixed Notch Size', defaults.dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE, 'resources/ui/dynamic_type_fixed_notch' )
        self._inputDynamicSizeType.listItems.add('Fixed Finger Size', defaults.dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE, 'resources/ui/dynamic_type_fixed_finger' )
        self._inputDynamicSizeType.listItems.add('Equal Notch and Finger Size', defaults.dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE, 'resources/ui/dynamic_type_equal_notch_and_finger' )
        self._inputDynamicSizeType.tooltipDescription = "Should notches or fingers have a fixed size or should their size be equally distributed over the length of the overlap?"
        self._dynamicSizeTypesByIndex = [
             DynamicSizeType.FIXED_NOTCH_SIZE,
             DynamicSizeType.FIXED_FINGER_SIZE,
             DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE,
        ]

        defaultNotchSize = adsk.core.ValueInput.createByReal(defaults.fixedNotchSize)
        self._inputFixedNotchSize = inputs.addValueInput('inputFixedNotchSize', 'Notch Size', defaultUnit, defaultNotchSize)

        defaultFingerSize = adsk.core.ValueInput.createByReal(defaults.fixedFingerSize)
        self._inputFixedFingerSize = inputs.addValueInput('inputFixedFingerSize', 'Finger Size', defaultUnit, defaultFingerSize)

        defaultMinNotchSize = adsk.core.ValueInput.createByReal(defaults.minNotchSize)
        self._inputMinNotchSize = inputs.addValueInput('inputMinNotchSize', 'Minimal Notch Size', defaultUnit, defaultMinNotchSize)

        defaultMinFingerSize = adsk.core.ValueInput.createByReal(defaults.minFingerSize)
        self._inputMinFingerSize = inputs.addValueInput('inputMinFingerSize', 'Minimal Finger Size', defaultUnit, defaultMinFingerSize)

        self._inputIsPreviewEnabled = inputs.addBoolValueInput('inputIsPreviewEnabled', 'Show Preview', True, '', defaults.isPreviewEnabled)

        self._inputErrorMessage = inputs.addTextBoxCommandInput('inputErrorMessage', '', '', 3, True)
        self._inputErrorMessage.isFullWidth = True

        self.updateVisibility()
        self.focusNextSelectionInput()

    def _getDistanceInputValue(self, input):
        if input.isVisible and input.isValidExpression:
            return input.value

    def updateVisibility(self):
        dynamicSizeType = self.getDynamicSizeType()
        numberOfFingersFixed = self.isNumberOfFingersFixed()
        self._inputFixedNotchSize.isVisible = dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE
        self._inputFixedFingerSize.isVisible = dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE
        self._inputFixedNumFingers.isVisible = numberOfFingersFixed
        self._inputMinNotchSize.isVisible = not numberOfFingersFixed and dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE
        self._inputMinFingerSize.isVisible = not numberOfFingersFixed and dynamicSizeType != DynamicSizeType.FIXED_FINGER_SIZE

    def getBody0(self):
        if self._inputBody0.selectionCount > 0:
            return self._inputBody0.selection(0).entity

    def getBody1(self):
        if self._inputBody1.selectionCount > 0:
            return self._inputBody1.selection(0).entity

    def getDirection(self):
        if self._inputDirection.selectionCount > 0:
            return self._inputDirection.selection(0).entity

    def getPlacementType(self):
        return self._placementTypesByIndex[self._inputPlacementType.selectedItem.index]

    def isNumberOfFingersFixed(self):
        return self._numberOfFingersFixedByIndex[self._inputIsNumberOfFingersFixed.selectedItem.index]

    def getFixedNumFingers(self):
        if self._inputFixedNumFingers.isVisible:
            return self._inputFixedNumFingers.value

    def getDynamicSizeType(self):
        return self._dynamicSizeTypesByIndex[self._inputDynamicSizeType.selectedItem.index]

    def getFixedNotchSize(self):
        return self._getDistanceInputValue(self._inputFixedNotchSize)

    def getFixedFingerSize(self):
        return self._getDistanceInputValue(self._inputFixedFingerSize)

    def getMinNotchSize(self):
        return self._getDistanceInputValue(self._inputMinNotchSize)

    def getMinFingerSize(self):
        return self._getDistanceInputValue(self._inputMinFingerSize)

    def isPreviewEnabled(self):
        return self._inputIsPreviewEnabled.value

    def setInputErrorMessage(self, msg):
        if msg:
            formattedText = '<p style="color:red">{}</p>'.format(msg)
        else:
            formattedText = ''
        # We guard this statement to prevent an infinite loop of setting
        # the value, validating the input because an input changed, computing
        # the preview because the validation was successfull, and setting the
        #  value to '' there.
        if self._inputErrorMessage.formattedText != formattedText:
            self._inputErrorMessage.formattedText = formattedText

    def focusNextSelectionInput(self):
        for input in self._inputs:
            if isinstance(input, adsk.core.SelectionCommandInput) and input.selectionCount == 0:
                input.hasFocus = True
                break

    def setRelevantOptions(self, options):
        options.dynamicSizeType = self.getDynamicSizeType()
        options.placementType = self.getPlacementType()
        options.isNumberOfFingersFixed = self.isNumberOfFingersFixed()
        # Only update the options that are relevant for the current operation.
        if self.getFixedNumFingers() is not None:
            options.fixedNumFingers = self.getFixedNumFingers()
        if self.getFixedNotchSize() is not None:
            options.fixedNotchSize = self.getFixedNotchSize()
        if self.getFixedFingerSize() is not None:
            options.fixedFingerSize = self.getFixedFingerSize()
        if self.getMinNotchSize() is not None:
            options.minNotchSize = self.getMinNotchSize()
        if self.getMinFingerSize() is not None:
            options.minFingerSize = self.getMinFingerSize()
        options.isPreviewEnabled = self.isPreviewEnabled()

    def areInputsValid(self):
        valid = True
        errorMessage = ''
        if self.getPlacementType() == PlacementType.FINGERS_OUTSIDE and self.isNumberOfFingersFixed() and self.getFixedNumFingers() < 2:
            valid = False
            errorMessage = 'When using one finger on each edge, there have to be at least two fingers.'
        if self._inputFixedNotchSize.isVisible and (self.getFixedNotchSize() is None or self.getFixedNotchSize() <= 0):
            valid = False
        if self._inputFixedFingerSize.isVisible and (self.getFixedFingerSize() is None or self.getFixedFingerSize() <= 0):
            valid = False
        if self._inputMinNotchSize.isVisible and (self.getMinNotchSize() is None or self.getMinNotchSize() <= 0):
            valid = False
        if self._inputMinFingerSize.isVisible and (self.getMinFingerSize() is None or self.getMinFingerSize() <= 0):
            valid = False
        self.setInputErrorMessage(errorMessage)
        return valid


def reportError(message, includeStacktrace=False):
    fusion = adsk.core.Application.get()
    fusionUI = fusion.userInterface
    if includeStacktrace:
        message = '{}\n\nStack trace:\n{}'.format(message, traceback.format_exc())
    fusionUI.messageBox(message)
