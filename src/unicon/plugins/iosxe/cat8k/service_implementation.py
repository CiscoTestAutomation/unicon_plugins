__author__ = "Lukas McClelland <lumcclel@cisco.com>"

import io
import re
import logging
from time import sleep

from unicon.eal.dialogs import Dialog
from unicon.core.errors import SubCommandFailure
from unicon.bases.routers.services import BaseService
from unicon.logs import UniconStreamHandler, UNICON_LOG_FORMAT
from unicon.plugins.generic.service_implementation import SwitchoverResult
from unicon.plugins.iosxe.cat8k.service_statements import switchover_statement_list


class SwitchoverService(BaseService):
    """ Service to switchover the device.

    Arguments:
        command: command to do switchover. default
                 "redundancy force-switchover"
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
            rtr.switchover(command="command to invoke switchover",timeout=700)
    """

    def __init__(self, connection, context, **kwargs):
        super().__init__(connection, context, **kwargs)
        self.start_state = 'enable'
        self.end_state = 'enable'
        self.timeout = connection.settings.SWITCHOVER_TIMEOUT
        self.dialog = Dialog(switchover_statement_list)
        self.command = 'redundancy force-switchover'
        self.log_buffer = io.StringIO()
        lb = UniconStreamHandler(self.log_buffer)
        lb.setFormatter(logging.Formatter(fmt=UNICON_LOG_FORMAT))
        self.connection.log.addHandler(lb)
        self.__dict__.update(kwargs)

    def call_service(self, command=None,
                     reply=Dialog([]),
                     timeout=None,
                     sync_standby=True,
                     return_output=False,
                     *args,
                     **kwargs):

        # create an alias for connection.
        con = self.connection
        timeout = timeout or self.timeout
        command = command or self.command

        if not isinstance(reply, Dialog):
            raise SubCommandFailure(
                "dialog passed via 'reply' must be an instance of Dialog")

        reply += self.dialog

        # Clear log buffer
        self.log_buffer.seek(0)
        self.log_buffer.truncate()

        con.log.debug("+++ Issuing switchover on  %s  with "
                      "switchover_command %s and timeout is %s +++"
                      % (con.hostname, command, timeout))

        # Check if switchover is possible by checking if "IOSXE_DUAL_IOS = 1" is
        # in the output of 'sh romvar'
        output = con.execute('show romvar')
        if not re.search('IOSXE_DUAL_IOS\s*=\s*1', output):
            raise SubCommandFailure(
                "Switchover can't be issued if IOSXE_DUAL_IOS is not activated")


        # Issue switchover command
        con.spawn.sendline(command)
        try:
            reply.process(con.spawn,
                           timeout=timeout,
                           prompt_recovery=self.prompt_recovery,
                           context=self.context)
        except TimeoutError:
            pass
        except SubCommandFailure as err:
            raise SubCommandFailure("Switchover Failed %s" % str(err)) from err

        con.log.info(f'Waiting {con.settings.POST_SWITCHOVER_WAIT} seconds')
        sleep(con.settings.POST_SWITCHOVER_WAIT)

        con.state_machine.go_to(
            'any',
            con.spawn,
            prompt_recovery=self.prompt_recovery,
            timeout=con.connection_timeout,
            context=self.context
        )
        con.state_machine.go_to(
            'enable',
            con.spawn,
            prompt_recovery=self.prompt_recovery,
            context=self.context
        )
        self.result = True

        if not sync_standby:
            con.log.info("Standby state check disabled on user request")
        else:
            con.log.info('Waiting for standby sync to finish')
            standby_wait_time = con.settings.POST_HA_RELOAD_CONFIG_SYNC_WAIT
            switchover_intervals = con.settings.SWITCHOVER_COUNTER
            sleep_per_interval = standby_wait_time // switchover_intervals + 1
            for interval in range(switchover_intervals):
                try:
                    output = con.execute('show platform')
                except (SubCommandFailure, TimeoutError):
                    self.result = False
                    con.log.info(
                        "Encountered subcommand failure while trying to "
                        "execute 'show platform'. Waiting for %s seconds"
                        % sleep_per_interval)
                    sleep(sleep_per_interval)
                    continue
                else:
                    if not re.search('R\d+/\d+\s+init,\s*standby.*', output):
                        break
                    elif interval * sleep_per_interval < standby_wait_time:
                        con.log.info(
                            'Standby still initializing. Waiting for %s seconds'
                            % sleep_per_interval)
                        sleep(sleep_per_interval)

                if interval * sleep_per_interval >= standby_wait_time:
                    con.log.error(
                            'Standby failed to complete initialization within '
                            '{} seconds'.format(standby_wait_time))
                    self.result = False

        self.log_buffer.seek(0)
        switchover_output = self.log_buffer.read()
        # clear buffer
        self.log_buffer.truncate()

        if return_output:
            self.result = SwitchoverResult(
                result=self.result,
                output=switchover_output)
