from time import sleep

from unicon.plugins.iosxe.connection_provider import IosxeSingleRpConnectionProvider


class VpagentSingleRpConnectionProvider(IosxeSingleRpConnectionProvider):
    """ Implements Vpagent singleRP Connection Provider,
        This class overrides the base class with the
        additional dialogs and steps required for
        connecting to any device via generic implementation
    """

    def __init__(self, *args, **kwargs):

        """ Initializes the generic connection provider
        """
        super().__init__(*args, **kwargs)


    def establish_connection(self):
        """ Reads the device state and brings it to the right state
        Note: Passive hostname learning is enabled by default and will
        give a warning if the device hostname does not match the learned
        hostname. The learned hostname is only used if user specifies
        `learn_hostname=True`. A timeout may occur if the prompt pattern
        uses the hostname, the timeout error includes the hostname and
        a hint to check the hostname if a mismatch was detected.
        """
        con = self.connection

        # Enable hostname learning by default
        con.state_machine.learn_hostname = True
        con.state_machine.learn_pattern = con.settings.DEFAULT_LEARNED_HOSTNAME

        context = self.connection.context
        if (login_creds := context.get('login_creds')):
            context.update(cred_list=login_creds)

        # Before accessing the vm since device is not ready and connection may be 
        # closed by vcenter manger we need to wait before accessing the device.
        timeout = con.settings.WAITE_TIMEOUT 
        con.log.info(f'sleeping for {timeout} seconds before accessing the device!')
        sleep(timeout)

        dialog  = self.get_connection_dialog()
        # Try to bring device to any state connection may be closed during bring the device
        # to a valid and cause an IO error 
        output = self._get_device_to_any(con, context, dialog)
        # if device is still in generic state that means we could not bring device to any state and 
        # spawn is closed so we need to create a new spawn and try again to bring device to any state
        if con.state_machine.current_state == 'generic':
            con.setup_connection()
            output = self._get_device_to_any(con, context, dialog)

        if con.state_machine.current_state == "config":
            con.state_machine.go_to('enable',
                                    self.connection.spawn,
                                    context=context,
                                    prompt_recovery=self.prompt_recovery,
                                    timeout=self.connection.connection_timeout)

        if con.state_machine.current_state not in ['rommon', 'standby_locked', 'shell']:
            cur_state = con.state_machine.get_state(con.state_machine.current_state)
            # if the learn hostname is set to True the pattern for state machine updated with
            # '(?P<hostname00...)' regex patterns so we check for the pattern before learning the hostname
            if 'P<hostname' in cur_state.pattern:
                self.learn_hostname()
            # If device is found in one of the above states, init_handle()
            # will change the device state to enable, after which
            # hostname learning and token discovery is done.
            self.learn_tokens()

        con.state_machine.learn_hostname = False
        context.pop('cred_list', None)

        return output

    def _get_device_to_any(self, connection, context, dialog):
        try:       
            connection.state_machine.go_to('any',
                                            self.connection.spawn,
                                            context=context,
                                            prompt_recovery=self.prompt_recovery,
                                            timeout=self.connection.connection_timeout,
                                            dialog=dialog)
        except Exception:
            connection.setup_connection()
            self._get_device_to_any(connection, context, dialog)