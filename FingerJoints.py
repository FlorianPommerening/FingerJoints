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


class FingerJointCommand(commands.RunningCommandBase):
    def __init__(self, args: adsk.core.CommandCreatedEventArgs):
        super(FingerJointCommand, self).__init__(args)
        self.options = options.FingerJointOptions()
        self.ui = ui.FingerJointUI(args.command.commandInputs, self.options)

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
        if not self.doExecute():
            args.executeFailed = True
            args.executeFailedMessage = 'Finger joints could not be completed. Try selecting overlapping bodies and double-check the dimensions.'

    def doExecute(self):
        self.ui.setRelevantOptions(self.options)
        body0 = self.ui.getBody0()
        body1 = self.ui.getBody1()
        direction = self.ui.getDirection()
        return geometry.createFingerJoint(body0, body1, direction, self.options)

    def onDestroy(self, args: adsk.core.CommandEventArgs):
        super(FingerJointCommand, self).onDestroy(args)
        if args.terminationReason == adsk.core.CommandTerminationReason.CompletedTerminationReason:
            self.options.writeDefaults()


class FingerJointAddIn(object):
    def __init__(self):
        self.button = commands.CommandButton('FingerJointBtn', 'SolidModifyPanel', FingerJointCommand)

    def start(self):
        self.button.addToUI('Finger Joint',
                            'Creates a finger joint from the overlap of two bodies',
                            'resources/ui/command_button')

    def stop(self):
        self.button.removeFromUI()


def run(context):
    global addIn
    try:
        if addIn is not None:
            stop({'IsApplicationClosing': False})
        addIn = FingerJointAddIn()
        addIn.start()
    except:
        ui.reportError('Uncaught exception', True)


def stop(context):
    global addIn
    addIn.stop()
    addIn = None
