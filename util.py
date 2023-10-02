import traceback

import adsk.core


def reportError(message, includeStacktrace=False):
    fusion = adsk.core.Application.get()
    fusionUI = fusion.userInterface
    if includeStacktrace:
        message = '{}\n\nStack trace:\n{}'.format(message, traceback.format_exc())
    fusionUI.messageBox(message)
