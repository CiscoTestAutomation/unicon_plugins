"""
Module:
    unicon.plugins.generic.service_implementation

Authors:
    pyATS TEAM (pyats-support@cisco.com, pyats-support-ext@cisco.com)

Description:
  This module contains dual-rp and single rp service implementation
  code for generic platform. These services are implemented by subclassing
  BaseService and handle majority of platforms.

"""

import io
import os
import re
import copy
import logging
import collections
import ipaddress
from itertools import chain
import time
import warnings
from datetime import datetime, timedelta

from time import sleep

from unicon.bases.routers.services import BaseService
from unicon.core.errors import SubCommandFailure, StateMachineError, \
    CopyBadNetworkError, TimeoutError, UniconBackendDecodeError
from unicon.eal.dialogs import Dialog
from unicon.eal.dialogs import Statement
from unicon.plugins.generic.statements import (
    chatty_term_wait,
    custom_auth_statements,
    buffer_settled,
    default_statement_list)
from unicon.plugins.generic.service_statements import reload_statement_list, \
    ping_dialog_list, extended_ping_dialog_list, copy_statement_list, \
    ha_reload_statement_list, switchover_statement_list, \
    standby_reset_rp_statement_list, trace_route_dialog_list
from unicon.plugins.generic.service_patterns import CopyPatterns
from unicon.utils import AttributeDict, to_plaintext
from unicon import logs
from unicon.logs import UniconStreamHandler, UNICON_LOG_FORMAT

from unicon.plugins.generic.utils import GenericUtils
from .service_statements import execution_statement_list, configure_statement_list
from unicon.plugins.generic.statemachine import config_transition

utils = GenericUtils()
ReloadResult = collections.namedtuple('ReloadResult', ['result', 'output'])

class SwitchoverResult:
    def __init__(self, result, output, **kwargs):
        self.result = result
        self.output = output


def invalid_state_change_action(spawn, err_state, sm):
    msg = "Expected device to reach '{}' state, but landed on '{}' state."\
          .format(sm.current_state, err_state.name)
    # Update device current state with unexpected state.
    sm.update_cur_state(err_state)
    raise StateMachineError(msg)


class Send(BaseService):
    """Service to send the command/string with "\\r" to spawned channel.

    If target is passed as standby, command will be sent to standby spawn.

    Arguments:
        command: Command to be sent.
        target: Target connection, Defaults to active.

    Returns:
        True: on Success

    Raises:
        SubCommandFailure: on failure.

    Example:
        .. code-block:: python

            rtr.send("show clock\\r")
            rtr.send("show clock\\r", target='standby')

    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, command, target=None, *args, **kwargs):
        spawn = self.get_spawn(target)
        try:
            spawn.send(command, *args, **kwargs)
        except Exception as err:
            raise SubCommandFailure("Failed to send the command to spawn",
                                    err) from err
        self.result = True

    def get_service_result(self):
        return self.result


class Sendline(BaseService):
    """ Sendline Service

    Service to  send the command/string to spawned channel,
    "\\r" will be appended to command by sendline. If target
    is passed as standby, command will be sent to standby
    spawn.

    Arguments:
        command: Command to be sent
        target: Target connection, Defaults to active

    Returns:
        True: on Success

    Raises:
        SubCommandFailureError: On failure of service

    Example:
        .. code-block:: python

            rtr.sendline("show clock")
            rtr.sendline("show clock", target='standby')
    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, command='', target=None, *args, **kwargs):
        spawn = self.get_spawn(target)
        try:
            spawn.sendline(command, *args, **kwargs)
        except Exception as err:
            raise SubCommandFailure("Failed to send the command to spawn",
                                    err) from err
        self.result = True

    def get_service_result(self):
        return self.result


class Expect(BaseService):
    """match a list of pattern again the buffer

    Arguments:
        patterns: list of patterns.
        timeout: time to wait for any of the patterns to match.
        size: read size in bytes for reading the buffer.
        trim_buffer: whether to trim the buffer after a successful match.
        target: ``standby`` to match a list of patterns against the buffer on standby spawn channel.
        search_size: maximum size in bytes to search at the end of the buffer

    Returns:
        ExpectMatch instance.
        * It contains the index of the pattern that matched.
        * matched string.
        * re match object.

    Raises:
        TimeoutError: In case no match is found within the timeout period
        or raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.sendline("a command")
            rtr.expect([r'^pat1', r'pat2'], timeout=10, target='standby')
    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, patterns, timeout=None,
                     size=None, trim_buffer=True,
                     target=None, *args, **kwargs):

        spawn = self.get_spawn(target)
        try:
            self.result = spawn.expect(patterns, timeout, size, *args, **kwargs)
        except Exception as err:
            raise SubCommandFailure("Failed to match buffer on spawn",
                                    err) from err

    def get_service_result(self):
        return self.result


class ReceiveService(BaseService):
    """match a pattern from spawn buffer

    Arguments:
        pattern: regular expression pattern to match. If r'nopattern^' is used then
                 no pattern is match and all data till timeout period will be matched.
        timeout: time to wait for the pattern to match.
        size: read size in bytes for reading the buffer.
        trim_buffer: whether to trim the buffer after a successful match. Default is True.
        target: ``standby`` to match a list of pattern against the buffer on standby spawn channel.
        search_size: maximum size in bytes to search at the end of the buffer

    Returns:
        Bool: True or False
        True: If data is matched by provided pattern.
        False: If nothing is matched by pattern.
        Data matched by pattern is set to receiveBuffer attribute of connection object.

    Raises:
        No Exception is raised if pattern does not get match or timeout happens.
        SubCommandFailure will be raised if any Exception is raised apart from TimeoutError.

    Example:
        .. code-block:: python

            rtr.sendline("a command")
            rtr.receive(r'some_pattern', timeout=10, target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, pattern, timeout=None,
                     size=None, trim_buffer=True,
                     target=None, *args, **kwargs):
        spawn = self.get_spawn(target)
        self.result = False
        self.connection.receiveBuffer = ''
        try:
            if pattern == r'nopattern^':
                sleep(timeout or 10)
                self.connection.receiveBuffer = spawn.expect(r'.*', size, *args, **kwargs).match_output
            else:
                self.connection.receiveBuffer = spawn.expect(pattern, timeout, size, *args, **kwargs).match_output
                self.result = True
        except TimeoutError:
            pass
        except Exception as err:
            raise SubCommandFailure("Receive service failed", err) from err

    def get_service_result(self):
        return self.result


class ReceiveBufferService(BaseService):
    """Returns data match by receive() service pattern.

    Returns:
        String: Data matched by receive() service pattern.

    Raises:
        SubCommandFailure: If this is called without calling receive() service.

    Example:
        .. code-block:: python

            rtr.sendline("a command")
            rtr.receive(r'some_pattern', timeout=10, target='standby')
            output = rtr.receive_buffer()
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self):
        try:
            self.result = self.connection.receiveBuffer
        except AttributeError as err:
            raise SubCommandFailure("receive_buffer should be invoked after receive call", err)
        except Exception as err:
            raise SubCommandFailure("Error in receive_buffer", err) from err

    def get_service_result(self):
        result = copy.copy(self.result)
        delattr(self.connection, 'receiveBuffer')
        return result


class LogUser(BaseService):
    """ Service to enable or disable a device logs on screen.

    Arguments:
        enable: True/False

    Example:
        .. code-block:: python

            rtr.log_user(enable=True)
            rtr.log_user(enable=False)
    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, enable, target=None, *args, **kwargs):
        conn = self.connection

        if enable:
            conn.log.info("+++ log_user: enable +++")

            # does it exist already
            for hdlr in conn.log.handlers:
                if type(hdlr) in (logs.UniconStreamHandler,
                                  logs.UniconScreenHandler):
                    break
            else:
                # add it
                try:
                    from pyats.log import managed_handlers  # noqa
                except Exception:
                    sh = logs.UniconStreamHandler()
                    sh.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s'))
                    conn.log.addHandler(sh)
                else:
                    conn.log.addHandler(logs.UniconScreenHandler())
        else:
            conn.log.info("+++ log_user: disable +++")

            for hdlr in conn.log.handlers:
                if type(hdlr) in (logs.UniconStreamHandler,
                                  logs.UniconScreenHandler):
                    conn.log.removeHandler(hdlr)

        self.result = True

    def get_service_result(self):
        return self.result


class LogFile(BaseService):
    """ Service to get or change Device FileHandler file.
        If no argument passed then it return current filename of FileHandler.
        Return True, if file handlers updated with new filename.

    Arguments:
        filename: file name in which device logs to dump.

    Example:
        .. code-block:: python

            rtr.log_file(filename='/some/path/uut.log')
            rtr.log_file()
    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, filename=None, *args, **kwargs):
        conn = self.connection
        file_handler = ''
        self.result = False
        for hdlr in conn.log.handlers:
            if isinstance(hdlr, logs.UniconFileHandler):
                file_handler = hdlr
                break
        if filename:
            filename = os.path.abspath(filename)
            conn.log.info("+++ logfile: {} +++".format(filename))
            if file_handler:
                file_handler.close()
                conn.log.removeHandler(file_handler)
            fh = logs.UniconFileHandler(filename)
            fh.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s'))
            conn.log.addHandler(fh)
            self.result = True
        else:
            if file_handler:
                self.result = file_handler.baseFilename

    def get_service_result(self):
        return self.result


class ExpectLogging(BaseService):
    r""" Service to enable expect internal logging.

    Arguments:
        enable: True/False for enabling and disabling the expect_log

    Example:

        .. code::

            rtr.expect_log(enable=True)
    """

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, enable=False,
                     *args, **kwargs):

        con = self.connection
        if enable:
            con.log.info("+++ enable debug logging +++")
            con.log.setLevel(logging.DEBUG)
        else:
            con.log.info("+++ disable debug logging +++")
            con.log.setLevel(logging.INFO)

        self.result = True

    def get_service_result(self):
        return self.result


class Enable(BaseService):
    """ Brings device to enable

    Service to change the device mode to enable from any state.
    Brings the standby handle to enable state, if standby is passed as input.

    Arguments:
        target= Target connection, Defaults to active

    Returns:
        True on Success, raise SubCommandFailure on failure

    Example:
        .. code-block:: python

            rtr.enable()
            rtr.enable(target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        # Connection object will have all the received details
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.__dict__.update(kwargs)

    def pre_service(self, *args, **kwargs):
        self.prompt_recovery = self.connection.prompt_recovery
        if 'prompt_recovery' in kwargs:
            self.prompt_recovery = kwargs.get('prompt_recovery')

    def call_service(self, target=None, command='', *args, **kwargs):
        handle = self.get_handle(target)
        spawn = self.get_spawn(target)
        sm = self.get_sm(target)
        timeout = kwargs.get('timeout', None)

        # If the device is in rommon, enable() will use the
        # image_to_boot info to boot the image specified
        # by the user. This is used by boot_image in iosxe/statements.py
        # (IOSXE only implementation at this time.)
        handle.context["image_to_boot"] = \
            kwargs.get("image_to_boot", kwargs.get('image', ''))

        # override command to be enable when command is given
        if command:
            disable = sm.get_state('disable')
            enable = sm.get_state('enable')
            pt = sm.get_path(disable, enable)
            sm.paths[sm.paths.index(pt)].command = command
        try:
            sm.go_to(self.start_state,
                     spawn,
                     context=handle.context,
                     timeout=timeout)
        except Exception as err:
            raise SubCommandFailure("Failed to Bring device to Enable State",
                                    err) from err
        self.result = True


class Disable(BaseService):
    """Service to change the device to disable mode from any state.

    Brings the standby handle to disable state, if standby is passed as
    input.

    Arguments:
        target: Target connection, Defaults to active

    Returns:
        True on Success, raise SubCommandFailure on failure

    Example:
        .. code-block:: python

            rtr.disable()
            rtr.disable(target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'disable'
        self.end_state = 'disable'
        self.__dict__.update(kwargs)

    def call_service(self, target=None, *args, **kwargs):
        handle = self.get_handle(target)
        spawn = self.get_spawn(target)
        sm = self.get_sm(target)
        try:
            sm.go_to(self.start_state,
                     spawn,
                     context=handle.context)
        except Exception as err:
            raise SubCommandFailure("Failed to Bring device to Disable State",
                                    err) from err
        self.result = True


class Execute(BaseService):
    """ Execute Service implementation

    Service  to executes exec_commands on the device and return the
    console output. reply option can be passed for the interactive exec
    command.
    By default, device start state should be same as end state. If device
    ends in some other state, StateMachineError exception is raised. For not to
    raise exception on state change, use allow_state_change=True.

    Arguments:
        command: string or list of strings
        reply: Additional Dialog patterns for interactive exec commands.
        timeout : Timeout value in sec, Default Value is 60 sec
        error_pattern: list of regex to detect command errors
        search_size: maximum size in bytes to search at the end of the buffer
        allow_state_change: Boolean. Default is None. If True, end state can be any state.
        service_dialog: Instance of Dialog that overrides the execute service dialog.
        matched_retries: retry times if state pattern is matched, default is 1
        matched_retry_sleep: sleep between matched_retries, default is 0.05 sec

    Returns:
        String for single command, list for repeated single command,
        dict for multiple commands.

        raises SubCommandFailure on failure
        raises StateMachineError when device fail to reach original state

    Example:
        .. code-block:: python

              output = rtr.execute("show clock")

    """

    def __init__(self, connection, context, **kwargs):
        # Connection object will have all the received details
        super().__init__(connection, context, **kwargs)
        self.start_state = 'any'
        self.end_state = 'any'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.__dict__.update(kwargs)
        self.utils = utils
        self.dialog = Dialog(execution_statement_list)
        self.matched_retries = connection.settings.EXECUTE_MATCHED_RETRIES
        self.matched_retry_sleep = connection.settings.EXECUTE_MATCHED_RETRY_SLEEP
        self.state_change_matched_retries = connection.settings.EXECUTE_STATE_CHANGE_MATCH_RETRIES
        self.state_change_matched_retry_sleep = connection.settings.EXECUTE_STATE_CHANGE_MATCH_RETRY_SLEEP

    def log_service_call(self):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, command=[],  # noqa: C901
                     reply=Dialog([]),
                     timeout=None,
                     error_pattern=None,
                     append_error_pattern=None,
                     search_size=None,
                     allow_state_change=None,
                     matched_retries=None,
                     matched_retry_sleep=None,
                     *args, **kwargs):
        con = self.connection
        sm = self.get_sm()
        if allow_state_change is None:
            allow_state_change = con.settings.EXEC_ALLOW_STATE_CHANGE

        timeout = timeout or self.timeout

        if error_pattern is None:
            self.error_pattern = con.settings.ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        if append_error_pattern:
            if not isinstance(append_error_pattern, list):
                raise ValueError('append_error_pattern should be a list')
            self.error_pattern += append_error_pattern

        # user specified search buffer size
        if search_size is not None:
            con.spawn.search_size = search_size
        else:
            con.spawn.search_size = con.settings.SEARCH_SIZE

        matched_retries = self.matched_retries \
            if matched_retries is None else matched_retries
        matched_retry_sleep = self.matched_retry_sleep \
            if matched_retry_sleep is None else matched_retry_sleep

        if (reply is None) or (reply == []):
            reply = Dialog([])
        elif not isinstance(reply, Dialog):
            raise SubCommandFailure(
                "dialog passed via 'reply' must be an instance of Dialog")

        # service_dialog overrides the default execution dialogs
        if 'service_dialog' in kwargs:
            service_dialog = kwargs['service_dialog']
            if (service_dialog is None) or (service_dialog == []):
                service_dialog = Dialog([])
            elif not isinstance(service_dialog, Dialog):
                raise SubCommandFailure(
                    "dialog passed via 'service_dialog' must be an instance of Dialog")

            dialog = self.service_dialog(
                service_dialog=service_dialog + reply,
                matched_retries=matched_retries,
                matched_retry_sleep=matched_retry_sleep
            )
        else:
            dialog = self.dialog + self.service_dialog(
                service_dialog=reply,
                matched_retries=matched_retries,
                matched_retry_sleep=matched_retry_sleep
            )

            # add default execution statements
            custom_auth_stmt = custom_auth_statements(con.settings.LOGIN_PROMPT,
                                                      con.settings.PASSWORD_PROMPT)
            if custom_auth_stmt:
                dialog += Dialog(custom_auth_stmt)

        # Add all known states to detect state changes.
        for state in sm.states:
            # The current state is already added by the service_dialog method
            if state.name != sm.current_state:
                if allow_state_change:
                    dialog.append(Statement(
                        pattern=state.pattern,
                        matched_retries=self.state_change_matched_retries,
                        matched_retry_sleep=self.state_change_matched_retry_sleep
                    ))
                else:
                    dialog.append(Statement(
                        pattern=state.pattern,
                        action=invalid_state_change_action,
                        args={'err_state': state, 'sm': sm},
                        matched_retries=self.state_change_matched_retries,
                        matched_retry_sleep=self.state_change_matched_retry_sleep
                    ))

        # store the last used dialog, used by unittest
        self._last_dialog = dialog

        if isinstance(command, str):
            if len(command) == 0:
                commands = ['']
            else:
                commands = command.splitlines()
        elif isinstance(command, list):
            commands = command
        else:
            raise ValueError('Command passed is not of type string or list (%s)' % type(command))

        if con.settings.IGNORE_CHATTY_TERM_OUTPUT:
            # clear buffer log messages
            chatty_term_wait(con.spawn, trim_buffer=True)

        command_output = {}
        for command in commands:

            message = f"executing command '{command}'"
            super().log_service_call(message)

            con.sendline(command)
            try:
                dialog_match = dialog.process(
                    con.spawn,
                    timeout=timeout,
                    prompt_recovery=self.prompt_recovery,
                    context=con.context
                )
                if dialog_match:
                    self.result = dialog_match.match_output
                    self.result = self.get_service_result()
                sm.detect_state(con.spawn, con.context)
            except StateMachineError:
                raise
            except UniconBackendDecodeError:
                pass
            except Exception as err:
                raise SubCommandFailure("Command execution failed", err) from err

            if self.result:
                output = self.utils.truncate_trailing_prompt(
                    sm.get_state(sm.current_state),
                    self.result,
                    hostname=con.hostname,
                    result_match=dialog_match,
                )
                output = self.extra_output_process(output)
                output = output.replace(command, "", 1)
                # only strip first newline and leave formatting intact
                output = re.sub(r"^\r?\r\n", "", output, 1)
                output = output.rstrip()

                if command in command_output:
                    if isinstance(command_output[command], list):
                        command_output[command].append(output)
                    else:
                        command_output[command] = [command_output[command], output]
                else:
                    command_output[command] = output

        if len(command_output) == 1:
            self.result = list(command_output.values())[0]
        else:
            self.result = command_output

        # revert search size to default
        con.spawn.search_size = con.settings.SEARCH_SIZE

        if self.end_state != 'any':
            sm.go_to(self.end_state, con.spawn,
                     prompt_recovery=self.prompt_recovery,
                     context=con.context)

    def extra_output_process(self, output):
        # remove backspace and ansi escape sequence from output
        # scenario 1: it prevents correct command replacement, on linux terminals
        # scenario 2: router with '\x1b[KSomething\x08 \x08\x08 \x08\x08 \x08\x08 \x08\x08\x1b[K'
        return utils.remove_backspace_ansi_escape(output)


class Configure(BaseService):
    """Service to configure device with single or list of `commands`.

    Config without config_command will take device to config mode.
    Commands Should be list, if `config_command` are more than one.
    reply option can be passed for the interactive config command.

    Arguments:
        commands : list/single config command
        reply: Addition Dialogs for interactive config commands.
        timeout : Timeout value in sec, Default Value is 30 sec
        error_pattern: list of regex to detect command errors
        allow_state_change: If True allow the state change during the
               configuration otherwise raise state machine error if the state
               changes during configuration.
        target: Target RP where to execute service, for DualRp only
        lock_retries: retry times if config mode is locked, default is 0
        lock_retry_sleep: sleep between retries, default is 2 sec
        bulk: If False, send all commands in one sendline,
              If True, send commands in chunked mode,
              default is False
        bulk_chunk_lines: maximum number of commands to send per chunk,
                          default is 50,
                          0 means to send all commands in a single chunk
        bulk_chunk_sleep: sleep between sending command chunks,
                          default is 0.5 sec
        result_check_per_command: boolean option, check results after
                                  each command (default: True)

    Returns:
        command output on Success, raise SubCommandFailure on failure

    Example:
        .. code-block:: python

              output = rtr.configure()
              output = rtr.configure('no logging console')
              cmd =['hostname si-tvt-7200-28-41', 'no logging console']
              output = rtr.configure(cmd)
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'config'
        self.end_state = 'enable'
        self.timeout = connection.settings.CONFIG_TIMEOUT
        self.dialog = Dialog(configure_statement_list)
        self.commit_cmd = ''
        self.bulk = connection.settings.BULK_CONFIG
        self.bulk_chunk_lines = connection.settings.BULK_CONFIG_CHUNK_LINES
        self.bulk_chunk_sleep = connection.settings.BULK_CONFIG_CHUNK_SLEEP
        self.valid_transition_commands = ['end', 'exit']
        self.valid_transition_states = ['config_pki_hexmode']
        self.state_change_matched_retries = connection.settings.EXECUTE_STATE_CHANGE_MATCH_RETRIES
        self.state_change_matched_retry_sleep = connection.settings.EXECUTE_STATE_CHANGE_MATCH_RETRY_SLEEP
        self.__dict__.update(kwargs)

        class ConfigUtils(GenericUtils):
            def truncate_trailing_prompt(self, con_state,
                                         result,
                                         hostname=None,
                                         result_match=None):
                host_idx = result.rfind(hostname)
                result = result[:host_idx] if host_idx \
                    else result
                return result

        self.utils = ConfigUtils()

    def pre_service(self, *args, **kwargs):
        sm = self.get_sm()
        self.prompt_recovery = kwargs.get('prompt_recovery', False)

        # Backward compatibility with old config lock implementation
        con = self.connection
        settings = con.settings
        settings.CONFIG_LOCK_RETRIES = kwargs.get('lock_retries', settings.CONFIG_LOCK_RETRIES)
        settings.CONFIG_LOCK_RETRY_SLEEP = kwargs.get('lock_retry_sleep', settings.CONFIG_LOCK_RETRY_SLEEP)

        super().pre_service(*args, **kwargs)

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self,   # noqa: C901
                     command=[],
                     reply=Dialog([]),
                     timeout=None,
                     error_pattern=None,
                     append_error_pattern=None,
                     allow_state_change=None,
                     target=None,
                     bulk=None,
                     bulk_chunk_lines=None,
                     bulk_chunk_sleep=None,
                     result_check_per_command=True,
                     *args,
                     **kwargs):

        self.result_check_per_command = result_check_per_command
        con = self.connection
        sm = self.get_sm()
        handle = self.get_handle(target)
        timeout = timeout or self.timeout

        if allow_state_change is None:
            allow_state_change = con.settings.CONFIGURE_ALLOW_STATE_CHANGE

        if error_pattern is None:
            self.error_pattern = \
                handle.settings.CONFIGURE_ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        if append_error_pattern:
            if not isinstance(append_error_pattern, list):
                raise ValueError('append_error_pattern should be a list')
            self.error_pattern += append_error_pattern

        bulk = self.bulk if bulk is None else bulk
        bulk_chunk_lines = self.bulk_chunk_lines \
            if bulk_chunk_lines is None else bulk_chunk_lines
        bulk_chunk_sleep = self.bulk_chunk_sleep \
            if bulk_chunk_sleep is None else bulk_chunk_sleep

        if not isinstance(reply, Dialog):
            raise SubCommandFailure('"reply" must be an instance of Dialog')

        def config_state_change(spawn, from_state, sm):
            last_cmd = spawn.last_sent.strip()
            # check if the last command is not in the list of valid commands and the state is not in the list of valid states
            # for transition
            if last_cmd not in self.valid_transition_commands and from_state.name not in self.valid_transition_states:
                invalid_state_change_action(
                    spawn, err_state=from_state, sm=sm)
            else:
                sm.update_cur_state(from_state)

        self.result = ''
        if command:
            flat_cmd = self.utils.flatten_splitlines_command(command)
            dialog = self.dialog + self.service_dialog(handle=handle, service_dialog=reply)
            sp = handle.spawn
            # Add all known states to detect state changes.
            for state in sm.states:
                # The current state is already added by the service_dialog method
                if state.name != sm.current_state:
                        if allow_state_change:
                            dialog.append(Statement(
                                pattern=state.pattern,
                                matched_retries=self.state_change_matched_retries,
                                matched_retry_sleep=self.state_change_matched_retry_sleep
                            ))
                        else:
                            dialog.append(Statement(
                                pattern=state.pattern,
                                action=config_state_change,
                                args={'from_state': state, 'sm': sm},
                                matched_retries=self.state_change_matched_retries,
                                matched_retry_sleep=self.state_change_matched_retry_sleep
                            ))
            if bulk:
                indicator = handle.settings.BULK_CONFIG_END_INDICATOR
                cmd_lst = list(chain(flat_cmd, [indicator]))
                if bulk_chunk_lines == 0:
                    chunks = [cmd_lst]
                else:
                    chunks = [cmd_lst[i:i + bulk_chunk_lines]
                              for i in range(0, len(cmd_lst), bulk_chunk_lines)]
                for idx, chunk in enumerate(chunks, 1):
                    chunk_cmd = '\n'.join(chunk)
                    sp.sendline(chunk_cmd)
                    if idx != len(chunks):
                        sleep(bulk_chunk_sleep)
                        sp.read_update_buffer()
                    else:
                        try:
                            sp.expect([indicator], timeout=timeout,
                                      trim_buffer=False)
                            self.result, _, sp.buffer = \
                                sp.buffer.rpartition(indicator)
                        except Exception as err:
                            raise SubCommandFailure('Configuration failed',
                                                    err) from err
                self.process_dialog_on_handle(handle, dialog, timeout)
                if self.commit_cmd:
                    sp.sendline(self.commit_cmd)
                    self.process_dialog_on_handle(handle, dialog, timeout)
            else:
                cmds = chain(flat_cmd, [self.commit_cmd]) \
                    if self.commit_cmd else flat_cmd
                for cmd in cmds:
                    sp.sendline(cmd)
                    self.update_hostname_if_needed([cmd])
                    self.process_dialog_on_handle(handle, dialog, timeout)
                    # To handle the session
                    if handle.context.get('config_session_locked'):
                        self.connection.log.warning('Config locked, waiting {} seconds'.format(
                            self.connection.settings.CONFIG_LOCK_RETRY_SLEEP))
                        sleep(self.connection.settings.CONFIG_LOCK_RETRY_SLEEP)
                        config_transition(handle.state_machine, handle.spawn, handle.context)
                        handle.context['config_session_locked'] = False
                        sp.sendline(cmd)
                        self.process_dialog_on_handle(handle, dialog, timeout)

        # store config_result so it can be returned to the user later
        config_result = self.result
        output = handle.state_machine.go_to(
            self.end_state,
            handle.spawn,
            prompt_recovery=self.prompt_recovery,
            timeout=timeout,
            context=self.context
        )
        # set self.result, this is used by get_server_result to check for errors
        self.result = output
        # check for errors in the transition to the end_state
        self.get_service_result()
        # return the config_result to the user via self.result
        self.result = config_result

    def process_dialog_on_handle(self, handle, dialog, timeout):
        try:
            cmd_result = dialog.process(
                handle.spawn,
                timeout=timeout,
                prompt_recovery=self.prompt_recovery,
                context=handle.context
            )
        except StateMachineError:
            raise
        except Exception as err:
            raise SubCommandFailure("Command execution failed", err) from err

        cmd_result = self.utils.truncate_trailing_prompt(
            handle.state_machine.get_state(handle.state_machine.current_state),
            cmd_result.match_output,
            hostname=handle.hostname,
            result_match=cmd_result)
        self.result += cmd_result
        if self.result_check_per_command:
            try:
                self.get_service_result()
            except SubCommandFailure:
                # Go to end state after command failure,
                handle.state_machine.go_to(self.end_state,
                                        handle.spawn,
                                        context=self.context)
                raise

    def update_hostname_if_needed(self, cmd_list):
        for cmd in cmd_list:
            m = re.match(r'^\s*(hostname|switchname) (\S+)', cmd)
            if m:
                self.connection.hostname = m.group(2)
                return


class Config(Configure):

    def call_service(self, *args, **kwargs):
        self.connection.log.warning('**** This service is deprecated. Please use "configure" service ****')
        super().call_service(*args, **kwargs)


class Reload(BaseService):
    """Service to reload the device.

    Arguments:
        reload_command: reload command to be issued. default is "reload"
        reload_creds: credential or list of credentials to use to respond to
                      username/password prompts.
        reply: Dialog which include list of Statements for
               additional dialogs prompted by reload command, in-case
               it is not in the current list.
        timeout: Timeout value in sec, Default Value is 300 sec
        return_output: If True, return a namedtuple with result and output
                result is True if reload is successful.
                output contains reload command output.

    Returns:
        True on Success, raise SubCommandFailure on failure

    Example ::
        .. code-block:: python

                  rtr.reload()
                  # If reload command is other than 'reload'
                  rtr.reload(reload_command="reload location all", timeout=400)

    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.RELOAD_TIMEOUT
        self.dialog = Dialog(reload_statement_list + default_statement_list)
        self.log_buffer = io.StringIO()
        lb = UniconStreamHandler(self.log_buffer)
        lb.setFormatter(logging.Formatter(fmt=UNICON_LOG_FORMAT))
        self.connection.log.addHandler(lb)
        self.__dict__.update(kwargs)

    def call_service(self,
                     reload_command='reload',
                     dialog=Dialog([]),
                     reply=Dialog([]),
                     timeout=None,
                     return_output=False,
                     reload_creds=None,
                     raise_on_error=True,
                     error_pattern=None,
                     append_error_pattern=None,
                     post_reload_wait_time = None,
                     *args, **kwargs):

        con = self.connection
        timeout = timeout or self.timeout

        syslog_wait = con.settings.SYSLOG_WAIT
        con.settings.SYSLOG_WAIT = con.settings.RELOAD_SYSLOG_WAIT

        if error_pattern is None:
            self.error_pattern = con.settings.ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        if post_reload_wait_time is None:
            self.post_reload_wait_time = con.settings.POST_RELOAD_WAIT
        else:
            self.post_reload_wait_time = post_reload_wait_time

        if not isinstance(self.error_pattern, list):
            raise ValueError('error_pattern should be a list')
        if append_error_pattern:
            if not isinstance(append_error_pattern, list):
                raise ValueError('append_error_pattern should be a list')
            self.error_pattern += append_error_pattern

        # Clear log buffer
        self.log_buffer.seek(0)
        self.log_buffer.truncate()

        fmt_msg = "+++ reloading %s " \
                  " with reload_command '%s' " \
                  "and timeout is %s seconds +++"
        con.log.info(fmt_msg % (self.connection.hostname, reload_command, timeout))

        if reply:
            if dialog:
                con.log.warning("**** Both 'reply' and 'dialog' were provided "
                                "to the reload service.  Ignoring 'dialog'.")
            dialog = reply
        elif dialog:
            warnings.warn('**** "dialog" parameter is deprecated.  '
                          'Use "reply" instead. ****',
                          category=DeprecationWarning)

        if not isinstance(dialog, Dialog):
            raise SubCommandFailure(
                "dialog passed must be an instance of Dialog")

        dialog += self.dialog
        custom_auth_stmt = custom_auth_statements(con.settings.LOGIN_PROMPT, con.settings.PASSWORD_PROMPT)
        if custom_auth_stmt:
            dialog += Dialog(custom_auth_stmt)

        if reload_creds:
            context = self.context.copy()
            context.update(cred_list=reload_creds)
        else:
            context = self.context

        start_time = current_time = datetime.now()
        timeout_time = timedelta(seconds=timeout)
        con.spawn.sendline(reload_command)

        try:
            reload_output = dialog.process(con.spawn,
                            timeout=timeout,
                            prompt_recovery=self.prompt_recovery,
                            context=context)
            self.result = reload_output.match_output
            self.get_service_result()
        except Exception as e:
            if hasattr(con.device, 'clean') and hasattr(con.device.clean, 'device_recovery') and\
                con.device.clean.device_recovery.get('golden_image'):
                    con.log.exception(f"Reload failed to install with file: {getattr(con.device.clean, 'images', [None])[0]}")
                    con.log.info(f'Booting the device using golden_image.')
                    con.device.api.device_recovery_boot(golden_image=con.device.clean.device_recovery['golden_image'])
                    con.log.info('Successfully booted the device using golden_image.')
                    raise
            elif raise_on_error:
                raise
            else:
                con.log.exception(f'Reload failed: {e}')
                self.result = False
        if not con.connected:
            con.disconnect()
            for x in range(con.settings.RELOAD_RECONNECT_ATTEMPTS):
                con.log.info('Waiting for {} seconds'.format(con.settings.RELOAD_WAIT / (x + 1)))
                sleep(con.settings.RELOAD_WAIT / (x + 1))
                try:
                    con.log.info('Trying to connect... attempt #{}'.format(x + 1))
                    con.connect()
                except Exception:
                    con.log.exception('Connection to {} failed'.format(con.hostname))
                    self.result = False
                if con.is_connected:
                    self.result = True
                    break
        else:
            con.log.info('Waiting for boot messages to settle for {} seconds'.format(
                self.post_reload_wait_time
            ))
            wait_time = timedelta(seconds=self.post_reload_wait_time)
            settle_time = current_time = datetime.now()
            while (current_time - settle_time) < wait_time:
                if buffer_settled(con.spawn, self.post_reload_wait_time):
                    con.log.info('Buffer settled, accessing device..')
                    break
                current_time = datetime.now()
                if (current_time - start_time) > timeout_time:
                    con.log.info('Time out, trying to acces device..')
                    break

            # ! This line was added to resolve an issue with HA devices, but was
            # ! found to cause further issues with other devices on reload
            # TODO Need to find a better way to implement a fix for HA devices
            # TODO that does not cause issues with other devices. Likely need to
            # TODO modify the state machine and/or dialog processing.
            # con.sendline()
        try:
            con.context = context
            con.connection_provider.connect()
            self.result = True
        except Exception:
            if raise_on_error:
                raise
            else:
                con.log.exception('Connection to {} failed'.format(con.hostname))
                self.result = False

        con.settings.SYSLOG_WAIT = syslog_wait

        self.log_buffer.seek(0)
        reload_output = self.log_buffer.read()
        # clear buffer
        self.log_buffer.truncate()

        if return_output:
            self.result = ReloadResult(self.result, reload_output)

        if self.result:
            con.log.info('--- Reload of device {} completed ---'.format(con.hostname))
        else:
            con.log.info('--- Reload of device {} failed ---'.format(con.hostname))


class Traceroute(BaseService):
    """ Service to issue traceroute response request to another network from device.

    Returns:
        traceroute command response on Success

    Raises:
        SubCommandFailure on failure

    Example:
        .. code-block:: python

            traceroute(addr="9.33.11.41")
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = 60
        self.dialog = Dialog(trace_route_dialog_list)
        self.__dict__.update(kwargs)

    def call_service(self, addr, command="traceroute", timeout=None, error_pattern=None, **kwargs):
        con = self.connection
        con.log.debug("+++ traceroute +++")

        traceroute_options = ['addr', 'proto', 'ingress', 'source', 'dscp', 'numeric',
                              'timeout', 'probe', 'minimum_ttl', 'maximum_ttl',
                              'port', 'style', 'resolve_as_number']

        if error_pattern is None:
            self.error_pattern = con.settings.TRACEROUTE_ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        # Default value setting
        timeout = timeout or self.timeout

        trace_route_context = AttributeDict({})

        # Read input values passed
        # Convert to string in case users pass in non-string types such as
        # integer for repeat_count or ipaddress for addr, src_addr or
        # src_route_addr keys.
        # The EAL backend requires all commands to be of string type.
        for key in kwargs:
            if key in traceroute_options:
                trace_route_context[key] = str(kwargs[key])
            else:
                con.log.warning("Unsupported traceroute option {}, ignoring".format(key))

        # Validate Inputs
        if addr:
            # Do string conversion on addr, if specified,
            # in case the user passes in an ipaddress object instead of a
            # string.
            trace_route_context['addr'] = str(addr)
        else:
            raise SubCommandFailure("Address is not specified ")

        # Stringify the command in case it is an object.
        trace_route_str = str(command)
        dialog = self.service_dialog(service_dialog=self.dialog)
        spawn = self.get_spawn()

        spawn.sendline(trace_route_str)
        try:
            self.result = dialog.process(spawn, context=trace_route_context, timeout=timeout)
        except TimeoutError:
            # Recover prompt and re-raise
            # Ctrl+shift+6
            spawn.send('\x1E')
            # Empty buffer
            spawn.expect(".+", trim_buffer=True)
            raise
        except Exception as err:
            raise SubCommandFailure("Traceroute failed", err) from err

        self.result = self.result.match_output
        if self.result.rfind(self.connection.hostname):
            self.result = self.result[:self.result.rfind(self.connection.hostname)]


class Ping(BaseService):
    """ Service to issue ping response request to another network from device.

    Returns:
        ping command response on Success

    Raises:
        SubCommandFailure on failure

    Example:
        .. code-block:: python

            ping(addr="9.33.11.41")
            ping(addr="10.2.1.1", extd_ping='y')

    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = 60
        self.dialog = Dialog(extended_ping_dialog_list)
        # Ping error Patterns
        self.error_pattern = ['^.*(% )?DSCP.*does not match any topology',
                              'Bad IP (A|a)ddress', 'Ping transmit failed',
                              'Invalid vrf', 'Unable to find',
                              'No Route to Host.*',
                              'Destination Host Unreachable',
                              'Unable to initialize Windows Socket Interface',
                              'IP routing table .* does not exist',
                              'Invalid input',
                              'bad context', 'Failed to resolve',
                              '(U|u)nknown (H|h)ost',
                              'Success rate is 0 percent',
                              '100.00% packet loss',
                              '100 % packet loss',
                              'Invalid host']

        self.__dict__.update(kwargs)

    def call_service(self, addr, command="ping", timeout=None, **kwargs):  # noqa: C901
        con = self.connection
        con.log.debug("+++ ping +++")

        # Extended ping options
        # If one of these is passed, set 'extd_ping' to 'y' automatically
        ext_ping_options = [
            'data_pat',
            'df_bit',
            'dscp',
            'exp',
            'extended_verbose',
            'force_exp_null_label',
            'ingress_int',
            'interface',
            'pad',
            'precedence',
            'record_hops',
            'reply_mode',
            'source',
            'src_route_addr',
            'src_route_type',
            'sweep_interval',
            'sweep_max',
            'sweep_min',
            'sweep_ping',
            'timestamp_count',
            'tos',
            'ttl',
            'udp',
            'validate_reply_data',
            'verbose',
        ]

        # Ping Options
        ping_options = [
            'multicast', 'transport', 'mask', 'vcid', 'tunnel',
            'dest_start', 'dest_end',
            'proto', 'count', 'size',
            'interval', 'timeout_limit',
            'send_interval', 'vrf', 'topo',
            'lsp_ping_trace_rev', 'oif',
            'novell_type', 'extd_ping',
            'extended_timeout_limit',
            'ipv6_ext_headers', 'ipv6_hbh_headers',
            'ipv6_dst_headers', 'ping_packet_timeout',
            'ping_failures', 'addr'
        ] + ext_ping_options

        # Default value setting
        timeout = timeout or self.timeout

        # Prepare ping context
        # set some default values
        ping_context = AttributeDict({})
        for a in ping_options:
            if a == "novell_type":
                ping_context[a] = "\r"
            elif a == "sweep_ping":
                ping_context[a] = "n"
            elif a == 'extd_ping':
                ping_context[a] = "n"
            else:
                ping_context[a] = ""

        # old to new argument mapping
        deprecated_arg_map = {
            'int': 'interface',
            'src_addr': 'source'
        }
        # Read input values passed
        # Convert to string in case users pass in non-string types such as
        # integer for repeat_count or ipaddress for addr, src_addr or
        # src_route_addr keys.
        # The EAL backend requires all commands to be of string type.
        for key in kwargs:

            # if one of the extended ping options is given,
            # automatically set extd_ping to y.
            # If extd_ping is explicitly set to 'n',
            # it will be set by logic below
            if key in ext_ping_options:
                ping_context['extd_ping'] = 'y'

            if key in deprecated_arg_map:
                con.log.warning(
                    'ping service "{key}" argument is deprecated, '
                    'please use "{new_key}" instead'.format(
                        key=key,
                        new_key=deprecated_arg_map.get(key)
                    ))
                old_key = key
                key = deprecated_arg_map.get(key)
                ping_context[key] = str(kwargs[old_key])
            else:
                # this also sets extd_ping to 'n'
                # if provided by user
                ping_context[key] = str(kwargs[key])

        # Validate Inputs
        if ping_context['addr'] == "":
            if addr:
                # Do string conversion on addr, if specified,
                # in case the user passes in an ipaddress object instead of a
                # string.
                ping_context['addr'] = str(addr)
            else:
                raise SubCommandFailure("Address is not specified ")

        if ping_context['src_route_type'] != "":
            if ping_context['src_route_addr'] in "":
                raise SubCommandFailure("If src route type is set, "
                                        "then src route addr is mandatory \n")
        elif ping_context['src_route_addr'] != "":
            raise SubCommandFailure("If src route addr is set, "
                                    "then src route type is mandatory \n")

        # Stringify the command in case it is an object.
        ping_str = str(command)

        # If only the address is passed, ping it directly
        if not kwargs:
            ping_str += ' {}'.format(addr)

        if ping_context['topo'] != "":
            ping_str = ping_str + "  topo " + ping_context['topo']

        handle = self.get_handle()
        spawn = self.get_spawn()
        if ping_context['extd_ping'].lower().startswith('y'):
            dialog = self.service_dialog(
                handle=handle, service_dialog=self.dialog)
        else:
            dialog = self.service_dialog(
                handle=handle, service_dialog=Dialog(ping_dialog_list))

        spawn.sendline(ping_str)
        try:
            self.result = dialog.process(
                spawn, context=ping_context, timeout=timeout)
        except Exception as err:
            # catch the prompt before raising an exception
            # this uses 'any' state and not 'end_state'
            # on purpose, this works best with real devices.
            handle.state_machine.go_to('any',
                                       handle.spawn,
                                       context=self.context)
            raise SubCommandFailure("Ping failed", err) from err

        self.result = self.result.match_output
        if self.result.rfind(self.connection.hostname):
            self.result = self.result[:self.result.rfind(self.connection.hostname)]


class Copy(BaseService):
    """ Implements Copy service

    Service to support variants of the IOS copy command, which basically
    copies images and configs into and out of router Flash memory.

    Arguments:
        timeout: Timeout value in sec, Default Value is 60 sec

    Returns:
        True on Success, raise SubCommandFailure on failure

    Example:
        .. code-block:python

            out = rtr.copy(source='running-conf',
                         dest='startup-config')

            copy_input = {'source' :'tftp:',
                          'dest':'disk0:',
                          'source_file' : 'copy-test',
                          'dest_file':'copy-test'}
            out = rtr.copy(copy_input)

            out = rtr.copy(source = 'tftp:',
                           dest = 'bootflash:',
                           source_file  = 'copy-test',
                           dest_file = 'copy-test',
                           server='10.105.33.158')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = 100
        self.dialog = Dialog(copy_statement_list)
        self.copy_pat = CopyPatterns()
        self.interrupt = connection.settings.COPY_INTERRUPT
        self.__dict__.update(kwargs)
        if not hasattr(self, 'max_attempts'):
            self.max_attempts = self.connection.settings.MAX_COPY_ATTEMPTS

    def call_service(self, reply=Dialog([]), *args, **kwargs):  # noqa: C901
        con = self.connection
        # Inputs supported
        copy_options = ['source', 'dest', 'dest_file', 'source_file',
                        'server', 'user', 'password', 'vrf', 'erase',
                        'partition', 'overwrite', 'timeout', 'net_type',
                        'dest_directory']

        # Default values
        copy_context = AttributeDict({})
        for a in copy_options:
            if a == "partition":
                copy_context[a] = 0
            elif a == "erase":
                copy_context[a] = "n"
            elif a == 'overwrite':
                # To Handle overwrite = False condition 
                overwrite = kwargs.get('overwrite', True)
                copy_context[a] = overwrite
            elif a == 'vrf':
                copy_context[a] = "Mgmt-intf"
            elif a == 'timeout':
                copy_context[a] = self.timeout
            elif a == 'password':
                password = kwargs.pop('password', None)
                if password:
                    copy_context[a] = to_plaintext(password)
                else:
                    copy_context[a] = ""
            else:
                copy_context[a] = ""

        if not isinstance(reply, Dialog):
            raise SubCommandFailure('reply passed must be instance of Dialog')

        # Read input values passed
        # Stringify input values in case they are objects
        for key in kwargs:
            copy_context[key] = str(kwargs[key])

        if 'max_attempts' in kwargs:
            self.max_attempts = kwargs['max_attempts']

        # Validate input
        if copy_context['source'] == "" or copy_context['dest'] == "":
            raise SubCommandFailure(
                "Source and Destination must be specified ")

        if copy_context['source_file'] == "":
            copy_context['source_file'] = copy_context['source']
        remote_source = ""
        remote_dest = ""
        copy_match = re.search(self.copy_pat.remote_param, copy_context['source'])
        if copy_match:
            remote_source = copy_match.group()
        copy_match = re.search(self.copy_pat.remote_param, copy_context['dest'])
        if copy_match:
            remote_dest = copy_match.group()

        if remote_dest != "" or remote_source != "":
            match_server = ""
            src_server_match = re.search(self.copy_pat.addr_in_remote, copy_context['source'])
            dest_server_match = re.search(self.copy_pat.addr_in_remote, copy_context['dest'])
            if src_server_match or dest_server_match:
                try:
                    match_server = src_server_match.group(2)
                    ipaddress.ip_address(match_server)
                except Exception:
                    try:
                        match_server = dest_server_match.group(2)
                        ipaddress.ip_address(match_server)
                    except Exception:
                        match_server = ""
            if copy_context['server'] == "":
                if match_server == "":
                    raise SubCommandFailure(
                        "Server address must be specified for remote copy")
                else:
                    copy_context['server'] = match_server

        timeout = copy_context['timeout'] or self.timeout

        handle = self.get_handle()
        spawn = self.get_spawn()
        dialog = self.service_dialog(handle=handle, service_dialog=self.dialog)

        dialog = reply + dialog

        copy_string = "copy  " + \
                      copy_context['source'] + " " + copy_context['dest']

        if 'extra_options' in kwargs:
            copy_string = copy_string + " " + kwargs['extra_options']

        if self.max_attempts < 1:
            raise SubCommandFailure(
                "Copy failed : max_attempts must be 1 or greater but "
                "{} was specified.".format(self.max_attempts))

        for retry_num in range(self.max_attempts):
            spawn.sendline(copy_string)
            try:
                if (sleep_time := kwargs.get('sleep_time')):
                    con.log.info(f"sleep for {sleep_time} seconds")
                    time.sleep(sleep_time)
                self.result = dialog.process(spawn,
                                             context=copy_context,
                                             timeout=timeout)
            except CopyBadNetworkError as err:
                try:
                    # copy_retry_message pattern only trims part of buffer
                    # consume buffer that is remaining there
                    handle.state_machine.go_to('any',
                                               handle.spawn,
                                               context=self.context)
                except Exception:
                    pass
                if retry_num != (self.max_attempts - 1):
                    # wait for a prompt before retry
                    spawn.sendline()
                    handle.state_machine.go_to('any',
                                               handle.spawn,
                                               context=self.context)

                    con.log.info("Copy failure encountered.  Retrying ...")
                else:
                    raise SubCommandFailure("Copy failed", err) from err
            except TimeoutError as err:
                # keep TimeoutError separately, as its consuming buffer part
                # is a best effort and may have different logic later
                # from CopyBadNetworkError
                spawn.send(self.interrupt)
                try:
                    # consume buffer if any is remaining there
                    handle.state_machine.go_to('any',
                                               handle.spawn,
                                               context=self.context)
                except Exception:
                    pass
                if retry_num != (self.max_attempts - 1):
                    # wait for a prompt before retry
                    spawn.sendline()
                    handle.state_machine.go_to('any',
                                               handle.spawn,
                                               context=self.context)
                    con.log.info("Copy dialog timeout encountered.  Retrying ...")
                else:
                    raise SubCommandFailure("Copy failed", err) from err
            except Exception as err:
                try:
                    # copy_error_message pattern may only trim part of buffer
                    # consume buffer if any is remaining there
                    handle.state_machine.go_to('any',
                                               handle.spawn,
                                               context=self.context)
                except Exception:
                    pass
                raise SubCommandFailure("Copy failed", err) from err
            else:
                break

        self.result = self.result.match_output
        if self.result.rfind(self.connection.hostname):
            self.result = self.result[:self.result.rfind(self.connection.hostname)]


class GetMode(BaseService):
    """ Service to get the redundancy mode of the device.

    Returns:
        'sso', 'rpr' or raise SubCommandFailure on failure.

    Example ::
        .. code-block:: python

            rtr.get_mode()
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.__dict__.update(kwargs)

    def call_service(self,
                     timeout=None,
                     utils=utils,
                     *args,
                     **kwargs):

        timeout = timeout or self.timeout
        try:
            self.result = utils.get_redundancy_details(self.connection,
                                                       timeout=timeout)
        except Exception as err:
            raise SubCommandFailure("get_mode failed", err) from err

    def get_service_result(self):
        if 'mode' in self.result:
            return self.result.mode
        else:
            return "None"


class GetRPState(BaseService):
    """ Get Rp state

    Service to get the redundancy state of the device rp.
    Returns  standby rp state if standby is passed as input.

    Arguments:
        target: Service target, by default active

    Returns:
        Expected return values are ACTIVE, STANDBY COLD, STANDBY HOT
        raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.get_rp_state()
            rtr.get_rp_state(target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.__dict__.update(kwargs)

    def call_service(self,
                     target='active',
                     timeout=None,
                     utils=utils,
                     *args,
                     **kwargs):
        """send the command on the right rp and return the output"""
        handle = self.get_handle(target)

        red_handle = 'my'
        if handle.alias == self.connection.standby.alias:
            red_handle = 'peer'

        try:
            self.result = utils.get_redundancy_details(self.connection, timeout=timeout, who=red_handle)
        except Exception as err:
            raise SubCommandFailure("get_rp_state failed", err) from err

    def get_service_result(self):
        if 'state' in self.result:
            return self.result.state
        else:
            return "None"


class GetConfig(BaseService):
    """Service return running configuration of the device.

    Returns:
        standby running configuration if standby is passed as input.

    Arguments:
        target: Service target, by default active

    Returns:
      running configuration on Success, raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.get_config()
            rtr.get_config(target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.__dict__.update(kwargs)

    def pre_service(self, *args, **kwargs):
        pass

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self,
                     target='active',
                     timeout=None,
                     *args,
                     **kwargs):
        try:
            self.result = self.connection.execute("show running-config",
                                                  target=target,
                                                  timeout=timeout)
        except Exception as err:
            raise SubCommandFailure("get_config failed", err) from err


class SyncState(BaseService):
    """Bring the device to stable state and re-designate the handles role.

    Returns:
        True on Success, raises SubcommandFailure exception on failure

    Example:
        .. code-block:: python

            rtr.sync_state()
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.__dict__.update(kwargs)

    def pre_service(self, *args, **kwargs):
        self.prompt_recovery = kwargs.get('prompt_recovery', False)

    def call_service(self,
                     target='active',
                     timeout=None,
                     *args,
                     **kwargs):

        con = self.connection
        try:
            # ToDo: Missing code to bring the device to stable state
            self.result = con.connection_provider.designate_handles()
        except Exception as err:
            raise SubCommandFailure("Failed to bring the device to stable state") from err
        self.result = True

    def get_service_result(self):
        return self.result


class HaExecService(BaseService):
    """ DualRp execute service

    Service  to executes exec_commands on the device and return the
    console output. reply option can be passed for the interactive exec
    command. Command will be executed on standby if target is specified
    as standby.

    Arguments:
        command: exec command
        target: Target RP where to execute service
        reply: Additional Dialog( i.e patterns) to be handled
        timeout: Timeout value in sec, Default Value is 60 sec
        matched_retries: retry times if state pattern is matched, default is 1
        matched_retry_sleep: sleep between matched_retries, default is 0.05 sec

    Returns:
        String for single command, list for repeated single command,
        dict for multiple commands.

        raises SubCommandFailure on failure.
        raises StateMachineError when device lands on unexpected state

    Example:
        .. code-block:: python

            output = rtr.execute("show clock")
            output = rtr.execute("show logging", timeout=200)
            output = rtr.execute("show clock", target='standby')
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'any'
        self.end_state = 'any'
        self.__dict__.update(kwargs)
        self.dialog = Dialog(execution_statement_list)

    def log_service_call(self):
        pass

    def pre_service(self, *args, **kwargs):
        self.prompt_recovery = kwargs.get('prompt_recovery', False)

    def post_service(self, *args, **kwargs):
        pass

    def call_service(self, command,
                     reply=Dialog([]),
                     target='active',
                     timeout=None,
                     error_pattern=None,
                     search_size=None,
                     allow_state_change=None,
                     matched_retries=None,
                     matched_retry_sleep=None,
                     *args,
                     **kwargs):
        """send the command on the right rp and return the output"""
        # create an alias for connection.
        handle = self.get_handle(target)

        self.result = handle.execute(command,
                                     reply=reply,
                                     timeout=timeout,
                                     error_pattern=error_pattern,
                                     search_size=search_size,
                                     allow_state_change=allow_state_change,
                                     matched_retries=matched_retries,
                                     matched_retry_sleep=matched_retry_sleep,
                                     *args,
                                     **kwargs)


class HaConfigureService(Configure):
    """DualRp configure service
    Service to configure device with single or list of `commands`.

    Config without config_command will take device to config mode.
    Commands Should be list, if `config_command` are more than one.
    reply option can be passed for the interactive config command.
    Command can be executed on standby by pass in target as standby.

    Arguments:
        commands : list/single config command
        reply: Addition Dialogs for interactive config commands.
        timeout : Timeout value in sec, Default Value is 30 sec
        target: Target RP where to execute service
        lock_retries: retry times if config mode is locked, default is 0
        lock_retry_sleep: sleep between retries, default is 2 sec
        bulk: send commands in one sendline or not, default is False

    Returns:
        command output on Success, raise SubCommandFailure on failure

    Example:
        .. code-block:: python

              output = rtr.configure()
              output = rtr.configure('no logging console')
              cmd =['hostname si-tvt-7200-28-41', 'no logging console']
              output = rtr.configure(cmd)
              output = rtr.configure(cmd, target='standby')
    """
    pass


class HaConfigure(HaConfigureService):

    def call_service(self, *args, **kwargs):
        self.connection.log.warning('**** This service is deprecated. ' +
                                    'Please use "configure" service ****')
        super().call_service(*args, **kwargs)


# TODO Add option to take additional dialog
class HAReloadService(BaseService):
    """ Service to reload the device.

    Arguments:
        reload_command: reload command to be used. default "redundancy reload shelf"
        reload_creds: credential or list of credentials to use to respond to
                      username/password prompts.
        reply: Additional Dialog( i.e patterns) to be handled
        timeout: Timeout value in sec, Default Value is 60 sec
        return_output: if True, return namedtuple with result and reload output

    Returns:
        console True on Success, raises SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.reload()
            # If reload command is other than 'redundancy reload shelf'
            rtr.reload(reload_command="reload location all", timeout=700)
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.HA_RELOAD_TIMEOUT
        self.dialog = Dialog(ha_reload_statement_list + default_statement_list)
        self.command = 'reload'
        self.__dict__.update(kwargs)

    def call_service(self,  # noqa: C901
                     reload_command=None,
                     command=None,
                     dialog=Dialog([]),
                     reply=Dialog([]),
                     target='active',
                     timeout=None,
                     return_output=False,
                     reload_creds=None,
                     target_standby_state='STANDBY HOT',
                     error_pattern = None,
                     append_error_pattern= None,
                     *args,
                     **kwargs):


        con = self.connection

        if error_pattern is None:
            self.error_pattern = con.settings.ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        if not isinstance(self.error_pattern, list):
                raise ValueError('error_pattern should be a list')
        if append_error_pattern:
            if not isinstance(append_error_pattern, list):
                raise ValueError('append_error_pattern should be a list')
            self.error_pattern += append_error_pattern

        if reply:
            if dialog:
                con.log.warning("**** Both 'reply' and 'dialog' were provided "
                                "to the reload service.  Ignoring 'dialog'.")
            dialog = reply
        elif dialog:
            warnings.warn('**** "dialog" parameter is deprecated.  '
                          'Use "reply" instead. ****',
                          category=DeprecationWarning)

        timeout = timeout or self.timeout
        if command:
            con.log.warning("*** HA reload() service 'command' parameter "
                            "will be deprecated in next release. "
                            "Please use 'reload_command' parameter ***")
        if command and reload_command:
            raise SubCommandFailure(
                "Please use either 'command' or 'reload_command' parameter")
        command = command or reload_command or self.command

        # TODO counter value must be moved to settings
        counter = 0
        fmt_str = "+++ reloading %s with reload_command '%s' and timeout is %s +++"
        con.log.info(fmt_str % (con.hostname, command, timeout))
        dialog += self.dialog
        custom_auth_stmt = custom_auth_statements(con.settings.LOGIN_PROMPT, con.settings.PASSWORD_PROMPT)

        if reload_creds:
            context = con.active.context.copy()
            context.update(cred_list=reload_creds)
            sby_context = con.standby.context.copy()
            sby_context.update(cred_list=reload_creds)
        else:
            context = con.active.context
            sby_context = con.standby.context

        if custom_auth_stmt:
            dialog += Dialog(custom_auth_stmt)

        # Issue reload command
        con.active.spawn.sendline(command)
        try:
            reload_output = dialog.process(con.active.spawn,
                                           context=context,
                                           prompt_recovery=self.prompt_recovery,
                                           timeout=timeout)
            self.result=reload_output.match_output

            self.get_service_result()

            con.active.state_machine.go_to('any',
                                           con.active.spawn,
                                           prompt_recovery=self.prompt_recovery,
                                           timeout=con.connection_timeout,
                                           context=context)

            # Bring standby to good state.
            con.log.info('Waiting for config sync to finish')
            standby_wait_time = con.settings.POST_HA_RELOAD_CONFIG_SYNC_WAIT
            standby_wait_interval = 50
            standby_sync_try = standby_wait_time // standby_wait_interval + 1
            for round in range(standby_sync_try):
                con.standby.spawn.sendline()
                try:
                    con.standby.state_machine.go_to(
                        'any',
                        con.standby.spawn,
                        context=sby_context,
                        timeout=standby_wait_interval,
                        prompt_recovery=self.prompt_recovery,
                        dialog=con.connection_provider.get_connection_dialog()
                    )
                    break
                except Exception as err:
                    if round == standby_sync_try - 1:
                        raise Exception(
                            'Bringing standby to any state failed within {} sec'.format(standby_wait_time)) from err

            # If standby is in rommon, use state machine to transition to disable state
            if con.standby.state_machine.current_state == 'rommon':
                con.log.info('Standby is in ROMMON state, transitioning to disable mode')
                con.standby.state_machine.go_to(
                    'disable',
                    con.standby.spawn,
                    context=sby_context,
                    timeout=timeout,
                    prompt_recovery=self.prompt_recovery,
                    dialog=con.connection_provider.get_connection_dialog()
                )

        except Exception as err:
            if hasattr(con.device, 'clean') and hasattr(con.device.clean, 'device_recovery') and\
                con.device.clean.device_recovery.get('golden_image'):
                con.log.error(f'Reload failed booting device using golden image: {con.device.clean.device_recovery["golden_image"]}')
                con.device.api.device_recovery_boot(golden_image=con.device.clean.device_recovery['golden_image'])
                con.log.info(f'Successfully booted the device using golden image.')
            raise SubCommandFailure(f"Reload failed : {err}")

        # Re-designate handles before applying config.
        # Roles could have switched as a result of the reload.
        con.connection_provider.designate_handles()
        con.connection_provider.unlock_standby()

        con.active.state_machine.go_to('enable',
                                       con.active.spawn,
                                       prompt_recovery=self.prompt_recovery,
                                       context=context)

        # Issue init commands to disable console logging
        exec_commands = con.active.settings.HA_INIT_EXEC_COMMANDS
        for exec_command in exec_commands:
            con.execute(exec_command, prompt_recovery=self.prompt_recovery)
        config_commands = con.active.settings.HA_INIT_CONFIG_COMMANDS

        config_lock_retries_ori = con.settings.CONFIG_LOCK_RETRIES
        config_lock_retry_sleep_ori = con.settings.CONFIG_LOCK_RETRY_SLEEP
        con.active.settings.CONFIG_LOCK_RETRY_SLEEP = con.active.settings.CONFIG_POST_RELOAD_RETRY_DELAY_SEC
        con.active.settings.CONFIG_LOCK_RETRIES = con.active.settings.CONFIG_POST_RELOAD_MAX_RETRIES

        try:
            con.configure(config_commands,
                          target='active',
                          prompt_recovery=self.prompt_recovery)
        except Exception:
            raise
        finally:
            con.settings.CONFIG_LOCK_RETRIES = config_lock_retries_ori
            con.settings.CONFIG_LOCK_RETRY_SLEEP = config_lock_retry_sleep_ori

        # best effort for 'STANDBY HOT', consider argument for mandatory/ignore
        while counter < 31:
            try:
                # TODO need fix iosxr get_rp_state service
                rp_state = con.get_rp_state(target='standby', timeout=30)
                if rp_state.find(target_standby_state) != -1:
                    con.log.info('Standby RP State: {}'.format(rp_state))
                    counter = 32
                else:
                    con.log.info('Standby RP State: {}, waiting for {}'.format(rp_state, target_standby_state))
                    sleep(6)
                    counter += 1
            except Exception as err:
                con.log.error('Failed to get RP state: {}'.format(err))
                sleep(6)
                counter += 1

        con.log.info("+++ Reload Completed Successfully +++")
        self.result = True
        if return_output:
            self.result = ReloadResult(self.result, reload_output)


class SwitchoverService(BaseService):
    """ Service to switchover the device.

    Arguments:
        command: command to do switchover. default
                 "redundancy force-switchover"
        switchover_creds: credential or list of credentials to use to respond to
                      username/password prompts.
        dialog: Dialog which include list of Statements for
                additional dialogs prompted by switchover command,
                in-case it is not in the current list.
        timeout: Timeout value in sec, Default Value is 500 sec

    Returns:
        True on Success, raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.switchover()
            # If switchover command is other than 'redundancy force-switchover'
            rtr.switchover(command="command which invoke switchover",
            timeout=700)
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.SWITCHOVER_TIMEOUT
        self.dialog = Dialog(switchover_statement_list)
        self.command = 'redundancy force-switchover'
        self.__dict__.update(kwargs)

    def call_service(self, command=None,  # noqa: C901
                     dialog=Dialog([]),
                     reply=Dialog([]),
                     timeout=None,
                     sync_standby=True,
                     switchover_creds=None,
                     *args,
                     **kwargs):
        # create an alias for connection.
        con = self.connection
        if reply:
            if dialog:
                con.log.warning("**** Both 'reply' and 'dialog' were provided "
                                "to the reload service.  Ignoring 'dialog'.")
            dialog = reply
        elif dialog:
            warnings.warn('**** "dialog" parameter is deprecated.'
                          ' Please use "reply" ****',
                          category=DeprecationWarning)

        timeout = timeout or self.timeout
        command = command or self.command
        switchover_counter = con.settings.SWITCHOVER_COUNTER
        con.log.debug("+++ Issuing switchover on  %s  with "
                      "switchover_command %s and timeout is %s +++"
                      % (con.hostname, command, timeout))

        # Check is switchover possible?
        rp_state = con.get_rp_state(target='standby', timeout=100)
        if rp_state.find('STANDBY HOT') == -1:
            raise SubCommandFailure(
                "Switchover can't be issued in %s state" % rp_state)

        # Save current active and standby handle details
        standby_start_cmd = con.standby.start
        dialog += self.dialog
        dialog = self.service_dialog(handle=con.active,
                                     service_dialog=dialog)
        custom_auth_stmt = custom_auth_statements(con.settings.LOGIN_PROMPT, con.settings.PASSWORD_PROMPT)
        if custom_auth_stmt:
            dialog += Dialog(custom_auth_stmt)

        # Use the standby credentials when processing because any
        # authentication request is expected to come from the new active.
        if switchover_creds:
            context = con.standby.context.copy()
            context.update(cred_list=switchover_creds)
        else:
            context = con.standby.context

        # Issue switchover command
        con.active.spawn.sendline(command)
        try:
            dialog.process(con.active.spawn,
                           timeout=timeout,
                           prompt_recovery=self.prompt_recovery,
                           context=context)
        except TimeoutError:
            pass
        except SubCommandFailure as err:
            raise SubCommandFailure("Switchover Failed %s" % str(err)) from err

        # swap roles after switchover
        con.swap_roles()

        counter = 0
        if not sync_standby:
            con.log.info("Standby state check disabled on user request")

        else:
            while counter < switchover_counter:
                con.active.spawn.sendline("\r")
                con.active.spawn.expect(".*")
                try:
                    rp_state = con.get_rp_state(target='standby',
                                                timeout=60)
                except (SubCommandFailure, TimeoutError):
                    sleep(9)
                    counter += 1
                    continue
                except Exception:
                    con.active.spawn.sendline("\r")
                    con.active.spawn.expect(".*")
                    continue
                else:
                    if re.search('STANDBY HOT', rp_state):
                        counter = switchover_counter + 1
                    else:
                        sleep(9)
                        counter += 1

            con.active.state_machine.go_to(
                'any',
                con.active.spawn,
                context=context,
                prompt_recovery=self.prompt_recovery,
                timeout=con.connection_timeout,
                dialog=con.connection_provider.get_connection_dialog()
            )
            con.active.state_machine.go_to(
                'enable',
                con.active.spawn,
                context=context,
                prompt_recovery=self.prompt_recovery
            )

            # Issue init commands to disable console logging
            exec_commands = self.connection.settings.HA_INIT_EXEC_COMMANDS
            for command in exec_commands:
                con.execute(command, prompt_recovery=self.prompt_recovery)
            config_commands = self.connection.settings.HA_INIT_CONFIG_COMMANDS
            con.configure(config_commands, prompt_recovery=self.prompt_recovery)

            # Try to determine state for to standby node,
            # if first attempt fails, sendline and check again
            for _ in range(2):
                # Determine standby state
                try:
                    con.standby.state_machine.go_to('any',
                                                    con.standby.spawn,
                                                    context=con.standby.context,
                                                    dialog=con.connection_provider.get_connection_dialog())
                    break
                except Exception:
                    con.log.error("Failed to bring standby rp to any state")
                    con.standby.spawn.sendline()
            else:
                raise Exception("Failed to bring standby rp to any state")

            con.enable(target='standby')
        # Verify switchover is Successful
        if con.active.start == standby_start_cmd:
            con.log.info("Switchover is Successful")
            self.result = True
        else:
            con.log.info("Switchover is Failed")
            self.result = False


class ResetStandbyRP(BaseService):
    """ Service to reset the standby rp.

    Arguments:

        command: command to reset standby, default is"redundancy reload peer"
        reply: Dialog which include list of Statements for
                 additional dialogs prompted by standby reset command,
                 in-case it is not in the current list.
        timeout: Timeout value in sec, Default Value is 500 sec

    Returns:
        True on Success, raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.reset_standby_rp()
            # If command is other than 'redundancy reload peer'
            rtr.reset_standby_rp(command="command which will reset standby rp",
            timeout=600)

    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.HA_RELOAD_TIMEOUT
        self.dialog = Dialog(standby_reset_rp_statement_list)
        self.__dict__.update(kwargs)

    def pre_service(self, *args, **kwargs):
        self.prompt_recovery = kwargs.get('prompt_recovery', False)
        if self.connection.is_connected:
            return
        elif self.connection.reconnect:
            self.connection.connect()
        else:
            raise ConnectionError("Connection is not established to device")
        state_machine = self.connection.active.state_machine
        state_machine.go_to(self.start_state,
                            self.connection.active.spawn,
                            context=self.connection.context)

    def post_service(self, *args, **kwargs):
        state_machine = self.connection.active.state_machine
        state_machine.go_to(self.end_state,
                            self.connection.active.spawn,
                            context=self.connection.context)

    def call_service(self, command='redundancy reload peer',  # noqa: C901
                     reply=Dialog([]),
                     timeout=None,
                     *args,
                     **kwargs):
        # create an alias for connection.
        con = self.connection
        timeout = timeout or self.timeout
        # resetting the standby rp for
        con.log.debug("+++ Issuing reset on  %s  with "
                      "reset_command %s and timeout is %s +++"
                      % (con.hostname, command, timeout))

        # Check is it possible to reset the standby?
        rp_state = con.get_rp_state(target='standby', timeout=100)

        if re.search('DISABLED', rp_state):
            raise SubCommandFailure("No Standby found")

        if 'standby_check' in kwargs and not re.search(kwargs['standby_check'], rp_state):
            raise SubCommandFailure("Standby found but not in the expected state")

        dialog = self.service_dialog(handle=con.active,
                                     service_dialog=self.dialog+reply)

        # Issue standby reset command
        con.active.spawn.sendline(command)
        try:
            dialog.process(con.active.spawn,
                           timeout=30,
                           context=con.active.context)
        except TimeoutError:
            pass
        except SubCommandFailure as err:
            raise SubCommandFailure("Failed to reset standby rp %s" % str(err)) from err

        reset_counter = timeout / 10

        counter = 0
        reloadGood = False
        while counter < reset_counter:
            try:
                rp_state = con.get_rp_state(target='standby',
                                            timeout=60)
            except (SubCommandFailure, TimeoutError):
                sleep(10)
                counter += 1
                continue
            else:
                # first need to insure reload happens
                # no false positives
                if not reloadGood:
                    if not re.search('DISABLED', rp_state):
                        sleep(2)
                        counter += 1
                        continue
                    else:
                        reloadGood = True
                        counter = 0

                if re.search('STANDBY HOT', rp_state):
                    counter = reset_counter + 1
                else:
                    sleep(10)
                    counter += 1

        # Clear Standby buffer
        try:
            con.standby.spawn.sendline("\r")
            con.standby.spawn.expect(".*")
            con.standby.state_machine._current_state = 'disable'
            con.enable(target='standby')
        except SubCommandFailure as err:
            raise SubCommandFailure("Failed to bring standby to enable: %s" %
                                    str(err)) from err
        con.log.info("Successfully reloaded Standby RP")
        self.result = True


class BashService(BaseService):
    """ Service to provide an console to do shell commands

    Arguments:
        None

    Returns:
        AttributeError: No attributes

    Example:
        .. code-block:: python

            rtr.bash_console(timeout=60).execute('ls')

    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_state = "enable"
        self.end_state = "enable"
        self.bash_enabled = False

    def pre_service(self, *args, **kwargs):
        self.prompt_recovery = kwargs.get('prompt_recovery', False)
        if not self.connection.is_connected:
            if self.connection.reconnect:
                self.connection.connect()
            else:
                raise ConnectionError("Connection is not established to device")

        if 'target' in kwargs:
            handle = self.get_handle(kwargs['target'])
        else:
            handle = self.get_handle()

        handle.state_machine.go_to(
            self.start_state,
            handle.spawn,
            context=self.connection.context,
            prompt_recovery=self.prompt_recovery
        )

    def call_service(self, target=None, **kwargs):
        enable_bash = kwargs.pop('enable_bash', False)
        handle = self.get_handle(target)
        self.result = self.__class__.ContextMgr(
            connection=handle,
            enable_bash=enable_bash and not self.bash_enabled,
            end_state=self.end_state,
            **kwargs)

        # if bash wasn't enabled, it is now!
        if enable_bash:
            self.bash_enabled = True

    def post_service(self, *args, **kwargs):
        # context manager will transition to end_state
        # no need to do anything post service
        pass

    class ContextMgr(object):
        def __init__(self, connection,
                enable_bash=False,
                end_state=None,
                timeout=None,
                **kwargs):
            self.conn = connection
            # Specific platforms has its own prompt
            self.enable_bash = enable_bash
            self.end_state = end_state
            self.timeout = timeout or connection.settings.CONSOLE_TIMEOUT

        def __enter__(self):
            raise NotImplementedError('No enter shell method supports in platform {}'.format(self.conn.os))

        def __exit__(self, exc_type, exc_value, exc_tb):
            self.conn.log.debug('--- detaching console ---')

            sm = self.conn.state_machine
            sm.go_to(self.end_state, self.conn.spawn)

            # do not suppress
            return False

        def parse(self, *args, **kwargs):
            abstract_args = kwargs.setdefault('abstract', {})
            device = getattr(self.conn, 'device', None)
            if device:
                abstract_args.update(dict(
                    os=[device.os, 'linux'],
                    platform=device.platform,
                    model=device.model,
                    pid=device.pid,
                ))
                return self.conn.device.parse(*args, **kwargs)
            else:
                self.conn.log.warning('No device object, parse method unavailable')

        def __getattr__(self, attr):
            if attr in ('execute', 'sendline', 'send', 'expect'):
                return getattr(self.conn, attr)

            raise AttributeError('%s object has no attribute %s'
                                 % (self.__class__.__name__, attr))


class AttachModuleService(BaseService):
    """ Service to connect to a device module and execute commands.

    Arguments:
        None

    Returns:
        AttributeError: No attributes

    Examples:
        .. code-block:: python

            rtr.attach(1, timeout=60).execute('show interface')

            with rtr.attach(1) as m:
                m.execute('show interface')
                m.execute(['show interface 1', 'show interface 2'])
            # if we want to go to module_debug state
            with rtr.attach(1, debug=True) as m:
                m.execute('show interface')
                m.execute(['show interface 1', 'show interface 2'])


    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_state = "module"
        self.end_state = "enable"
        self.service_name = "attach"

    def pre_service(self, module_num, *args, **kwargs):
        """ Common pre_service procedure for all Services """
        self.prompt_recovery = kwargs.get('prompt_recovery', False)
        if self.connection.is_connected:
            return
        elif self.connection.reconnect:
            self.connection.connect()
        else:
            raise ConnectionError("Connection is not established to device")
        self.context._module_num = module_num

    def call_service(self, module_num, debug=False, **kwargs):
        self.result = self.__class__.ContextMgr(self.connection,
                                                module_num,
                                                debug,
                                                context=self.context,
                                                **kwargs)

    class ContextMgr(object):
        def __init__(self,
                     connection,
                     module_num,
                     debug=False,
                     target='active',
                     context=None,
                     timeout=None):
            self.conn = connection
            # Specific platforms has its own prompt
            self.timeout = timeout
            self.target = target
            self.context = context
            self.debug = debug
            self.timeout = timeout or connection.settings.CONSOLE_TIMEOUT
            self.context._module_num = module_num

        def __enter__(self):
            if self.conn.is_ha:
                if self.target == 'standby':
                    conn = self.conn.standby
                elif self.target == 'active':
                    conn = self.conn.active
            else:
                conn = self.conn

            if 'module' not in [s.name for s in conn.state_machine.states]:
                raise NotImplementedError('Attach module state not implemented')

            self.conn.log.debug('+++ attaching module +++')
            conn.state_machine.go_to('module_debug' if self.debug else 'module',
                                     conn.spawn,
                                     context=self.context,
                                     timeout=self.timeout)

            return self

        def __exit__(self, exc_type, exc_value, exc_tb):
            self.conn.log.debug('--- detaching module ---')

            if self.conn.is_ha:
                if self.target == 'standby':
                    conn = self.conn.standby
                elif self.target == 'active':
                    conn = self.conn.active
            else:
                conn = self.conn

            sm = conn.state_machine
            sm.go_to('enable', conn.spawn)

            # do not suppress
            return False

        def __getattr__(self, attr):
            if attr in ('execute', 'sendline', 'send', 'expect'):
                return getattr(self.conn, attr)

            raise AttributeError('%s object has no attribute %s'
                                 % (self.__class__.__name__, attr))


class Switchto(BaseService):
    """ Switch to a certain CLI state that is known to the statemachine
    """

    def __init__(self, connection, context, **kwargs):
        # Connection object will have all the received details
        super().__init__(connection, context, **kwargs)
        self.service_name = 'switchto'
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.context = context

    def log_service_call(self):
        pass

    def pre_service(self, to_state, *args, **kwargs):

        if not self.connection.connected:
            self.connection.log.warning('Device is not connected, ignoring switchto')
            return

        self.connection.log.info("+++ %s: %s +++" % (self.service_name, to_state))

    def call_service(self, to_state,
                     timeout=None,
                     *args, **kwargs):

        if not self.connection.connected:
            return

        con = self.connection
        sm = self.get_sm()

        timeout = timeout if timeout is not None else self.timeout

        if isinstance(to_state, str):
            to_state_list = [to_state]
        elif isinstance(to_state, list):
            to_state_list = to_state
        else:
            raise Exception('Invalid switchto to_state type: %s' % repr(to_state))

        for to_state in to_state_list:
            to_state = to_state.replace(' ', '_')

            valid_states = [x.name for x in sm.states]
            if to_state not in valid_states:
                con.log.warning('%s is not a valid state, ignoring switchto' % to_state)
                return

            con.state_machine.go_to(to_state, con.spawn,
                                    context=self.context,
                                    hop_wise=True,
                                    timeout=timeout)

        self.end_state = sm.current_state

    def post_service(self, *args, **kwargs):
        pass


class GuestshellService(BaseService):
    """Service to provide a Linux console.

    Arguments:
        enable_guestshell: Enable the guestshell if not already enabled
        timeout: Timeout for entering/exiting guestshell mode
        retries: If enable_guestshell is True, number of retries
          (waiting 5 seconds per retry) to successfully issue the
          "guestshell enable" command, and also the number of retries to wait
          for the guestshell to become activated afterward.
          Default is 20 (100 seconds maximum)

    Example:
        .. code-block:: python

            with rtr.guestshell(enable_guestshell=True, retries=10) as gs:
                gs.execute("ifconfig")

            with rtr.guestshell() as gs:
                gs.execute("ls")
                gs.execute("pwd")
    """

    def __init__(self, connection, *args, **kwargs):
        super().__init__(connection, *args, **kwargs)
        self.start_state = "enable"
        self.end_state = "enable"

    def call_service(self, **kwargs):
        self.result = self.__class__.ContextMgr(connection=self.connection,
                                                **kwargs)

    class ContextMgr(object):
        def __init__(self, connection,
                     enable_guestshell=False, timeout=None, retries=None):
            self.conn = connection
            self.enable_guestshell = enable_guestshell
            self.timeout = timeout or connection.settings.EXEC_TIMEOUT
            self.retries = retries or connection.settings.GUESTSHELL_RETRIES

        def __enter__(self):

            if 'guestshell' not in [s.name for s in self.conn.state_machine.states]:
                raise NotImplementedError('Guest shell state not implemented')

            if self.enable_guestshell:
                self.conn.log.debug("+++ enabling guestshell +++")

                if self.conn.settings.GUESTSHELL_CONFIG_CMDS:
                    output = self.conn.execute(self.conn.settings.GUESTSHELL_CONFIG_VERIFY_CMDS)
                    if isinstance(output, dict):
                        output = '\n'.join(output.values())

                    if not re.search(self.conn.settings.GUESTSHELL_CONFIG_VERIFY_PATTERN, output):
                        self.conn.configure(self.conn.settings.GUESTSHELL_CONFIG_CMDS)
                        for _ in range(self.retries):
                            output = self.conn.execute(self.conn.settings.GUESTSHELL_CONFIG_VERIFY_CMDS)
                            if isinstance(output, dict):
                                output = '\n'.join(output.values())

                            if re.search(self.conn.settings.GUESTSHELL_CONFIG_VERIFY_PATTERN, output):
                                break
                            else:
                                sleep(self.conn.settings.GUESTSHELL_RETRY_SLEEP)
                                continue
                        else:
                            raise SubCommandFailure(
                                "Failed to enable guestshell after %d tries"
                                % self.retries)

                if self.conn.settings.GUESTSHELL_ENABLE_CMDS:
                    # "guestshell enable" may fail with a "please retry request"
                    # if the guestshell is already undergoing another transition,
                    # so we may potentially need to retry the command.
                    for _ in range(self.retries):
                        # Note: "guestshell enable" is an exec command not a config
                        output = self.conn.execute(self.conn.settings.GUESTSHELL_ENABLE_CMDS,
                                                   timeout=self.timeout)
                        if isinstance(output, dict):
                            output = '\n'.join(output.values())
                        if not output or re.search("already enabled|enabled successfully", output):
                            break
                        elif "please retry request" in output:
                            sleep(self.conn.settings.GUESTSHELL_RETRY_SLEEP)
                            continue
                        else:
                            # Other output indicates some unexpected failure
                            raise SubCommandFailure(
                                "Failed to enable guestshell: %s" % output)
                    else:
                        raise SubCommandFailure(
                            "Failed to enable guestshell after %d tries"
                            % self.retries)

                if self.conn.settings.GUESTSHELL_ENABLE_VERIFY_CMDS:
                    # Okay, we successfully issued "guestshell enable".
                    # Now it may take some time for the guestshell to become
                    # fully activated (ready for use).
                    self.conn.log.debug("+++ waiting for guestshell activation +++")
                    for i in range(self.retries):
                        output = self.conn.execute(self.conn.settings.GUESTSHELL_ENABLE_VERIFY_CMDS,
                                                   timeout=self.timeout)

                        if isinstance(output, dict):
                            output = '\n'.join(output.values())
                        if re.search(self.conn.settings.GUESTSHELL_ENABLE_VERIFY_PATTERN, output):
                            # Success
                            break
                        elif "failed" in output.lower():
                            # Terminal state, won't recover
                            raise SubCommandFailure(
                                "Failed to install/activate guestshell: %s"
                                % output)
                        else:
                            # Not yet ready
                            sleep(self.conn.settings.GUESTSHELL_RETRY_SLEEP)
                            continue
                    else:
                        raise SubCommandFailure(
                            "Guestshell failed to become activated after %d tries"
                            % self.retries)

            self.conn.log.debug('+++ entering guestshell +++')
            conn = self.conn.active if self.conn.is_ha else self.conn
            conn.state_machine.go_to('guestshell',
                                     conn.spawn,
                                     timeout=self.timeout,
                                     context=self.conn.context)

            return self

        def __exit__(self, *args):
            self.conn.log.debug('--- exiting guestshell ---')
            conn = self.conn.active if self.conn.is_ha else self.conn
            conn.state_machine.go_to('enable',
                                     conn.spawn,
                                     timeout=self.timeout,
                                     context=self.conn.context)

            # do not suppress any errors that occurred
            return False

        def __getattr__(self, attr):
            if attr in ('execute', 'sendline', 'send', 'expect'):
                return getattr(self.conn, attr)

            raise AttributeError('%s object has no attribute %s'
                                 % (self.__class__.__name__, attr))

class ContextMgrBaseService(BaseService):
    """ Base service to provide a context manager for device states.
    Example:
        .. code-block:: python
        with device.service() as service:
            service.execute('command')
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_name = "context"
        self.context_state = "enable"
        self.start_state = "enable"
        self.end_state = "enable"

    def call_service(self, target=None, **kwargs):
        self.result = self.__class__.ContextMgr(
            connection=self.connection,
            service=self,
            **kwargs)

    class ContextMgr(object):
        def __init__(self, connection, service=None, **kwargs):
            self.conn = connection
            self.service = service

        def __enter__(self):
            self.conn.log.debug(f'Entering context for service {self.service.service_name}')
            sm = self.conn.state_machine
            sm.go_to(self.service.context_state,
                     self.conn.spawn,
                     context=self.conn.context)
            return self

        def __exit__(self, exc_type, exc_value, exc_tb):
            self.conn.log.debug(f'Exiting context for service {self.service.service_name}')
            sm = self.conn.state_machine
            sm.go_to(self.service.end_state,
                     self.conn.spawn,
                     context=self.conn.context)

            # do not suppress
            return False

        def __getattr__(self, attr):
            # check for connection methods
            if hasattr(self.conn, attr):
                return getattr(self.conn, attr)
            # to support .parse() and other device methods
            elif hasattr(self.conn.device, attr):
                return getattr(self.conn.device, attr)
            else:
                raise AttributeError('Device %s and/or connection %s has no attribute %s'
                                    % (self.conn.device, self.conn, attr))

