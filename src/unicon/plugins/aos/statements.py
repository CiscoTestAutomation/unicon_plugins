'''
Author: Alex Pfeil
Contact: www.linkedin.com/in/alex-p-352040a0
Contents largely inspired by sample Unicon repo and Knox Hutchinson and Cisco Development Team:
https://github.com/CiscoDevNet/pyats-plugin-examples/tree/master/unicon_plugin_example/src/unicon_plugin_example
'''

from unicon.eal.dialogs import Statement
from unicon.plugins.aos.patterns import aosPatterns
from unicon.plugins.generic.statements import password_handler
from unicon.plugins.generic.statements import login_handler
import time
from unicon.plugins.utils import (
    get_current_credential,
    common_cred_username_handler
)
import getpass
patterns = aosPatterns()

def escape_char_handler(spawn):
    """ handles telnet login messages
    """
    # Wait a small amount of time for any chatter to cease from the
    # device before attempting to call sendline.
    time.sleep(.2)

def run_level(spawn):
    time.sleep(1)

def continue_connecting(spawn):
    """ handles SSH new key prompt
    """
    time.sleep(0.5)
    print("I saw the ssh key configuration")
    spawn.sendline('yes')
def ssh_continue_connecting(spawn):
    """ handles SSH new key prompt
    """
    time.sleep(0.5)
    print("I saw the ssh key configuration")
    spawn.sendline('yes')


def wait_and_enter(spawn):
    # wait for 0.5 second and read the buffer
    # this avoids issues where the 'sendline'
    # is somehow lost
    time.sleep(.5)
    spawn.sendline()

def send_password(spawn, password):
    spawn.sendline(password)
    print("***This is where I printed the " + password + "***")

def complete_login(spawn):
    spawn.sendline()

def login_handler(spawn, context, session):
    """ handles login prompt
    """
    credential = get_current_credential(context=context, session=session)
    if credential:
        common_cred_username_handler(
            spawn=spawn, context=context, credential=credential)
    else:
        spawn.sendline(context['username'])
        session['tacacs_login'] = 1
'''
Example:

    dialog = Dialog([
        Statement(pattern=r"^username:$",
                  action=lambda spawn: spawn.sendline("admin"),
                  args=None,
                  loop_continue=True,
                  continue_timer=False ),
        Statement(pattern=r"^password:$",
                  action=lambda spawn: spawn.sendline("admin"),
                  args=None,
                  loop_continue=True,
                  continue_timer=False ),
        Statement(pattern=r"^host-prompt#$",
                  action=None,
                  args=None,
                  loop_continue=False,
                  continue_timer=False ),
    ])

    It is also possible to construct a dialog instance by supplying list of
    statement arguments.

    dialog = Dialog([
        [r"^username$", lambda spawn: spawn.sendline("admin"), None, True, False],
        [r"^password:$", lambda spawn: spawn.sendline("admin"), None, True, False],
        [r"^hostname#$", None, None, False, False]
    ])
'''

class aosStatements(object):
    
    def __init__(self):
# This is the statements to login to AOS.
        self.start_stmt = Statement(pattern=patterns.start,
                                    action=run_level,
                                    args=None,
                                    loop_continue=True,
                                    continue_timer=True,
                                    trim_buffer=True,
                                    debug_statement=True)
        self.login_stmt = Statement(pattern=patterns.login_prompt,
                                    action=login_handler,
                                    args=None,
                                    loop_continue=True,
                                    continue_timer=True,
                                    trim_buffer=True,
                                    debug_statement=True)
        self.password_stmt = Statement(pattern=patterns.password_prompt,
                                       action=password_handler,
                                       args=None,
                                       loop_continue=True,
                                       continue_timer=True,
                                       trim_buffer=True,
                                       debug_statement=True)
        self.ssh_key_check = Statement(pattern=patterns.ssh_key_check,
                                    action=ssh_continue_connecting,
                                    args=None,
                                    loop_continue=True,
                                    continue_timer=True,
                                    trim_buffer=True,
                                    debug_statement=True)
        self.continue_connecting_stmt = Statement(pattern=patterns.continue_connecting,
                                    action=continue_connecting,
                                    args=None,
                                    loop_continue=True,
                                    continue_timer=True,
                                    trim_buffer=True,
                                    debug_statement=True)
        self.press_any_key_stmt = Statement(pattern=patterns.press_any_key,
                                            action=wait_and_enter,
                                            args=None,
                                            loop_continue=True,
                                            continue_timer=True,
                                            trim_buffer=True,
                                            debug_statement=True)
        self.press_return_stmt = Statement(pattern=patterns.executive_prompt,
                                            action='sendline(exit)',
                                            args=None,
                                            loop_continue=True,
                                            continue_timer=True,
                                            trim_buffer=True,
                                            debug_statement=True)

#############################################################
#  Statement lists
#############################################################

aos_statements = aosStatements()

#############################################################
# Authentication Statements
#############################################################

aosAuthentication_statement_list = [aos_statements.start_stmt,
                                    aos_statements.login_stmt,
                                    aos_statements.password_stmt,
                                    aos_statements.press_any_key_stmt,
                                    aos_statements.ssh_key_check,
                                    aos_statements.press_return_stmt,
                                    aos_statements.continue_connecting_stmt]

aosConnection_statement_list = aosAuthentication_statement_list