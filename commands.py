import adsk.core
import adsk.fusion

from . import ui

# Keep track of all currently running commands in a global set, so their
# callback handlers are not GC'd.
running_commands = set()

class RunningCommandBase(object):
    """
    Base class to keep persistent data during the lifetime of a command from
    creation to destruction. The constructor of this class automatically adds
    the instance to running_commands and the onDestroy event removes it again.
    To use this class, inherit from it an override the events.
    """

    def __init__(self, args):
        running_commands.add(self)

        cmd = adsk.core.Command.cast(args.command)            

        self._inputChangedHandler = makeForwardingHandler(
            adsk.core.InputChangedEventHandler, self.onInputChanged)
        cmd.inputChanged.add(self._inputChangedHandler)

        self._selectionHandler = makeForwardingHandler(
            adsk.core.SelectionEventHandler, self.onSelectionEvent)
        cmd.selectionEvent.add(self._selectionHandler)
        
        self._validateHandler = makeForwardingHandler(
            adsk.core.ValidateInputsEventHandler, self.onValidate)
        cmd.validateInputs.add(self._validateHandler)
        
        self._executeHandler = makeForwardingHandler(
            adsk.core.CommandEventHandler, self.onExecute)
        cmd.execute.add(self._executeHandler)

        self._executePreviewHandler = makeForwardingHandler(
            adsk.core.CommandEventHandler, self.onExecutePreview)
        cmd.executePreview.add(self._executePreviewHandler)

        self._destroyHandler = makeForwardingHandler(
            adsk.core.CommandEventHandler, self.onDestroy)
        cmd.destroy.add(self._destroyHandler)

    def onCreated(self, args):
        pass

    def onInputChanged(self, args):
        pass

    def onSelectionEvent(self, args):
        pass

    def onValidate(self, args):
        pass

    def onExecute(self, args):
        pass

    def onExecutePreview(self, args):
        pass

    def onDestroy(self, args):
        running_commands.remove(self)


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, runningCommandClass):
        super().__init__()
        self.runningCommandClass = runningCommandClass

    def notify(self, args):
        try:
            running_command = self.runningCommandClass(args)
            running_command.onCreated(args)
        except:
            ui.reportError('Command creation callback method failed', True)


def makeForwardingHandler(handler_cls, callback):
    class ForwardingHandler(handler_cls):
        def __init__(self, callback):
            super().__init__()
            self.callback = callback

        def notify(self, args):
            try:
                self.callback(args)
            except:
                ui.reportError('Callback method failed', True)
    return ForwardingHandler(callback)


class CommandButton(object):
    def __init__(self, commandID, panelName, commandDataClass):
        self.commandID = commandID
        self.panelName = panelName

        fusion = adsk.core.Application.get()
        self.fusionUI = fusion.userInterface
        self.creationHandler = CommandCreatedHandler(commandDataClass)

    def addToUI(self, name, tooltip='', resourceFolder=''):
        # If there are existing instances of the button, clean them up first.
        try:
            self.removeFromUI()
        except:
            pass

        # Create a command definition and button for it.
        commandDefinition = self.fusionUI.commandDefinitions.addButtonDefinition(
            self.commandID, name, tooltip, resourceFolder)
        commandDefinition.commandCreated.add(self.creationHandler)

        panel = self.fusionUI.allToolbarPanels.itemById(self.panelName)
        buttonControl = panel.controls.addCommand(commandDefinition)

        # Make the button available in the panel.
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

    def removeFromUI(self):
        commandDefinition = self.fusionUI.commandDefinitions.itemById(self.commandID)
        if commandDefinition:
            commandDefinition.deleteMe()
        panel = self.fusionUI.allToolbarPanels.itemById(self.panelName)
        buttonControl = panel.controls.itemById(self.commandID)
        if buttonControl:
            buttonControl.deleteMe()
