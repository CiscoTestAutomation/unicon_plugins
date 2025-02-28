import re
import time
import logging
from functools import wraps
from datetime import datetime, timedelta

from unicon.eal.dialogs import Statement
from unicon.plugins.generic.service_statements import\
    admin_password as admin_password_stmt
from unicon.plugins.generic.statements import (
    connection_statement_list, boot_timeout_stmt)

from .patterns import IosXEReloadPatterns, IosXEPatterns

log = logging.getLogger(__name__)
reload_patterns = IosXEReloadPatterns()
patterns = IosXEPatterns()


def please_reset_handler(spawn, session):
    """ Handles the router asking to be reset before booting. """
    if not session.get("please_reset_seen"):
        spawn.log.debug("The device has asked to be reset.")
        session['please_reset_seen'] = True
        if session.get("rommon_count"):
            # Reset rommon prompt processing state (ignore popped result).
            _ = session.pop('rommon_count')


def rommon_prompt_handler(spawn, session, context):
    """ handles connection refused scenarios
    """
    image = context.get('image')
    cmd = "boot " + image[0] if image else "boot"

    if not session.get("please_reset_seen"):
        if not session.get("rommon_count"):
            # Now boot the image
            spawn.sendline(cmd)
            session['rommon_count'] = 1
        else:
            raise Exception(
                'Rommon prompt encountered unexpectedly'
                ', Maybe golden image does not exist for  % ', str(spawn))
    else:
        if session.get("rommon_count"):

            if session['rommon_count'] == 1:
                # Now reset the device
                spawn.send("reset\r\r")
                session['rommon_count'] += 1

            elif session['rommon_count'] == 2:
                # Set the configuration register to boot directly from flash
                # hereafter, and not boot to rommon.
                spawn.send("confreg 0x1\r")
                session['rommon_count'] += 1

            elif session['rommon_count'] == 3:
                # Now boot the image
                spawn.sendline(cmd)
                session['rommon_count'] += 1
            else:
                raise Exception(
                    'Rommon prompt encountered unexpectedly'
                    ', Maybe golden image does not exist for  % ', str(spawn))
        else:
            # The rommon prompt is seen for the first time since the
            # "Please reset" message was detected.
            # Set the configuration register to 0x0 (boot to rommon) and reset.
            # This is recommended in the platform documentation:
            # http://www.cisco.com/c/en/us/support/docs/routers/4000-platform-integrated-services-routers/200678-Troubleshoot-Cisco-4000-platform-ISR-Stuck.pdf
            spawn.send("confreg 0x0\r")
            session['rommon_count'] = 1


def grub_prompt_handler(spawn, session, context):
    """ handles the grub menu during boot process
    """

    # if grub prompt already handled, return
    if session.get('grub_handler'):
        return
    else:
        session['grub_handler'] = True
        # Below is used by the boot_timeout statement
        # with the `BOOT_TIMEOUT` setting.
        context['boot_start_time'] = datetime.now()
        context['boot_prompt_count'] = 1

    grub_boot_image = context.get('grub_boot_image')
    # if no grub_boot_image, do nothing
    if not grub_boot_image:
        return

    spawn.log.info("Finding an entry that includes the string '{}'".
             format(grub_boot_image))

    # Regex to match grub screen boot entries on cat9kv
    lines = re.findall(spawn.settings.GRUB_REGEX_PATTERN, spawn.buffer)

    spawn.log.debug(f'Grub lines: {lines}')

    selected_line = None
    desired_line = None

    # Get index for selected_line and desired_line
    for index, line in enumerate(lines):
        # \x1b[7m is reverse video (inverted colors)
        if '*' in line or '\x1b[7m' in line:
            selected_line = index
        if grub_boot_image in line:
            desired_line = index

    if selected_line is None or desired_line is None:
        raise Exception("Cannot figure out which image to select! "
                        "Debug info:\n"
                        "selected_line: {}\n"
                        "desired_line: {}\n"
                        "lines: {}"
                        .format(selected_line, desired_line, lines))

    spawn.log.info("Selecting the entry '{}' now.".format(lines[desired_line]))

    num_lines_to_move = desired_line - selected_line

    spawn.log.debug(f'Lines to move: {num_lines_to_move}')

    keys = {
        'down': '\x1B[B',
        'up': '\x1B[A'
    }
    # If positive we want to move down the list.
    # If negative we want to move up the list.
    if num_lines_to_move >= 0:
        key = 'down'
    else:
        key = 'up'

    for _ in range(abs(num_lines_to_move)):
        spawn.send(keys.get(key))
        time.sleep(0.5)

    spawn.sendline()
    time.sleep(0.5)


def boot_image(spawn, context, session):
    if not context.get('boot_prompt_count'):
        context['boot_prompt_count'] = 1
    if context.get('boot_prompt_count') < \
            spawn.settings.MAX_BOOT_ATTEMPTS:
        if "boot_cmd" in context:
            cmd = context.get('boot_cmd')
        elif "image_to_boot" in context:
            cmd = "boot {}".format(context['image_to_boot']).strip()
        elif spawn.settings.FIND_BOOT_IMAGE:
            filesystem = spawn.settings.BOOT_FILESYSTEM if \
                hasattr(spawn.settings, 'BOOT_FILESYSTEM') else 'flash:'
            spawn.buffer = ''
            spawn.sendline('dir {}'.format(filesystem))
            dir_listing = spawn.expect(patterns.rommon_prompt).match_output
            boot_file_regex = spawn.settings.BOOT_FILE_REGEX if \
                hasattr(spawn.settings, 'BOOT_FILE_REGEX') else r'(\S+\.bin)'
            m = re.search(boot_file_regex, dir_listing)
            if m:
                boot_image = m.group(1)
                cmd = "boot {}{}".format(filesystem, boot_image)
            else:
                cmd = "boot"
        else:
            cmd = "boot"
        spawn.sendline(cmd)
        context['boot_prompt_count'] += 1
    else:
        raise Exception("Too many failed boot attempts have been detected.")


boot_from_rommon_stmt = Statement(
    pattern=patterns.rommon_prompt,
    action=boot_image,
    args=None,
    loop_continue=True,
    continue_timer=False)


# Statement covering when a device asks us to reset it.
please_reset_stmt = \
    Statement(pattern=reload_patterns.please_reset,
              action=please_reset_handler,
              args=None,
              loop_continue=True,
              continue_timer=False)

grub_prompt_stmt = \
    Statement(pattern=reload_patterns.grub_prompt,
              action=grub_prompt_handler,
              args=None,
              loop_continue=True,
              continue_timer=False)

setup_dialog_stmt = \
    Statement(pattern=reload_patterns.setup_dialog,
              action='sendline(no)',
              args=None,
              loop_continue=True,
              continue_timer=False)

auto_install_stmt = \
    Statement(pattern=reload_patterns.autoinstall_dialog,
              action='sendline(yes)',
              args=None,
              loop_continue=True,
              continue_timer=False)

# This list is extended later, see below
boot_from_rommon_statement_list = [
    please_reset_stmt, admin_password_stmt,
    setup_dialog_stmt, auto_install_stmt,
    boot_timeout_stmt
]


def boot_finished_deco(func):
    '''Decorator function that wraps dialog statements
    for rommon to disable state transition to pop the
    boot_start_time  after boot is (supposedly) finished.

    Used with boot_from_rommon_statement_list (see below)
    '''

    @wraps(func)
    def wrapper(spawn, session, context, **kwargs):
        args = [a for a in [spawn, session, context] if a]
        if context:
            context.pop('boot_start_time', None)
        return func(*args, **kwargs)
    return wrapper


# Create list of statements for rommon to disable, i.e. device boot
# If the boot is completed because we hit a statement with
# loop_continue = False, use the wrapper to pop the start time
# from the context dict.
boot_from_rommon_statement_list += connection_statement_list.copy()
for stmt in boot_from_rommon_statement_list:
    if stmt.pattern in [reload_patterns.press_return] or stmt.loop_continue is False:
        stmt.action = boot_finished_deco(stmt.action)
