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

from . import commands
from . import options
from . import ui
from . import geometry

# Global variable to hold the add-in (created in run(), destroyed in stop())
addIn = None


def createBaseFeature(parentComponent, bRepBody, name):
    feature = parentComponent.features.baseFeatures.add()
    feature.startEdit()
    parentComponent.bRepBodies.add(bRepBody, feature)
    feature.name = name
    feature.finishEdit()
    return feature

def createCutFeature(parentComponent, targetBody, toolBodyFeature):
    toolBodies = adsk.core.ObjectCollection.create()
    assert(toolBodyFeature.bodies.count == 1)
    toolBodies.add(toolBodyFeature.bodies.item(0))
    cutInput = parentComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    cutInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    cutInput.isNewComponent = False
    cutFeature = parentComponent.features.combineFeatures.add(cutInput)
    return cutFeature


class CreateFingerJointCommand(commands.RunningCommandBase):
    def __init__(self, args: adsk.core.CommandCreatedEventArgs):
        super(CreateFingerJointCommand, self).__init__(args)
        defaults = options.FingerJointFeatureInput()
        self.ui = ui.FingerJointUI(args.command.commandInputs, defaults)
        self.last_used_inputs = defaults

    def onInputChanged(self, args: adsk.core.InputChangedEventArgs):
        self.ui.updateVisibility()
        self.ui.focusNextSelectionInput()

    def onValidate(self, args: adsk.core.ValidateInputsEventArgs):
        args.areInputsValid = self.ui.areInputsValid()

    def onExecutePreview(self, args: adsk.core.CommandEventArgs):
        if self.ui.isPreviewEnabled():
            if self.doExecute():
                args.isValidResult = True
                self.ui.setInputErrorMessage('')
            else:
                self.ui.setInputErrorMessage('Finger joints could not be completed. Try selecting overlapping bodies and double-check the dimensions.')

    def onExecute(self, args: adsk.core.CommandEventArgs):
        # We split onExecute and doExecute here so we can re-use the main functionality in
        # onExecutePreview where we have to react differently to errors.
        if not self.doExecute():
            args.executeFailed = True
            args.executeFailedMessage = 'Finger joints could not be completed. Try selecting overlapping bodies and double-check the dimensions.'

    def doExecute(self):
        inputs = self.ui.createInputs()
        self.last_used_inputs = inputs
        toolBodies = geometry.createToolBodies(inputs)
        if toolBodies == True:
            # No cut is neccessary (bodies do not overlap).
            return True
        elif toolBodies == False:
            # No cut is possible (e.g., because of invalid inputs).
            return False
        else:
            self.createCustomFeature(inputs, *toolBodies)
            return True

    def createCustomFeature(self, inputs, toolBody0, toolBody1):
        app = adsk.core.Application.get()
        activeComponent = app.activeProduct.activeComponent
        design = activeComponent.parentDesign

        # Temporarily switch to parametric design
        previousDesignType = design.designType
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        # We will later group all created features into a custom feature.
        # For that reason, we have to remember the first and last feature that is part of this group.
        tool0Feature = createBaseFeature(activeComponent, toolBody0, "tool0")
        createCutFeature(activeComponent, inputs.body0, tool0Feature)
        tool1Feature = createBaseFeature(activeComponent, toolBody1, "tool1")
        createCutFeature(activeComponent, inputs.body1, tool1Feature)

        design.designType = previousDesignType

    def onDestroy(self, args: adsk.core.CommandEventArgs):
        super(CreateFingerJointCommand, self).onDestroy(args)
        if args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
            self.last_used_inputs.writeDefaults()


class FingerJointAddIn(commands.AddIn):
    COMMAND_ID = 'fpFingerJoints'
    FEATURE_NAME = 'Finger Joint'
    RESOURCE_FOLDER = 'resources/ui/command_button'
    CREATE_TOOLTIP='Creates a finger joint from the overlap of two bodies'
    EDIT_TOOLTIP='Edit finger joint'
    PANEL_NAME='SolidModifyPanel'
    RUNNING_CREATE_COMMAND_CLASS = CreateFingerJointCommand


def run(context):
    global addIn
    try:
        if addIn is not None:
            stop({'IsApplicationClosing': False})
        addIn = FingerJointAddIn()
        addIn.addToUI()
    except:
        ui.reportError('Uncaught exception', True)


def stop(context):
    global addIn
    addIn.removeFromUI()
    addIn = None
