import adsk.core
import adsk.fusion

from . import ui

# Keep track of all currently running commands in a global set, so their
# callback handlers are not GC'd.
running_commands = set()

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


class RunningCommandBase(object):
    """
    Base class to keep persistent data during the lifetime of a custom feature
    creation or edit dialog. The constructor of this class automatically adds the
    instance to running_commands and the onDestroy event removes it again.
    To use this class, inherit from it an override the events.
    """

    def __init__(self, args, customFeatureDefinition):
        self.customFeatureDefinition = customFeatureDefinition
        running_commands.add(self)

    def onCreate(self, args):
        cmd = adsk.core.Command.cast(args.command)

        self._activateHandler = makeForwardingHandler(
            adsk.core.CommandEventHandler, self.onActivate)
        cmd.activate.add(self._activateHandler)

        self._deactivateHandler = makeForwardingHandler(
            adsk.core.CommandEventHandler, self.onDeactivate)
        cmd.deactivate.add(self._deactivateHandler)

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

    def onActivate(self, args):
        pass

    def onDeactivate(self, args):
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


class ComputeCommandBase(object):
    """
    Base class for handlers of compute events for custom features.
    To use this class, inherit from it an override the events.
    """

    def __init__(self, args, customFeatureDefinition):
        self.customFeatureDefinition = customFeatureDefinition

    def onCompute(self, args):
        pass

class AddIn(object):
    # Defaults that are None have to be overridden in derived classes.
    COMMAND_ID = None
    FEATURE_NAME = None
    RESOURCE_FOLDER = None
    CREATE_TOOLTIP=''
    EDIT_TOOLTIP=''
    PANEL_NAME=None
    RUNNING_CREATE_COMMAND_CLASS = None
    RUNNING_EDIT_COMMAND_CLASS = None
    COMPUTE_COMMAND_CLASS = None

    def __init__(self):
        fusion = adsk.core.Application.get()
        self.fusionUI = fusion.userInterface

        # Add handlers for creating, editing and computing the feature.
        self._createHandler = makeForwardingHandler(
            adsk.core.CommandCreatedEventHandler, self._onCreate)
        self._editHandler = makeForwardingHandler(
            adsk.core.CommandCreatedEventHandler, self._onEdit)
        self._computeHandler = makeForwardingHandler(
            adsk.fusion.CustomFeatureEventHandler, self._onCompute)

        # Register a new custom feature and the compute handler for it.
        self._customFeatureDefinition = adsk.fusion.CustomFeatureDefinition.create(
            self._getCustomFeatureID(), self.FEATURE_NAME, self.RESOURCE_FOLDER)
        self._customFeatureDefinition.customFeatureCompute.add(self._computeHandler)

    def _onCreate(self, args):
        running_command = self.RUNNING_CREATE_COMMAND_CLASS(args, self._customFeatureDefinition)
        running_command.onCreate(args)

    def _onEdit(self, args):
        running_command = self.RUNNING_EDIT_COMMAND_CLASS(args, self._customFeatureDefinition)
        running_command.onCreate(args)

    def _onCompute(self, args):
        running_command = self.COMPUTE_COMMAND_CLASS(args, self._customFeatureDefinition)
        running_command.onCompute(args)

    def _getCreateButtonID(self):
        return self.COMMAND_ID + 'Create'

    def _getEditButtonID(self):
        return self.COMMAND_ID + 'Edit'

    def _getCustomFeatureID(self):
        return self.COMMAND_ID + 'Feature'

    def _getCreateButtonName(self):
        return self.FEATURE_NAME

    def _getEditButtonName(self):
        return 'Edit ' + self.FEATURE_NAME

    def addToUI(self):
        # If there are existing instances of the button, clean them up first.
        try:
            self.removeFromUI()
        except:
            pass

        # Create a command for creating the feature.
        createCommandDefinition = self.fusionUI.commandDefinitions.addButtonDefinition(
            self._getCreateButtonID(), self._getCreateButtonName(), self.CREATE_TOOLTIP, self.RESOURCE_FOLDER)
        createCommandDefinition.commandCreated.add(self._createHandler)

        # Add a button to the UI.
        panel = self.fusionUI.allToolbarPanels.itemById(self.PANEL_NAME)
        buttonControl = panel.controls.addCommand(createCommandDefinition)
        buttonControl.isPromotedByDefault = True
        buttonControl.isPromoted = True

        # Create a command definition for editing the feature.
        editCommandDefinition = self.fusionUI.commandDefinitions.addButtonDefinition(
            self._getEditButtonID(), self._getEditButtonName(), self.EDIT_TOOLTIP, '')
        editCommandDefinition.commandCreated.add(self._editHandler)
        self._customFeatureDefinition.editCommandId = self._getEditButtonID()


    def removeFromUI(self):
        createCommandDefinition = self.fusionUI.commandDefinitions.itemById(self._getCreateButtonID())
        if createCommandDefinition:
            createCommandDefinition.deleteMe()
        editCommandDefinition = self.fusionUI.commandDefinitions.itemById(self._getEditButtonID())
        if editCommandDefinition:
            editCommandDefinition.deleteMe()

        panel = self.fusionUI.allToolbarPanels.itemById(self.PANEL_NAME)
        buttonControl = panel.controls.itemById(self._getCreateButtonID())
        if buttonControl:
            buttonControl.deleteMe()
