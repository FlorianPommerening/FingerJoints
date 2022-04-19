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

def recoverDependenciesFromFeature(customFeature):
    body0 = customFeature.dependencies.itemById('body0').entity
    body1 = customFeature.dependencies.itemById('body1').entity
    direction = customFeature.dependencies.itemById('direction').entity
    return body0, body1, direction

def recoverOptionsFromFeature(customFeature):
    opts = options.FingerJointOptions()
    opts.readFromParameters(customFeature.parameters)
    return opts

def replaceFirstBodyInFeature(feature, newBody):
    feature.startEdit()
    body = feature.bodies.item(0)
    feature.updateBody(body, newBody)
    feature.finishEdit()

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

# We use this class to reduce the code duplication of the creation and the edit command.
class FingerJointCommand(commands.RunningCommandBase):
    def onCreate(self, args):
        super(FingerJointCommand, self).onCreate(args)
        self.options = self.loadOptions()
        if self.options is not None:
            self.ui = ui.FingerJointUI(args.command.commandInputs, self.options)

    def loadOptions(self):
        return options.FingerJointOptions()

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
        self.ui.setRelevantOptions(self.options)
        body0 = self.ui.getBody0()
        body1 = self.ui.getBody1()
        direction = self.ui.getDirection()
        toolBodies = geometry.createToolBodies(body0, body1, direction, self.options)
        if toolBodies == True:
            # No cut is neccessary (bodies do not overlap).
            return True
        elif toolBodies == False:
            # No cut is possible (e.g., because of invalid inputs).
            return False
        else:
            self.createCustomFeature(body0, body1, *toolBodies, direction)
            return True

    def createCustomFeature(self, body0, body1, toolBody0, toolBody1, direction):
        pass

    def onDestroy(self, args: adsk.core.CommandEventArgs):
        super(FingerJointCommand, self).onDestroy(args)
        if args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
            self.options.writeDefaults()


class CreateFingerJointCommand(FingerJointCommand):
    def onCreate(self, args):
        super(FingerJointCommand, self).onCreate(args)
        self.options = options.FingerJointOptions()
        self.ui = ui.FingerJointUI(args.command.commandInputs, self.options)

    def createCustomFeature(self, body0, body1, toolBody0, toolBody1, direction):
        app = adsk.core.Application.get()
        activeComponent = app.activeProduct.activeComponent
        # We will later group all created features into a custom feature.
        # For that reason, we have to remember the first and last feature that is part of this group.
        firstFeature = tool0Feature = createBaseFeature(activeComponent, toolBody0, "tool0")
        createCutFeature(activeComponent, body0, tool0Feature)
        tool1Feature = createBaseFeature(activeComponent, toolBody1, "tool1")
        lastFeature = createCutFeature(activeComponent, body1, tool1Feature)

        # Create an object holding the inputs, parameters, and dependencies for the new custom feature.
        customFeatureInput = activeComponent.features.customFeatures.createInput(
            self.customFeatureDefinition)
        self.options.storeInParameters(customFeatureInput)
        customFeatureInput.addDependency('body0', body0)
        customFeatureInput.addDependency('body1', body1)
        customFeatureInput.addDependency('direction', direction)
        customFeatureInput.setStartAndEndFeatures(firstFeature, lastFeature)

        # Create the custom feature.
        activeComponent.features.customFeatures.add(customFeatureInput)


class EditFingerJointCommand(FingerJointCommand):
    def __init__(self, args, customFeatureDefinition):
        super(FingerJointCommand, self).__init__(args, customFeatureDefinition)
        app = adsk.core.Application.get()
        self.editedFeature = app.userInterface.activeSelections.item(0).entity

    def loadOptions(self):
        if self.editedFeature is None:
            return None
        return recoverOptionsFromFeature(self.editedFeature)

    def onActivate(self, args):
        app = adsk.core.Application.get()

        # Roll the timeline to just before the custom feature being edited.
        timeline = app.activeProduct.timeline
        markerPosition = timeline.markerPosition
        self._restoreTimelineObject = timeline.item(markerPosition - 1)
        self.editedFeature.timelineObject.rollTo(True)
        self._isRolledForEdit = True

        # Define a transaction marker so the change in the timeline above is
        # not undone during a rollback in preview mode.
        args.command.beginStep()

        # Preselect the bodies and direction in the UI (this is not possible
        # in onCreate yet).
        body0, body1, direction = recoverDependenciesFromFeature(self.editedFeature)
        self.ui.selectBody0(body0)
        self.ui.selectBody1(body1)
        self.ui.selectDirection(direction)

    def createCustomFeature(self, body0, body1, toolBody0, toolBody1, direction):
        self.options.updateInParameters(self.editedFeature)
        dependencies = self.editedFeature.dependencies
        dependencies.itemById('body0').entity = body0
        dependencies.itemById('body1').entity = body1
        dependencies.itemById('direction').entity = direction
        recomputeFingerJoint(self.editedFeature)

        self._restoreTimelineObject.rollTo(False)


def recomputeFingerJoint(feature):
    body0, body1, direction = recoverDependenciesFromFeature(feature)
    opts = recoverOptionsFromFeature(feature)

    toolBodies = geometry.createToolBodies(body0, body1, direction, opts)
    if toolBodies == True:
        # No cut is neccessary (bodies do not overlap).
        return True
    elif toolBodies == False:
        # No cut is possible (e.g., because of invalid inputs).
        return False
    else:
        # Get the existing base feature and update the body.
        for subfeature in feature.features:
            if subfeature.objectType == adsk.fusion.BaseFeature.classType():
                if subfeature.name.startswith('tool0'):
                    replaceFirstBodyInFeature(subfeature, toolBodies[0])
                else:
                    assert subfeature.name.startswith('tool1'), subfeature.name
                    replaceFirstBodyInFeature(subfeature, toolBodies[1])



class ComputeFingerJointCommand(commands.ComputeCommandBase):
    def onCompute(self, args: adsk.fusion.CustomFeatureEventArgs):
        return recomputeFingerJoint(args.customFeature)


class FingerJointAddIn(commands.AddIn):
    COMMAND_ID = 'fpFingerJoints'
    FEATURE_NAME = 'Finger Joint'
    RESOURCE_FOLDER = 'resources/ui/command_button'
    CREATE_TOOLTIP='Creates a finger joint from the overlap of two bodies'
    EDIT_TOOLTIP='Edit finger joint'
    PANEL_NAME='SolidModifyPanel'
    RUNNING_CREATE_COMMAND_CLASS = CreateFingerJointCommand
    RUNNING_EDIT_COMMAND_CLASS = EditFingerJointCommand
    COMPUTE_COMMAND_CLASS = ComputeFingerJointCommand


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
