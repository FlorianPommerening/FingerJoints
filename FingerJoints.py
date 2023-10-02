# Author: Florian Pommerening
# Description: An Add-In for making finger joints.

# Select two overlapping bodies and a direction. The overlap is cut along the
# direction multiple times resulting in the individual fingers/notches. We
# then remove every second finger from the first body and the other fingers
# from the second body. The remaining bodies then do not overlap anymore.

# Some inspiration was taken from the dogbone add-in developed by Peter
# Ludikar, Gary Singer, Patrick Rainsberry, David Liu, and Casey Rogers.

from typing import Optional, List, cast, Union

import adsk.core
import adsk.fusion

from .options import FingerJointFeatureInput
from .log import logger
from .commands import Action
from . import util
from . import commands
from . import options
from . import ui
from . import geometry

# Global variable to hold the add-in (created in run(), destroyed in stop())
addIn: Optional[commands.AddIn] = None

_app = adsk.core.Application.get()
_design: adsk.fusion.Design = cast(adsk.fusion.Design, _app.activeProduct)


class Attribute:
    GROUP_NAME = 'fingerJoint'
    INPUT = 'input'
    BODY0 = 'body0'
    BODY1 = 'body1'
    DIRECTION = 'direction'


def createBaseFeature(parentComponent: adsk.fusion.Component, body0: adsk.fusion.BRepBody, body1: adsk.fusion.BRepBody, inputs: FingerJointFeatureInput):
    feature = parentComponent.features.baseFeatures.add()
    feature.startEdit()
    parentComponent.bRepBodies.add(body0, feature)
    parentComponent.bRepBodies.add(body1, feature)
    feature.name = "fingerjoint tool"
    feature.attributes.add(Attribute.GROUP_NAME, Attribute.INPUT, inputs.asJson())
    feature.attributes.add(Attribute.GROUP_NAME, Attribute.BODY0, inputs.body0.entityToken)
    feature.attributes.add(Attribute.GROUP_NAME, Attribute.BODY1, inputs.body1.entityToken)
    feature.attributes.add(Attribute.GROUP_NAME, Attribute.DIRECTION, inputs.direction.entityToken)
    feature.finishEdit()
    return feature


def createCutFeature(parentComponent, targetBody, toolBodyFeature):
    toolBodies = adsk.core.ObjectCollection.create()

    toolBodies.add(toolBodyFeature.bodies.item(0))
    cutInput = parentComponent.features.combineFeatures.createInput(targetBody, toolBodies)
    cutInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    cutInput.isNewComponent = False
    cutInput.isKeepToolBodies = False
    cutFeature = parentComponent.features.combineFeatures.add(cutInput)
    return cutFeature


def getEntity(token: str, type: str):
    entities = _design.findEntityByToken(token)

    if entities is None or len(entities) != 1:
        logger.warn(f"Found {len(entities) if entities is not None else 0} for {type} for token {token}")
        raise Exception('Cannot find entity')

    return entities[0]


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
        if toolBodies is True:
            # No cut is necessary (bodies do not overlap).
            return True
        elif toolBodies is False:
            # No cut is possible (e.g., because of invalid inputs).
            return False
        else:
            self.createCustomFeature(inputs, *toolBodies)
            return True

    # noinspection PyMethodMayBeStatic
    def createCustomFeature(self, inputs: FingerJointFeatureInput, toolBody0, toolBody1):
        app = adsk.core.Application.get()
        activeComponent = cast(adsk.fusion.Design, app.activeProduct).activeComponent
        design = activeComponent.parentDesign

        # Temporarily switch to parametric design
        previousDesignType = design.designType
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType

        # We will later group all created features into a custom feature.
        # For that reason, we have to remember the first and last feature that is part of this group.
        toolFeature = createBaseFeature(activeComponent, toolBody0, toolBody1, inputs)
        createCutFeature(activeComponent, inputs.body0, toolFeature)
        createCutFeature(activeComponent, inputs.body1, toolFeature)

        design.designType = previousDesignType

    def onDestroy(self, args: adsk.core.CommandEventArgs):
        super(CreateFingerJointCommand, self).onDestroy(args)
        if args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
            self.last_used_inputs.writeDefaults()


class UpdateFingerJointCommand(commands.RunningCommandBase):

    @staticmethod
    def updateFingerJoint(feature: adsk.fusion.BaseFeature, obj: adsk.fusion.TimelineObject) -> bool:
        attributes: adsk.core.Attributes = feature.attributes

        if not len(attributes.itemsByGroup(Attribute.GROUP_NAME)) > 0:
            # not a finger joint feature
            return True

        logger.debug(f"update feature '{feature.name}' at index: {obj.index}")

        inputAsJson = attributes.itemByName(Attribute.GROUP_NAME, Attribute.INPUT).value
        if not obj.rollTo(False):
            raise Exception('Cannot rollback history')

        inputs = FingerJointFeatureInput.fromJson(inputAsJson)
        inputs.body0 = getEntity(attributes.itemByName(Attribute.GROUP_NAME, Attribute.BODY0).value, 'body0')
        inputs.body1 = getEntity(attributes.itemByName(Attribute.GROUP_NAME, Attribute.BODY1).value, 'body1')
        inputs.direction = getEntity(attributes.itemByName(Attribute.GROUP_NAME, Attribute.DIRECTION).value, 'direction')

        toolBodies = geometry.createToolBodies(inputs)

        if toolBodies is True or toolBodies is False:
            # No cut is necessary (bodies do not overlap).
            # delete finger joint features created before
            index = feature.timelineObject.index
            cast(adsk.fusion.CombineFeature, _design.timeline.item(index + 2).entity).deleteMe()
            cast(adsk.fusion.CombineFeature, _design.timeline.item(index + 1).entity).deleteMe()
            cast(adsk.fusion.BaseFeature, _design.timeline.item(index).entity).deleteMe()

            return False

        body0, body1 = toolBodies

        feature.startEdit()
        feature.updateBody(feature.bodies[0], body0)
        feature.updateBody(feature.bodies[1], body1)
        feature.finishEdit()

        return True

    def onExecute(self, args):
        app = adsk.core.Application.get()
        design: adsk.fusion.Design = cast(adsk.fusion.Design, app.activeProduct)

        def processFeature(obj: adsk.fusion.TimelineObject) -> bool:

            if obj.entity.classType() == adsk.fusion.BaseFeature.classType():
                feature = cast(adsk.fusion.BaseFeature, obj.entity)
                return UpdateFingerJointCommand.updateFingerJoint(feature, obj)

            return True

        def processTimeline(timeline: Union[adsk.fusion.Timeline, adsk.fusion.TimelineGroup]) -> int:
            count = 0

            for obj in timeline:
                if obj.isGroup:
                    group = cast(adsk.fusion.TimelineGroup, obj)
                    isCollapsed = group.isCollapsed
                    group.isCollapsed = False
                    processTimeline(group)
                    group.isCollapsed = isCollapsed
                else:
                    if not processFeature(obj):
                        count += 3

            return count

        position = design.timeline.markerPosition
        deletionCount = 0
        try:
            deletionCount = processTimeline(design.timeline)
        finally:
            design.timeline.markerPosition = position - deletionCount


class FingerJointAddIn(commands.AddIn):
    def actions(self) -> List[Action]:
        return [
            Action('create', 'Create Finger Joint', 'Creates a finger joint from the overlap of two bodies', 'resources/ui/command_button', CreateFingerJointCommand),
            Action('update', 'Update Finger Joints', 'Update finger joints', 'resources/ui/command_button', UpdateFingerJointCommand)
        ]

    def _prefix(self) -> str:
        return 'fpFingerJoints'


def run(_context):
    global addIn
    try:
        if addIn is not None:
            stop({'IsApplicationClosing': False})
        addIn = FingerJointAddIn()
        addIn.addToUi()
    except Exception as e:
        logger.exception(e)
        util.reportError('Uncaught exception', True)


def stop(_context):
    global addIn

    if addIn:
        addIn.removeFromUI()

    addIn = None
