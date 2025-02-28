"""
Module:
    unicon.plugins.generic

Authors:
    pyATS TEAM (pyats-support@cisco.com, pyats-support-ext@cisco.com)

Description:
    Module for defining all the Statements and callback required for the
    Current implementation
"""
import re
from time import sleep
from datetime import datetime, timedelta
from unicon.eal.dialogs import Statement
from unicon.eal.helpers import sendline
from unicon.core.errors import UniconAuthenticationError
from unicon.core.errors import CredentialsExhaustedError
from unicon.core.errors import ConnectionError as UniconConnectionError
from unicon.utils import Utils

from unicon.plugins.generic.patterns import GenericPatterns
from unicon.plugins.utils import (
    get_current_credential,
    _get_creds_to_try,
    common_cred_username_handler,
    common_cred_password_handler,
)

from unicon.utils import to_plaintext
from unicon.bases.routers.connection import ENABLE_CRED_NAME

pat = GenericPatterns()
utils = Utils()


#############################################################
#  Callbacks
#############################################################

def terminal_position_handler(spawn, session, context):
    """ send terminal position (VT100) """
    spawn.send('\x1b[0;200R')


def connection_refused_handler(spawn, context):
    """ handles connection refused scenarios
    """
    context.setdefault('connection_refused_count', 0)
    context['connection_refused_count'] += 1
    if context.get('connection_refused_count') < spawn.settings.CONNECTION_REFUSED_MAX_COUNT:
        if spawn.device:
            spawn.device.api.execute_clear_line()
            spawn.device.connect()
            return
    raise Exception('Connection refused to device %s' % (str(spawn)))


def connection_failure_handler(spawn):
    raise Exception('received disconnect from router %s' % (str(spawn)))

def permission_denied_handler(spawn):
    raise UniconConnectionError(
        'Permission denied for device "%s"' % (str(spawn)))

def syslog_stripper(spawn):
    """Strip syslog from spawn buffer"""
    spawn.buffer = re.sub(pat.syslog_message_pattern, '', spawn.buffer, flags=re.M).strip()


def buffer_wait(spawn, wait_time):
    ''' Keep reading the buffer until wait_time.

    Args:
        wait_time (float): wait time in seconds
    Returns:
        None
    '''
    time_wait = timedelta(seconds=wait_time)
    start_time = current_time = datetime.now()
    while (current_time - start_time) < time_wait:
        spawn.read_update_buffer()
        current_time = datetime.now()


def buffer_settled(spawn, wait_time):
    """Wait up to wait_time for the buffer to settle.

    Args:
        wait_time (float): wait time in seconds
    Returns:
        True/False

    If the buffer is growing, return False immediately,
    if the buffer did not grow during wait_time,
    return True.
    """
    wait_time = timedelta(seconds=wait_time)
    start_time = current_time = datetime.now()
    prev_buf_len = len(spawn.buffer)
    while (current_time - start_time) < wait_time:
        spawn.read_update_buffer()
        cur_buf_len = len(spawn.buffer)

        if cur_buf_len > prev_buf_len:
            return False

        current_time = datetime.now()
    return True


def syslog_wait_send_return(spawn, session):
    """Handle syslog messages observed in the buffer.

    If a syslog messsage was seen, this handler is executed.
    Read the buffer, if its growing, return.

    If the buffer is not growing, read updates up to SYSLOG_WAIT
    and check if in that period the buffer stayed the same.
    If so, the last message was a syslog message and we want
    to send a return to get back the prompt. A return is sent
    and the length of the buffer is stored, another return
    is sent only if the buffer size changed the next time
    this handler is called (i.e. another syslog message was received).
    """
    buffer_len = session.get('buffer_len', 0)
    if len(spawn.buffer) == buffer_len:
        if not session.get('syslog_sent_cr', False) and \
                buffer_settled(spawn, spawn.settings.SYSLOG_WAIT):
            spawn.sendline()
            session['syslog_sent_cr'] = True
    else:
        session['syslog_sent_cr'] = False
    session['buffer_len'] = len(spawn.buffer)


def chatty_term_wait(spawn, trim_buffer=False, wait_time=None):
    """ Wait some time for any chatter to cease from the device.
    """
    chatty_wait_time = wait_time or spawn.settings.ESCAPE_CHAR_CHATTY_TERM_WAIT
    for retry_number in range(spawn.settings.ESCAPE_CHAR_CHATTY_TERM_WAIT_RETRIES):

        if buffer_settled(spawn, chatty_wait_time):
            break
        else:
            buffer_wait(spawn, chatty_wait_time * (retry_number + 1))

    else:
        spawn.log.warning('The buffer has not settled because the device is chatty. '
                          'You can try adjusting ESCAPE_CHAR_CHATTY_TERM_WAIT and '
                          'ESCAPE_CHAR_CHATTY_TERM_WAIT_RETRIES')

    if trim_buffer:
        spawn.trim_buffer()


def escape_char_callback(spawn):
    """ Wait some time for terminal chatter to cease before attempting to obtain prompt,
    do not attempt to obtain prompt if login message is seen.
    """

    chatty_term_wait(spawn)

    # get from settings or fallback to default
    escape_char_prompt = getattr(spawn.settings, 'ESCAPE_CHAR_PROMPT_PATTERN',
        r'.*(User Access Verification|sername:\s*$|assword:\s*$|login:\s*$)')
    # Device is already showing some kind of prompt
    if re.search(escape_char_prompt, spawn.buffer):
        return

    auth_pat = ''
    if spawn.settings.LOGIN_PROMPT:
        auth_pat = spawn.settings.LOGIN_PROMPT
    if spawn.settings.PASSWORD_PROMPT:
        if auth_pat:
            auth_pat += '|' + spawn.settings.PASSWORD_PROMPT
        else:
            auth_pat = spawn.settings.PASSWORD_PROMPT

    if auth_pat and re.search(auth_pat, spawn.buffer):
        return

    # try and get to the first prompt
    # best effort handling of network delays and connection establishing

    # store current know buffer
    known_buffer = len(spawn.buffer.strip())

    for retry_number in range(spawn.settings.ESCAPE_CHAR_PROMPT_WAIT_RETRIES):
        # hit enter
        spawn.sendline()

        # incremental wait logic
        buffer_wait(spawn, spawn.settings.ESCAPE_CHAR_PROMPT_WAIT * (retry_number + 1))

        # check buffer
        if known_buffer != len(spawn.buffer.strip()):
            # we got new stuff - assume it's the the prompt, get out
            break

    else:
        spawn.log.warning('Device is not responding, it might be slow. '
                          'You can try adjusting the ESCAPE_CHAR_PROMPT_WAIT and '
                          'ESCAPE_CHAR_PROMPT_WAIT_RETRIES settings.')


def ssh_continue_connecting(spawn):
    """ handles SSH new key prompt
    """
    sleep(0.1)
    spawn.sendline('yes')


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


def user_access_verification(session):
    # Enable the tacacs_login flag
    session['tacacs_login'] = 1


def get_enable_credential_password(context):
    """ Get the enable password from the credentials.

    1. If there is a previous credential (the last credential used to respond to
       a password prompt), use its enable_password member if it exists.
    2. Otherwise, if the user specified a list of credentials, pick the final one in the list and
       use its enable_password member if it exists.
    3. Otherwise, if there is a default credential, use its enable_password member if it exists.
    4. Otherwise, use the well known "enable" credential, password member if it exists.
    5. Otherwise, use the default credential "password" member if it exists.
    6. Otherwise, raise error that no enable password could be found.

    """
    credentials = context.get('credentials')
    enable_credential_password = ""
    login_creds = context.get('login_creds', [])
    fallback_cred = context.get('default_cred_name', "")
    if not login_creds:
        login_creds = [fallback_cred]
    if not isinstance(login_creds, list):
        login_creds = [login_creds]

    # Pick the last item in the login_creds list to select the intended
    # credential even if the device does not ask for a password on login
    # and the given credential is not consumed.
    final_credential = login_creds[-1] if login_creds else ""
    if credentials:
        enable_pw_checks = [
            (context.get('previous_credential', ""), 'enable_password'),
            (final_credential, 'enable_password'),
            (fallback_cred, 'enable_password'),
            (ENABLE_CRED_NAME, 'password'),
            (context.get('default_cred_name', ""), 'password'),
        ]
        for cred_name, key in enable_pw_checks:
            if cred_name:
                candidate_enable_pw = credentials.get(cred_name, {}).get(key)
                if candidate_enable_pw is not None:
                    enable_credential_password = candidate_enable_pw
                    break
        else:
            raise UniconAuthenticationError('{}: Could not find an enable credential.'.
                                            format(context.get('hostname', "")))
    return to_plaintext(enable_credential_password)


def enable_password_handler(spawn, context, session):
    if 'password_attempts' not in session:
        session['password_attempts'] = 1
    else:
        session['password_attempts'] += 1
    if session.password_attempts > spawn.settings.PASSWORD_ATTEMPTS:
        raise UniconAuthenticationError('Too many enable password retries')

    enable_credential_password = get_enable_credential_password(context=context)
    if enable_credential_password:
        spawn.sendline(enable_credential_password)
    else:
        spawn.sendline(context['enable_password'])

def set_new_password(spawn, context, session):
    '''setting up the new password on the device.

        For setting up the password we need to do these 2 steps
        to make sure we don't get CredentialsExhaustedError:
            1- remove the current_credential(this is the last credential used for login into device)
               from session.
            2- remove the cred_iter(an iterable of login credentials) from session.
        after removing these 2 we reset credentials and we could use the default password from the default credentials
        for setting up the password on the device.
    '''
    # remove the current credential from session
    if session.get('current_credential'):
        session.pop('current_credential')
    # remove the cred_iter from session
    if session.get('cred_iter'):
        session.pop('cred_iter')
    # calling the password handler for sending the passowrd.
    password_handler(spawn, context, session )


def enable_secret_handler(spawn, context, session):
    if 'password_attempts' not in session:
        session['password_attempts'] = 1
    else:
        session['password_attempts'] += 1
    if session.password_attempts > spawn.settings.PASSWORD_ATTEMPTS:
        raise UniconAuthenticationError('Too many enable password retries')

    enable_credential_password = get_enable_credential_password(context=context)
    if enable_credential_password and len(enable_credential_password) >= \
            spawn.settings.ENABLE_SECRET_MIN_LENGTH:
        spawn.sendline(enable_credential_password)
    else:
        spawn.log.warning('Using enable secret from TEMP_ENABLE_SECRET setting')
        enable_secret = spawn.settings.TEMP_ENABLE_SECRET
        context['setup_selection'] = 0
        spawn.sendline(enable_secret)


def setup_enter_selection(spawn, context):
    selection = context.get('setup_selection')
    if selection is not None:
        if str(selection) == '0':
            spawn.log.warning('Not saving setup configuration')
        spawn.sendline(f'{selection}')
    else:
        spawn.sendline('2')


def ssh_tacacs_handler(spawn, context):
    result = False
    start_cmd = spawn.spawn_command
    if context.get('username'):
        if re.search(context['username'] + r'@', start_cmd) \
            or re.search(r'-l\s*' + context['username'], start_cmd) \
                or re.search(context['username'] + r'@', spawn.buffer):
            result = True
    return result


def password_handler(spawn, context, session):
    """ handles password prompt
    """
    if 'enable' in spawn.last_sent:
        return enable_password_handler(spawn, context, session)

    credential = get_current_credential(context=context, session=session)
    if credential:
        common_cred_password_handler(
            spawn=spawn, context=context, credential=credential,
            session=session)
    else:
        if 'password_attempts' not in session:
            session['password_attempts'] = 1
        else:
            session['password_attempts'] += 1
        if session.password_attempts > spawn.settings.PASSWORD_ATTEMPTS:
            raise UniconAuthenticationError('Too many password retries')

        if context.get('username', '') == spawn.last_sent.rstrip() or ssh_tacacs_handler(spawn, context):
            if (tacacs_password := context.get('tacacs_password')):
                spawn.sendline(tacacs_password)
            elif context.get('password'):
                spawn.sendline(context['password'])
        else:
            spawn.sendline(context['line_password'])

    cred_actions = context.get('cred_action', {}).get(credential, {})
    if cred_actions:
        post_action = cred_actions.get('post', '')
        action = re.match(r'(send|sendline)\((.*)\)', post_action)
        if action:
            method = action.group(1)
            args = action.group(2)
            spawn.log.info('Executing post credential command: {}'.format(post_action))
            getattr(spawn, method)(args)
    elif credential and getattr(spawn.settings, 'SENDLINE_AFTER_CRED', None) == credential:
        spawn.log.info("Sending return after credential '{}'".format(credential))
        spawn.sendline()


def passphrase_handler(spawn, context, session):
    """ Handles SSH passphrase prompt """
    credential = get_current_credential(context=context, session=session)
    try:
        spawn.sendline(to_plaintext(
            context['credentials'][credential]['passphrase']))
    except KeyError:
        raise UniconAuthenticationError("No passphrase found "
                                        "for credential {}.".format(credential))


def bad_password_handler(spawn, context, session):
    """ handles bad password prompt
    """
    # check if there is a fallback credential
    if context['fallback_creds']:
        spawn.log.info('Using fallback credentials for logging in to the device!')
        # Update the session with fallback credentials
        if not session.get('fallback_creds'):
            session['fallback_creds'] = iter(context['fallback_creds'])
            # this list keep track of the fallback credentials being used
            session['cred_list'] = []
        try:
            # update the current credential with the next fallback credential
            session['current_credential'] = next(session['fallback_creds'])
            spawn.log.info(f"Using {session['current_credential']} from fallback credential list.")
            # update the list of fallback credentials
            session['cred_list'].append(session['current_credential'])
        except StopIteration:
            raise CredentialsExhaustedError(
                creds_tried= _get_creds_to_try(context) + (session['cred_list']))
    else:
        raise UniconAuthenticationError('Bad Password sent to device %s' % (str(spawn),))


def incorrect_login_handler(spawn, context, session):
    # In nxos device if the first attempt password prompt occur before
    # username prompt, it will get Login incorrect error.
    # Reset the cred_iter to try again
    if 'incorrect_login_attempts' not in session:
        session.pop('cred_iter', None)

    credential = get_current_credential(context=context, session=session)
    if credential and 'incorrect_login_attempts' in session:
        # If credentials have been supplied, there are no login retries.
        # The user must supply appropriate credentials to ensure login
        # does not fail. Skip it for the first attempt
        raise UniconAuthenticationError(
            'Login failure, either wrong username or password')
    if 'incorrect_login_attempts' not in session:
        session['incorrect_login_attempts'] = 1

    # Let's give a chance for unicon to login with right credentials
    # let's give three attempts
    if session['incorrect_login_attempts'] <= 3:
        session['incorrect_login_attempts'] = \
            session['incorrect_login_attempts'] + 1
    else:
        raise UniconAuthenticationError(
            'Login failure, either wrong username or password')


def sudo_password_handler(spawn, context, session):
    """ Password handler for sudo command
    """
    if 'sudo_attempts' not in session:
        session['sudo_attempts'] = 1
    else:
        raise UniconAuthenticationError('sudo failure')

    credentials = context.get('credentials')
    if credentials:
        try:
            spawn.sendline(
                to_plaintext(credentials['sudo']['password']))
        except KeyError:
            raise UniconAuthenticationError("No password has been defined "
                                            "for sudo credential.")
    else:
        raise UniconAuthenticationError("No credentials has been defined for sudo.")


def wait_and_enter(spawn, wait=0.5):
    # wait and read the buffer
    # this avoids issues where the 'sendline'
    # is somehow lost
    wait_time = timedelta(seconds=wait)
    settle_time = current_time = datetime.now()
    while (current_time - settle_time) < wait_time:
        spawn.read_update_buffer()
        current_time = datetime.now()
    spawn.sendline()


def more_prompt_handler(spawn):
    output = utils.remove_backspace(spawn.match.match_output)
    all_more = re.findall(spawn.settings.MORE_REPLACE_PATTERN, output)
    if all_more:
        spawn.match.match_output = ''.join(output.rsplit(all_more[-1], 1))
        spawn.buffer = ''.join(spawn.buffer.rsplit(all_more[-1], 1))
    else:
        spawn.match.match_output = output
        spawn.buffer = utils.remove_backspace(spawn.buffer)
    spawn.send(spawn.settings.MORE_CONTINUE)


def custom_auth_statements(login_pattern=None, password_pattern=None):
    """ Return list of Statements based on login_pattern and password_prompt."""
    stmt_list = []
    if login_pattern:
        login_stmt = Statement(pattern=login_pattern,
                               action=login_handler,
                               args=None,
                               loop_continue=True,
                               continue_timer=False)
        stmt_list.append(login_stmt)
    if password_pattern:
        password_stmt = Statement(pattern=password_pattern,
                                  action=password_handler,
                                  args=None,
                                  loop_continue=True,
                                  continue_timer=False)
        stmt_list.append(password_stmt)
    if stmt_list:
        return stmt_list


def update_context(spawn, context, session, **kwargs):
    context.update(kwargs)


def boot_timeout_handler(spawn, context, session):
    '''Special handler for dialog timeouts that occur during boot.
    Based on start_boot_time set in the rommon->disable
    transition handler, determine if boot is taking too
    long and raise an exception.
    '''
    boot_timeout_time = timedelta(seconds=spawn.settings.BOOT_TIMEOUT)
    boot_start_time = context.get('boot_start_time')
    if boot_start_time:
        current_time = datetime.now()
        delta_time = current_time - boot_start_time
        if delta_time > boot_timeout_time:
            context.pop('boot_start_time', None)
            raise TimeoutError('Boot timeout')
        return True
    else:
        return False


boot_timeout_stmt = Statement(
    pattern='__timeout__',
    action=boot_timeout_handler,
    args=None,
    loop_continue=True,
    continue_timer=False)



#############################################################
#  Generic statements
#############################################################

class GenericStatements():
    """
        Class that defines All the Statements for Generic platform
        implementation
    """

    def __init__(self):
        '''
         All generic Statements
        '''
        self.escape_char_stmt = Statement(pattern=pat.escape_char,
                                          action=escape_char_callback,
                                          args=None,
                                          loop_continue=True,
                                          continue_timer=False)
        self.press_return_stmt = Statement(pattern=pat.press_return,
                                           action=wait_and_enter, args=None,
                                           loop_continue=True,
                                           continue_timer=False)
        self.connection_refused_stmt = \
            Statement(pattern=pat.connection_refused,
                      action=connection_refused_handler,
                      args=None,
                      loop_continue=False,
                      continue_timer=False)

        self.bad_password_stmt = Statement(pattern=pat.bad_passwords,
                                           action=bad_password_handler,
                                           args=None,
                                           loop_continue=True,
                                           continue_timer=False)

        self.login_incorrect = Statement(pattern=pat.login_incorrect,
                                         action=incorrect_login_handler,
                                         args=None,
                                         loop_continue=True,
                                         continue_timer=False)

        self.disconnect_error_stmt = Statement(pattern=pat.disconnect_message,
                                               action=connection_failure_handler,
                                               args=None,
                                               loop_continue=False,
                                               continue_timer=False)
        self.login_stmt = Statement(pattern=pat.username,
                                    action=login_handler,
                                    args=None,
                                    loop_continue=True,
                                    continue_timer=False)
        self.useraccess_stmt = Statement(pattern=pat.useracess,
                                         action=user_access_verification,
                                         args=None,
                                         loop_continue=True,
                                         continue_timer=False)
        self.password_stmt = Statement(pattern=pat.password,
                                       action=password_handler,
                                       args=None,
                                       loop_continue=True,
                                       continue_timer=False)
        self.new_password_stmt = Statement(pattern=pat.new_password,
                                           action=set_new_password,
                                           args=None,
                                           loop_continue=True,
                                           continue_timer=False)
        self.enable_password_stmt = Statement(pattern=pat.enable_password,
                                              action=enable_password_handler,
                                              args=None,
                                              loop_continue=True,
                                              continue_timer=False)
        self.enable_secret_stmt = Statement(pattern=pat.enable_secret,
                                            action=enable_secret_handler,
                                            args=None,
                                            loop_continue=True,
                                            continue_timer=False)
        self.password_ok_stmt = Statement(pattern=pat.password_ok,
                                          action=sendline,
                                          args=None,
                                          loop_continue=True,
                                          continue_timer=False)
        self.more_prompt_stmt = Statement(pattern=pat.more_prompt,
                                          action=more_prompt_handler,
                                          args=None,
                                          loop_continue=True,
                                          continue_timer=False,
                                          trim_buffer=False)
        self.confirm_prompt_stmt = Statement(pattern=pat.confirm_prompt,
                                             action=sendline,
                                             args=None,
                                             loop_continue=True,
                                             continue_timer=False)
        self.confirm_prompt_y_n_stmt = Statement(pattern=pat.confirm_prompt_y_n,
                                                 action='sendline(y)',
                                                 args=None,
                                                 loop_continue=True,
                                                 continue_timer=False)
        self.yes_no_stmt = Statement(pattern=pat.yes_no_prompt,
                                     action=sendline,
                                     args={'command': 'y'},
                                     loop_continue=True,
                                     continue_timer=False)

        self.continue_connect_stmt = Statement(pattern=pat.continue_connect,
                                               action=ssh_continue_connecting,
                                               args=None,
                                               loop_continue=True,
                                               continue_timer=False)

        self.hit_enter_stmt = Statement(pattern=pat.hit_enter,
                                        action=wait_and_enter,
                                        args=None,
                                        loop_continue=True,
                                        continue_timer=False)

        self.press_ctrlx_stmt = Statement(pattern=pat.press_ctrlx,
                                          action=wait_and_enter,
                                          args=None,
                                          loop_continue=True,
                                          continue_timer=False)

        self.init_conf_stmt = Statement(pattern=pat.setup_dialog,
                                        action='sendline(no)',
                                        args=None,
                                        loop_continue=True,
                                        continue_timer=False)

        self.mgmt_setup_stmt = Statement(pattern=pat.enter_basic_mgmt_setup,
                                         action='send(\x03)',  # Ctrl-C
                                         args=None,
                                         loop_continue=True,
                                         continue_timer=False)

        self.clear_kerberos_no_realm = Statement(pattern=pat.kerberos_no_realm,
                                                 action=sendline,
                                                 args=None,
                                                 loop_continue=True,
                                                 continue_timer=False)

        self.connected_stmt = Statement(pattern=pat.connected,
                                        action=sendline,
                                        args=None,
                                        loop_continue=True,
                                        continue_timer=False)

        self.passphrase_stmt = Statement(pattern=pat.passphrase_prompt,
                                         action=passphrase_handler,
                                         args=None,
                                         loop_continue=True,
                                         continue_timer=False)

        self.sudo_stmt = Statement(pattern=pat.sudo_password_prompt,
                                   action=sudo_password_handler,
                                   args=None,
                                   loop_continue=True,
                                   continue_timer=False)

        self.syslog_msg_stmt = Statement(pattern=pat.syslog_message_pattern,
                                         action=syslog_wait_send_return,
                                         args=None,
                                         loop_continue=True,
                                         trim_buffer=False,
                                         continue_timer=False)

        self.syslog_stripper_stmt = Statement(pattern=pat.syslog_message_pattern,
                                              action=syslog_stripper,
                                              args=None,
                                              loop_continue=True,
                                              trim_buffer=False,
                                              continue_timer=False)

        self.enter_your_selection_stmt = Statement(pattern=pat.enter_your_selection_2,
                                                   action=setup_enter_selection,
                                                   args=None,
                                                   loop_continue=True,
                                                   continue_timer=True)

        self.press_any_key_stmt = Statement(pattern=pat.press_any_key,
                                            action='sendline()',
                                            args=None,
                                            loop_continue=True,
                                            continue_timer=False)

        self.permission_denied_stmt = Statement(pattern=pat.permission_denied,
                                            action=permission_denied_handler,
                                            args=None,
                                            loop_continue=False,
                                            continue_timer=False)

        self.terminal_position_stmt = Statement(pattern=pat.get_cursor_position,
                                                action=terminal_position_handler,
                                                args=None,
                                                loop_continue=True,
                                                continue_timer=False)

        self.enter_your_encryption_selection_stmt = Statement(pattern=pat.enter_your_encryption_selection_2,
                                                   action=setup_enter_selection,
                                                   args=None,
                                                   loop_continue=True,
                                                   continue_timer=True)

#############################################################
#  Statement lists
#############################################################

generic_statements = GenericStatements()

#############################################################
# Initial connection Statements
#############################################################

pre_connection_statement_list = [generic_statements.escape_char_stmt,
                                 generic_statements.press_return_stmt,
                                 generic_statements.continue_connect_stmt,
                                 generic_statements.connection_refused_stmt,
                                 generic_statements.disconnect_error_stmt,
                                 generic_statements.hit_enter_stmt,
                                 generic_statements.press_ctrlx_stmt,
                                 generic_statements.connected_stmt,
                                 generic_statements.syslog_msg_stmt,
                                 generic_statements.press_any_key_stmt,
                                 generic_statements.permission_denied_stmt,
                                 ]

#############################################################
# Authentication Statements
#############################################################

authentication_statement_list = [generic_statements.bad_password_stmt,
                                 generic_statements.login_incorrect,
                                 generic_statements.login_stmt,
                                 generic_statements.useraccess_stmt,
                                 generic_statements.new_password_stmt,
                                 generic_statements.password_stmt,
                                 generic_statements.clear_kerberos_no_realm,
                                 generic_statements.password_ok_stmt,
                                 generic_statements.passphrase_stmt,
                                 generic_statements.enable_secret_stmt
                                 ]

#############################################################
# Setup Statements
#############################################################

initial_statement_list = [generic_statements.init_conf_stmt,
                          generic_statements.mgmt_setup_stmt,
                          generic_statements.enter_your_selection_stmt,
                          generic_statements.enter_your_encryption_selection_stmt
                          ]


############################################################
# Default pattern Statement
#############################################################

default_statement_list = [generic_statements.more_prompt_stmt]

connection_statement_list = \
    default_statement_list + \
    authentication_statement_list + \
    initial_statement_list + \
    pre_connection_statement_list

