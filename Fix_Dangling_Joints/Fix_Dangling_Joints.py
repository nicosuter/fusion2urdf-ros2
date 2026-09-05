#Author-Elia Huber
#Description-Delete dangling ghost joints left behind by deleted components

"""Standalone repair script for Fusion designs.

The URDF exporter is deliberately read-only: it reports fully dangling ghost
joints and skips them, but never touches the CAD document. This script is the
opt-in counterpart that actually removes them, so the cleanup is an explicit
user action with its own undo step instead of a side effect of exporting.

Deleted here:
  * ghost joints - both endpoints report None, so the joint is attached to
    nothing and shows up nowhere in the assembly.
  * unreadable joints - reading an endpoint raises, which is what makes the
    exporter crash. They are listed separately in the confirmation.

Never deleted here:
  * half-dangling joints - exactly one endpoint is None, meaning the joint is
    attached to the root component or to ground. That is a modelling mistake
    with real intent behind it, so the script only reports and selects them.
"""

import adsk
import adsk.core
import adsk.fusion
import traceback

TITLE = 'Fix Dangling Joints'

GHOST = 'ghost'
UNREADABLE = 'unreadable'
HALF = 'half'


def _endpoints(joint):
    """Return (occurrenceOne, occurrenceTwo, readable)."""
    try:
        return joint.occurrenceOne, joint.occurrenceTwo, True
    except:
        return None, None, False


def _classify(joint):
    one, two, readable = _endpoints(joint)
    if not readable:
        return UNREADABLE
    if one is None and two is None:
        return GHOST
    if one is None or two is None:
        return HALF
    return None


def _describe(joint, component_name):
    try:
        name = joint.name
    except:
        name = '<unnamed joint>'
    return "{} (in {})".format(name, component_name)


def _scan(design):
    """Collect problem joints across every component of the design."""
    found = {GHOST: [], UNREADABLE: [], HALF: []}
    for component in design.allComponents:
        try:
            component_name = component.name
        except:
            component_name = '<unknown component>'
        for collection in (component.joints, component.asBuiltJoints):
            for joint in collection:
                verdict = _classify(joint)
                if verdict is not None:
                    found[verdict].append((joint, _describe(joint, component_name)))
    return found


def _select(joint):
    """Highlight a joint in the browser so the user can find it."""
    try:
        ui = adsk.core.Application.get().userInterface
        ui.activeSelections.clear()
        ui.activeSelections.add(joint)
    except:
        pass


def _bullets(entries, limit=30):
    labels = [label for _, label in entries[:limit]]
    if len(entries) > limit:
        labels.append('... and {} more'.format(len(entries) - limit))
    return '\n'.join('  - ' + label for label in labels)


def _delete(entries):
    """Delete the given joints. Returns (deleted, failed) label lists."""
    deleted = []
    failed = []
    for joint, label in entries:
        try:
            if joint.deleteMe():
                deleted.append(label)
            else:
                failed.append(label)
        except:
            failed.append(label)
    return deleted, failed


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if not design:
            ui.messageBox('No active Fusion design', TITLE)
            return

        found = _scan(design)
        removable = found[GHOST] + found[UNREADABLE]

        if not removable:
            report = 'No dangling ghost joints found. Nothing to delete.'
            if found[HALF]:
                _select(found[HALF][0][0])
                report += ('\n\n{} joint(s) are attached to the root component '
                           'or to ground. Fix these by hand - the exporter '
                           'cannot use them and this script will not delete '
                           'them:\n{}\n\nThe first one is selected in the '
                           'browser.').format(len(found[HALF]),
                                              _bullets(found[HALF]))
            ui.messageBox(report, TITLE)
            return

        question = 'Delete {} dangling joint(s)?\n'.format(len(removable))
        if found[GHOST]:
            question += ('\nGhost joints - both sides reference deleted '
                         'components:\n{}\n').format(_bullets(found[GHOST]))
        if found[UNREADABLE]:
            question += ('\nUnreadable joints - their endpoints raise on '
                         'access:\n{}\n').format(_bullets(found[UNREADABLE]))
        question += ('\nThis modifies the CAD document. It is a single undo '
                     'step and is not saved until you save the document.')

        answer = ui.messageBox(question, TITLE,
                               adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                               adsk.core.MessageBoxIconTypes.QuestionIconType)
        if answer != adsk.core.DialogResults.DialogYes:
            ui.messageBox('Cancelled. Nothing was changed.', TITLE)
            return

        deleted, failed = _delete(removable)

        report = 'Deleted {} of {} dangling joint(s).'.format(
            len(deleted), len(removable))
        if failed:
            report += ('\n\nCould not delete {} joint(s). These usually live '
                       'inside a derived or otherwise read-only component - '
                       'fix them in the source design and let the Derive '
                       'update:\n{}').format(len(failed), _bullets(failed))
        if found[HALF]:
            _select(found[HALF][0][0])
            report += ('\n\nStill broken: {} joint(s) attached to the root '
                       'component or to ground. Both sides of every joint must '
                       'connect to sub-components. Fix these by hand:\n{}\n\n'
                       'The first one is selected in the browser.').format(
                           len(found[HALF]), _bullets(found[HALF]))
        if deleted:
            report += '\n\nReview the result, then save the document yourself.'
        ui.messageBox(report, TITLE)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()), TITLE)
