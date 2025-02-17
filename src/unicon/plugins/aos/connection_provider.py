'''
Author: Alex Pfeil
Contact: www.linkedin.com/in/alex-p-352040a0
Contents largely inspired by sample Unicon repo, Knox Hutchinson and Cisco:
https://github.com/CiscoDevNet/pyats-plugin-examples/tree/master/unicon_plugin_example/src/unicon_plugin_example
'''
import time

from unicon.bases.routers.connection_provider import \
    BaseSingleRpConnectionProvider
from unicon.eal.dialogs import Dialog
from unicon.plugins.aos.statements import (aosConnection_statement_list)
from unicon.plugins.generic.statements import custom_auth_statements
import getpass

#This is the aos Connection Provider It is called in the __init__.py file.
class aosSingleRpConnectionProvider(BaseSingleRpConnectionProvider):
    """ Implements Junos singleRP Connection Provider,
        This class overrides the base class with the
        additional dialogs and steps required for
        connecting to any device via generic implementation
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

#This funciton must be member of aosSingleRpConnectionProvider    
    def get_connection_dialog(self):
        con = self.connection
        custom_auth_stmt = custom_auth_statements(
                             self.connection.settings.LOGIN_PROMPT,
                             self.connection.settings.PASSWORD_PROMPT)
        return con.connect_reply + \
                    Dialog(custom_auth_stmt + aosConnection_statement_list
                        if custom_auth_stmt else aosConnection_statement_list)
    
    def set_init_commands(self):
        con = self.connection
        if con.init_exec_commands is not None:
            self.init_exec_commands = con.init_exec_commands
            self.init_config_commands = con.init_exec_commands
        else:
            self.init_exec_commands = [
                                        'terminal length 1000',
                                        'terminal width 1000']
            self.init_config_commands = []