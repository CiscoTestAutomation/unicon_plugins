__author__ = "Syed Raza <syedraza@cisco.com>"

import io
import re
import logging
from time import sleep
from datetime import datetime, timedelta

from unicon.plugins.generic import service_implementation as svc
from unicon.bases.routers.services import BaseService
from unicon.core.errors import SubCommandFailure, StateMachineError
from unicon.eal.dialogs import Dialog, Statement
from unicon.logs import UniconStreamHandler
from unicon.plugins.utils import slugify
from unicon.plugins.generic.service_implementation import BashService as GenericBashService
from unicon.plugins.generic.service_implementation import GetRPState as GenericGetRPState

from .service_statements import (switchover_statement_list,
                                 config_commit_stmt_list,
                                 execution_statement_list,
                                 configure_statement_list)

from .utils import IosxrUtils
from .patterns import IOSXRPatterns

utils = IosxrUtils()
patterns = IOSXRPatterns()


def get_commit_cmd(**kwargs):
    if 'force' in kwargs and kwargs['force'] is True:
        commit_cmd = 'commit force'
    elif 'replace' in kwargs and kwargs['replace'] is True:
        commit_cmd = 'commit replace'
    elif 'best_effort' in kwargs and kwargs['best_effort'] is True:
        commit_cmd = 'commit best-effort'
    else:
        commit_cmd = 'commit'
    return commit_cmd


class Execute(svc.Execute):
    def __init__(self, connection, context, **kwargs):
        # Connection object will have all the received details
        super().__init__(connection, context, **kwargs)
        self.dialog += Dialog(execution_statement_list)


class Configure(svc.Configure):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'config'
        self.end_state = 'enable'
        self.dialog += Dialog(configure_statement_list)

    def call_service(self, command=[], reply=Dialog([]),
                     timeout=None, *args, **kwargs):
        self.commit_cmd = get_commit_cmd(**kwargs)
        super().call_service(command,
                             reply=reply + Dialog(config_commit_stmt_list),
                             timeout=timeout,
                             result_check_per_command=False,
                             *args, **kwargs)


class ConfigureExclusive(Configure):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'exclusive'
        self.end_state = 'enable'
        self.service_name = 'exclusive'


class HaConfigureService(svc.HaConfigureService):
    def call_service(self, command=[], reply=Dialog([]), target='active',
                     timeout=None, *args, **kwargs):
        self.commit_cmd = get_commit_cmd(**kwargs)
        super().call_service(command,
                             reply=reply + Dialog(config_commit_stmt_list),
                             target=target, timeout=timeout, *args, **kwargs)


class Reload(svc.Reload):

    def call_service(self, reload_command='reload', *args, **kwargs):
        super().call_service(reload_command, *args, **kwargs)


class HaReload(svc.HAReloadService):
    def call_service(self, command=[], reload_command=[], reply=Dialog([]), timeout=None, *args,
                     **kwargs):
        if command:
            super().call_service(command,
                                 timeout=timeout, *args, **kwargs)
        else:
            super().call_service(reload_command=reload_command or "reload",
                                 timeout=timeout, *args, **kwargs)


class AdminExecute(Execute):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'admin'
        self.end_state = 'enable'


class AdminConfigure(Configure):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'admin_conf'
        self.end_state = 'enable'


class HAExecute(svc.HaExecService):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.dialog += Dialog(execution_statement_list)


class HaAdminExecute(AdminExecute):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'admin'
        self.end_state = 'enable'


class HaAdminConfigure(HaConfigureService):
    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'admin_conf'
        self.end_state = 'enable'


class Switchover(BaseService):
    """ Service to switchover the device.

    Arguments:
        command: command to do switchover. default
                 "redundancy switchover"
        dialog: Dialog which include list of Statements for
                additional dialogs prompted by switchover command,
                in-case it is not in the current list.
        timeout: Timeout value in sec, Default Value is 500 sec

    Returns:
        True on Success, raise SubCommandFailure on failure.

    Example:
        .. code-block:: python

            rtr.switchover()
            # If switchover command is other than 'redundancy switchover'
            rtr.switchover(command="command which invoke switchover",
            timeout=700)
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.SWITCHOVER_TIMEOUT
        self.dialog = Dialog(switchover_statement_list)

    def call_service(self, command='redundancy switchover',
                     dialog=Dialog([]),
                     timeout=None,
                     sync_standby=True,
                     error_pattern=None,
                     *args,
                     **kwargs):
        # create an alias for connection.
        con = self.connection

        if error_pattern is None:
            self.error_pattern = con.settings.ERROR_PATTERN
        else:
            self.error_pattern = error_pattern

        start_time = datetime.now()
        timeout = timeout or self.timeout

        con.log.debug("+++ Issuing switchover on  %s  with "
                      "switchover_command %s and timeout is %s +++"
                      % (con.hostname, command, timeout))

        dialog += self.dialog

        # Issue switchover command
        con.active.spawn.sendline(command)
        try:
            self.result = dialog.process(con.active.spawn,
                           timeout=self.timeout,
                           prompt_recovery=self.prompt_recovery,
                           context=con.active.context)
        except SubCommandFailure as err:
            raise SubCommandFailure("Switchover Failed %s" % str(err))

        output = ""
        if self.result:
            self.result = self.get_service_result()
            output += self.result.match_output

        con.log.info('Switchover done, switching sessions')
        con.active.spawn.sendline()
        con.standby.spawn.sendline()
        con.connection_provider.prompt_recovery = True
        con.connection_provider.connect()
        con.connection_provider.prompt_recovery = False

        if sync_standby:
            con.log.info('Waiting for standby state')

            delta_time = timedelta(seconds=timeout)
            current_time = datetime.now()
            while (current_time - start_time) < delta_time:
                show_redundancy = con.execute('show redundancy', prompt_recovery=True)
                standby_state = re.findall(con.settings.STANDBY_STATE_REGEX, show_redundancy)
                standby_state = [s.strip() for s in standby_state]
                con.log.info('Standy state: %s' % standby_state)
                if standby_state == con.settings.STANDBY_EXPECTED_STATE:
                    break
                wait_time = con.settings.STANDBY_STATE_INTERVAL
                con.log.info('Waiting %s seconds' % wait_time)
                sleep(wait_time)
                current_time = datetime.now()

            if current_time - start_time > delta_time:
                raise SubCommandFailure('Switchover timed out, standby state: %s' % standby_state)

        # TODO: return all/most console output, not only from the switchover
        # This requires work on the bases.router.connection_provider BaseDualRpConnectionProvider implementation
        self.result = output


class AttachModuleConsole(BaseService):


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.start_state = "enable"
        self.end_state = "enable"

    def call_service(self, module_num, **kwargs):
        self.result = self.__class__.ContextMgr(connection = self.connection,
                                                module_num = module_num,
                                                **kwargs)

    class ContextMgr(object):
        def __init__(self, connection,
                           module_num,
                           login_name = 'root',
                           change_prompt = '#',
                           timeout = None):
            self.conn = connection
            self.module_num = module_num
            self.login_name = login_name
            self.change_prompt = change_prompt
            self.timeout = timeout or connection.settings.CONSOLE_TIMEOUT

        def __enter__(self):
            self.conn.log.debug('+++ attaching console +++')
            # attach to console
            self.conn.sendline('attach location %s' % self.module_num)
            try:
                match = self.conn.expect([r"export PS1=\'\#\'.*[\r\n]*\#"],
                                          timeout = self.timeout)
            except SubCommandFailure:
                pass

            return self

        def execute(self, command, timeout = None):
            # take default if not set
            timeout = timeout or self.timeout

            # send the command
            self.conn.sendline(command)

            # expect output until prompt again
            # wait for timeout provided by user
            out = self.conn.expect([r'(.+)[\r\n]*%s$' % self.change_prompt], timeout=timeout)
            raw = out.last_match.groups()[0].strip()

            # remove the echo back - best effort
            # (bash window uses a carriage return + space  to wrap over 80 char)
            if raw.split('\r\n')[0].replace(' \r', '').strip() == command:
                raw = '\r\n'.join(raw.split('\r\n')[1:])

            return raw


        def __exit__(self, exc_type, exc_value, exc_tb):
            self.conn.log.debug('--- detaching console ---')
            # disconnect console
            self.conn.sendline('') # clear last bad command

            # burn the buffer
            self.conn.expect([r'.+'], timeout = self.timeout)

            # get out
            self.conn.sendline('exit')
            self.conn.expect([r'(.+)%s\#' % self.conn.hostname], timeout = self.timeout)

            # do not suppress
            return False

        def __getattr__(self, attr):
            if attr in ('sendline', 'send'):
                return getattr(self.conn, attr)

            raise AttributeError('%s object has no attribute %s'
                                 % (self.__class__.__name__, attr))


class AdminAttachModuleConsole(AttachModuleConsole):


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.start_state = "admin"
        self.end_state = "enable"

    class ContextMgr(AttachModuleConsole.ContextMgr):

        def __init__(self, connection,
                           module_num,
                           login_name = 'root',
                           change_prompt = r'\~(.+)?\]\$',
                           timeout = None):
            self.conn = connection
            self.module_num = module_num
            self.login_name = login_name
            self.change_prompt = change_prompt
            self.timeout = timeout or connection.settings.CONSOLE_TIMEOUT

        def __enter__(self):
            self.conn.log.debug('+++ attaching console +++')

            sm = self.conn.state_machine
            sm.go_to('admin', self.conn.spawn)

            # attach to console
            self.conn.sendline('attach location %s' % self.module_num)
            try:
                match = self.conn.expect([r"%s" % self.change_prompt],
                                          timeout = self.timeout)
            except SubCommandFailure:
                pass

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not SubCommandFailure:
                # exit from attached location
                admin = self.conn.state_machine.get_state('admin')
                self.conn.sendline('exit')
                self.conn.expect(admin.pattern, timeout = self.timeout)
            return super().__exit__(exc_type, exc_val, exc_tb)


class AdminService(GenericBashService):

    class ContextMgr(GenericBashService.ContextMgr):

        def __enter__(self):
            self.conn.log.debug('+++ attaching admin shell +++')
            sm = self.conn.state_machine
            sm.go_to('admin', self.conn.spawn)
            return self


class BashService(GenericBashService):

    class ContextMgr(GenericBashService.ContextMgr):

        def __enter__(self):
            self.conn.log.debug('+++ attaching bash shell +++')
            sm = self.conn.state_machine
            sm.go_to('run', self.conn.spawn)
            return self

class AdminBashService(GenericBashService):

    class ContextMgr(GenericBashService.ContextMgr):

        def __enter__(self):
            self.conn.log.debug('+++ attaching bash shell +++')
            sm = self.conn.state_machine
            sm.go_to('admin_run', self.conn.spawn)
            return self


class GetRPState(GenericGetRPState):
    """ Get Rp state

    Service to get the redundancy state of the device rp.
    Returns standby rp state if standby is passed as input.

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
        self.start_state = 'any'
        self.end_state = 'any'

    def call_service(self,
                     target='active',
                     timeout=None,
                     utils=utils,
                     *args,
                     **kwargs):

        """send the command on the right rp and return the output"""
        return super().call_service(target=target, timeout=timeout, utils=utils, *args, **kwargs)


class Monitor(BaseService):

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.service_name = 'monitor'
        self.start_state = 'any'
        self.end_state = 'any'
        self.monitor_state = {}
        self.timeout = connection.settings.EXEC_TIMEOUT
        self.dialog = Dialog()
        self.log_buffer = io.StringIO()
        lb = UniconStreamHandler(self.log_buffer)
        lb.setFormatter(logging.Formatter(fmt='[%(asctime)s] %(message)s'))
        self.connection.log.addHandler(lb)

    @property
    def running(self):
        return self.connection.state_machine.current_state == 'monitor'

    def call_service(self, command, reply=Dialog(), timeout=None, **kwargs):
        conn = self.connection
        if not isinstance(command, str):
            raise ValueError('command must be a string')
        command = command.strip()
        timeout = timeout or self.timeout

        monitor_action = re.search('(?:mon\S* )?(?P<action>\S+)', command)
        if monitor_action:
            action = monitor_action.groupdict().get('action')
            if monitor_action in ['stop', 'quit']:
                return self.stop()

            if action != 'interface':
                # grab last 250 bytes
                monitor_output = self.get_buffer()[-250:]
                m = re.finditer(patterns.monitor_command_pattern, monitor_output)
                for item in m:
                    group = item.groupdict()
                    monitor_command = slugify(group.get('command'))
                    command_key = group.get('key')
                    if action == monitor_command:
                        conn.send(command_key)
                        return self._process_dialog(reply=reply, timeout=timeout)
                else:
                    raise SubCommandFailure(f'Monitor command {command} is not supported')

        if command:
            if not re.match('^mon', command):
                command = 'monitor ' + command

            # Clear log buffer
            self.log_buffer.seek(0)
            self.log_buffer.truncate()

            conn.sendline(command)
            return self._process_dialog(reply=reply, timeout=timeout)

    def _process_dialog(self, reply=None, timeout=None):
        conn = self.connection
        sm = conn.state_machine
        dialog = self.dialog + self.service_dialog()
        for state in sm.states:
            if state.name != sm.current_state:
                dialog.append(Statement(pattern=state.pattern))

        try:
            dialog_match = dialog.process(
                conn.spawn,
                timeout=timeout,
                prompt_recovery=self.prompt_recovery,
                context=conn.context
            )
            if dialog_match:
                self.result = utils.remove_ansi_escape_codes(dialog_match.match_output)
                self.result = self.get_service_result()
            sm.detect_state(conn.spawn, conn.context)
        except StateMachineError:
            raise
        except Exception as err:
            raise SubCommandFailure("Command execution failed", err) from err

        m = re.search(patterns.monitor_time_regex, self.result)
        if m:
            for k, v in m.groupdict().items():
                self.monitor_state[k] = v

        return self.result

    def get_buffer(self, truncate=False):
        """
        Return log buffer contents and clear log buffer if truncate is true
        """
        self.log_buffer.seek(0)
        output = self.log_buffer.read()
        if truncate:
            self.log_buffer.seek(0)
            self.log_buffer.truncate()
        return output

    def tail(self, timeout=30, reply=None):
        """
        Monitor the 'monitor' output up to 'timeout' seconds or if a reply statement matches.

        :Parameters:
            :param timeout: (int) Timeout in seconds. Default: 30
            :param reply: (Dialog) reply dialog (optional)

        :Returns:
            Returns the current buffer contents.
        """
        conn = self.connection

        dialog = Dialog()
        if reply:
            dialog += reply
        try:
            dialog.process(conn.spawn, timeout=timeout, context=self.context)
        except TimeoutError:
            pass

        return self.get_buffer()

    def stop(self):
        """ Stop the monitor session and return to enable mode.
        """
        conn = self.connection

        if not self.running:
            conn.log.info('Monitor not running')
            return

        # Grab output before stoppig monitor
        output = self.get_buffer(truncate=True)
        output = utils.remove_ansi_escape_codes(output)

        conn.log.info('Stopping monitor...')
        conn.state_machine.go_to('enable', conn.spawn)
        return output

    def log_service_call(self):
        pass

    def post_service(self, *args, **kwargs):
        pass
