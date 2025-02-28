""" Utilities used by multiple plugins.

Module:
    unicon.plugins

Authors:
    pyATS TEAM (pyats-support@cisco.com, pyats-support-ext@cisco.com)

Description:
    Module for defining utilities used across various plugins.
"""

import os
import re
import csv
from pathlib import Path
from prettytable import PrettyTable
from unicon.utils import to_plaintext
from unicon.eal.dialogs import Dialog
from unicon.eal.dialogs import Statement
from unicon.core.errors import UniconAuthenticationError
from unicon.core.errors import CredentialsExhaustedError

# Declare token types for abstract token discovery
TOKEN_TYPES = ['os', 'os_flavor', 'version', 'platform', 'model', 'submodel', 'pid', 'chassis_type']
OPTIONAL_TOKENS = ['os_flavor']
ShowVersion = None
ShowInventory = None
Uname = None
PID_TOKEN_FILE = Path(__file__).parent / 'pid_tokens.csv'


def _fallback_cred(context):
    return [context['default_cred_name']] \
        if 'default_cred_name' in context else []

def _get_creds_to_try(context):
    """ Get list of credentials to try. """
    creds_to_try =  context.get('cred_list', _fallback_cred(context))

    if creds_to_try is None:
        creds_to_try = _fallback_cred(context)

    if not isinstance(creds_to_try, list):
        creds_to_try = [creds_to_try]
    return creds_to_try


def get_current_credential(context, session):
    """ Gets the current credential name to try, if available.

    If a current credential name has not been set, try to get the next
    credential name from the credential list.

    The following optional context keys may be set:
        - credentials - Dict of all known credentials, keyed by name.

        - cred_list - List of credential names to try.
            If not specified, or specified as None, defaults to
            [context.default_cred_name] if set, otherwise [].
            If specified as a non-list, then it is reassigned to a single-
            element list.

        - default_cred_name - Default credential name.

    The following session variables are used:
        - current_credential : The credential currently being used.
          This credential is set to the next credential in the cred_list if
          not previously set.

        - cred_iter : Initialized to an iterable based on cred_list, keeps
          track of which credential to try next.

    Raises
    ------
        CredentialsExhaustedError
            If the session's current_credential was not set and all credential
            names in cred_list have already been tried.
    """
    credentials = context.get('credentials')
    current_credential = None
    if credentials:
        current_credential = session.get('current_credential')
        if not current_credential:
            creds_to_try = session.get('cred_iter',
                iter(_get_creds_to_try(context)))
            session['cred_iter'] = creds_to_try
            try:
                current_credential = next(creds_to_try)
            except StopIteration:
                # All credentials in the list have already been tried.
                pass

        if not current_credential:
            raise CredentialsExhaustedError(
                creds_tried=_get_creds_to_try(context))
        else:
            session['current_credential'] = current_credential

    return current_credential


def invalidate_current_credential(context, session):
    """ The current credential is no longer to be used.
    Save aside the previous credential name in the context so it outlives
    the session.
    """
    context['previous_credential'] = session['current_credential']
    session['current_credential'] = None


def common_cred_username_handler(spawn, context, credential):
    """ Send the current credential's username. """
    try:
        spawn.sendline(to_plaintext(
            context['credentials'][credential]['username']))
    except KeyError:
        raise UniconAuthenticationError("No username found "
            "for credential {}.".format(credential))


def common_cred_password_handler(spawn, context, session, credential,
        reuse_current_credential=False):
    """ Send the current credential's password.

    The current credential is then invalidated as long as
    reuse_current_credential is set to `False`.

    Invalidating a credential means that if any subsequent usernames/passwords
    are requested, the next credential in session['cred_iter'] is consumed.
    """
    try:
        spawn.sendline(to_plaintext(
            context['credentials'][credential]['password']))
    except KeyError:
        raise UniconAuthenticationError("No password found "
            "for credential {}.".format(credential))
    if not reuse_current_credential:
        invalidate_current_credential(context=context, session=session)


def slugify(text):
    """ Simple slugify

    Returns string stripped of special chars, replaced with _
    """
    text = text.lower()
    pattern = re.compile(r'[^a-z0-9]+')
    text = re.sub(pattern, '_', text)
    text = re.sub(r'_{2,}', '_', text).strip('_')
    return text


def sanitize(s):
    """ Remove escape codes and non ASCII characters from output.

    Remove crypto related lines as workaround for deprecation messages.

    ../python3.10/site-packages/asyncssh/crypto/cipher.py:29: CryptographyDeprecationWarning: Blowfish has been deprecated
    from cryptography.hazmat.primitives.ciphers.algorithms import Blowfish, CAST5
    ../python3.10/site-packages/asyncssh/crypto/cipher.py:29: CryptographyDeprecationWarning: CAST5 has been deprecated
    from cryptography.hazmat.primitives.ciphers.algorithms import Blowfish, CAST5
    ../python3.10/site-packages/asyncssh/crypto/cipher.py:30: CryptographyDeprecationWarning: SEED has been deprecated
    from cryptography.hazmat.primitives.ciphers.algorithms import SEED, TripleDES
    """
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    s = ansi_escape.sub('', s)
    mpa = dict.fromkeys(range(32))

    # clean up crypto deprecation warnings
    lines = s.splitlines()
    new_lines = []
    for line in lines:
        if 'CryptographyDeprecationWarning' not in line \
            and 'cryptography.hazmat.primitives.ciphers.algorithms' not in line:
                new_lines.append(line)
    s = '\n'.join(new_lines)

    return s.translate(mpa).strip().replace(' ', '')


def load_token_csv_file(file_path, key='pid'):
    """ Opens the provided .csv file and loads the contents into a dictionary

    A header is required for correct loading. For example:
    pid,os,platform,model,etc...

    By default, this function uses 'pid' as a key column for the return
    dictionary, but a different key can be specified instead
    load_token_csv_file(file_path, key='custom_key')

    For example:
    ASR1002-F,iosxe,asr1k,ASR1000
    or
    CISCO1005,iosxe,c1k,C1000
    """

    ret_dict = {}
    with open(file_path) as f:
        reader = csv.reader(f)
        header = next(reader, None)

        # Create an index mapping for dynamic token loading. Isolate the index
        # of the key and dump the rest into a dict. For example:
        # {'os': 1, 'platform': 2, 'model': 3}, where key_index = 0
        index_map = {}
        key_index = 0
        for index in range(len(header)):
            if header[index] == key:
                key_index = index
            else:
                index_map[header[index]] = index

        # Populate return dict by looping through rows and applying index_map
        for row in reader:
            key_dict = ret_dict.setdefault(row[key_index], {})
            for token_name, token_index in index_map.items():
                key_dict[token_name] = row[token_index]

    return ret_dict

def get_device_mode(con):
        '''Check the mode of device
        '''
        output = con.execute('show version | include operating mode')
        if output:
            pattern = re.compile(r'.*operating mode:\s*(?P<mode>[\w-]+).*', re.DOTALL)
            m = pattern.match(output)
            if m:
                return m.groupdict().get('mode')


class AbstractTokenDiscovery():

    def __init__(self, con, execute_target=None):
        # Putting these imports at the top creates a circular import chain
        # Import them during object initialization if not already imported
        global ShowVersion
        if not ShowVersion:
            from genie.libs.parser.generic.rv1.show_platform import ShowVersion
        global ShowInventory
        if not ShowInventory:
            from genie.libs.parser.generic.rv1.show_platform import ShowInventory
        global Uname
        if not Uname:
            from genie.libs.parser.generic.show_platform import Uname


        self.con = con
        self.device = con.device
        self.execute_target = execute_target

        # Load the pid token lookup file
        self.pid_data = {}
        self.pid_lookup_file = PID_TOKEN_FILE
        self.pid_data = load_token_csv_file(file_path=self.pid_lookup_file)

        # Attach commands and accompying classes for cleaner looping
        self.commands_and_classes = {
            'show version': ShowVersion,
            'show inventory': ShowInventory,
            'uname -a': Uname,
        }

        # Fill in starting token values
        self.learned_tokens = {token_type:None for token_type in TOKEN_TYPES}
        self.predefined_tokens = \
            {token_type:getattr(self.device, token_type, None)
                for token_type in TOKEN_TYPES}


    def update_learned_tokens(self, new_tokens, overwrite_existing_values=True):
        for token_type, token_value in self.learned_tokens.items():
            if token_type in new_tokens:
                if token_value is None or overwrite_existing_values:
                    self.learned_tokens[token_type] = new_tokens[token_type]


    def all_tokens_learned(self):
        for token ,token_value in self.learned_tokens.items():
            if token not in OPTIONAL_TOKENS:
                if token_value == '' or token_value is None:
                    return False
        return True


    def lookup_tokens_using_pid(self, pid_to_check):
        try:
            data = self.pid_data[pid_to_check]
        except KeyError:
            return {'pid': pid_to_check}
        else:
            return {
                'os': data['os'],
                'platform': data['platform'],
                'model': data['model'],
                'pid': pid_to_check,
            }


    def discover_tokens(self):
        """
        Loop through the commands one at a time and parse the output (if any).
        Update learned tokens when new token values are found
        """
        # import is done here to avoid circular import error
        from unicon.plugins.generic.statements import generic_statements

        device = self.device
        controller_mode = None

        discovery_prompt_stmt = \
            Statement(pattern=self.con.state_machine\
                .get_state('learn_tokens_state').pattern)
        dialog = Dialog([
            discovery_prompt_stmt,
            generic_statements.more_prompt_stmt,
            generic_statements.syslog_msg_stmt
        ])

        # Try to get to enable mode, ignore failure
        from unicon.plugins.generic.statements import generic_statements
        enable_dialog = dialog + Dialog([
            generic_statements.enable_password_stmt,
            generic_statements.syslog_msg_stmt
        ])
        try:
            self.con.sendline('enable')
            enable_dialog.process(self.con.spawn, context=self.con.context)
        except Exception:
            pass

        # Execute the command on the device
        for cmd in self.commands_and_classes:
            try:
                self.con.sendline(cmd)
            except Exception as e:
                self.con.log.debug(
                    f"Failed to execute command '{cmd}' on {self}. Reason: {e}")
                continue
            else:
                outcome = dialog.process(self.con.spawn,
                                         timeout=self.con.spawn.settings.EXEC_TIMEOUT
                                        )

                if not outcome.match_output:
                    continue

                # Try to parse the output from the command
                try:
                    parsed_output = \
                        self.commands_and_classes[cmd](device=self.device)\
                            .cli(output=outcome.match_output)
                except Exception as e:
                    self.con.log.debug(f"Failed to parse command '{cmd}' on "
                                       f"{device}. Reason: {e}")
                else:
                    # this controller will be se to true if device is in controller mode.
                    if parsed_output.get('operating_mode', '') == 'Controller-Managed':
                        controller_mode = True
                    self.update_learned_tokens(parsed_output,
                                               overwrite_existing_values=False)

                    # If pid learned from show version, use to get other tokens
                    if 'pid' in self.learned_tokens:
                        tokens_from_pid = self.lookup_tokens_using_pid(
                            self.learned_tokens['pid'])

                        if tokens_from_pid:
                            self.update_learned_tokens(
                                tokens_from_pid, overwrite_existing_values=True)

                    if cmd == 'show inventory' and \
                            parsed_output.get('inventory_item_index', None):

                        if parsed_output.get('chassis_type'):
                            self.learned_tokens['chassis_type'] = \
                                parsed_output.get('chassis_type')

                        # Look though pids that were found with show inventory
                        for _,entry_data in \
                                parsed_output['inventory_item_index'].items():
                            tokens_from_pid_lookup = \
                                self.lookup_tokens_using_pid(
                                    entry_data.get('pid', None))

                            if tokens_from_pid_lookup:
                                self.update_learned_tokens(
                                    tokens_from_pid_lookup,
                                    overwrite_existing_values=True)
                                break
                if self.all_tokens_learned():
                    self.con.log.debug(
                        "All tokens discovered, ending token discovery early")
                    # if the controller is True device is in controller mode set the
                    # platform to sdwan
                    if controller_mode:
                        self.update_learned_tokens({'platform':'sdwan'})
                    break
        if controller_mode:
            self.update_learned_tokens({'platform':'sdwan'})


    def standardize_token_values(self, tokens):
        """
        Standardize tokens values to ensure they can be used by the abstraction
        lookup library. All lowercase, weird versions cleaned up, etc.
        """
        ret_dict = {}
        for token_type, token_value in tokens.items():

            if not token_value:
                ret_dict[token_type] = None

            else:
                # Remove all white space
                modified_value = re.sub(r'\s', r'', token_value)

                if token_type != 'pid':
                    modified_value = modified_value.lower()

                if token_type == 'version':

                    # Remove brackets that have a colon in them. Typically seen
                    # in experimental version builds containing dates
                    # 17.7.1(20210101:01234) -> 17.7.1
                    # 17.6.20210302:012459 -> 17.6
                    modified_value = re.sub(r'\.?\(?\d{8}\:\d+\)?',
                                            r'',
                                            modified_value)

                    # Remove brackets around numbers. If a number is in a
                    # bracket, then treat it as minor version
                    # 17.7(1) -> 17.7.1
                    modified_value = re.sub(r'\((\w+)\)',
                                            r'.\1',
                                            modified_value)

                    # Remove 0s from front of version numbers and remove
                    # leading/trailing 0s
                    # 17.07.01 -> 17.7.1
                    modified_value = re.sub(r'\.0+(\d)', r'.\1', modified_value)
                    modified_value = re.sub(r'\.0+$|^0+', r'', modified_value)

                ret_dict[token_type] = modified_value

        return ret_dict


    def assign_tokens(self, overwrite_testbed_tokens):
        """
        Assign tokens to the device. Don't overwrite token values unless asked
        to. Give warnings if learned token values are different than those
        that have been predefined in the testbed.
        """
        con = self.con
        device = self.device
        # Loop through token types and update/assign tokens to device
        for token_type in TOKEN_TYPES:

            # Get the value of the token defined in the testbed (if any)
            predefined_token_value = self.predefined_tokens.get(token_type,
                                                                None)

            # Get the value of the token that was learned using various commands
            learned_token_value  = self.learned_tokens.get(token_type, None)

            # If Device has no specified token, assign one
            if learned_token_value and not predefined_token_value:
                con.log.debug(f"Learned new token for {device}. "
                            f"Token type: {token_type}, "
                            f"Token value: {learned_token_value}")
                setattr(device, token_type, learned_token_value)
                continue

            # If device has token specified as 'generic', assign learned token
            # with an overwrite warning
            if learned_token_value and predefined_token_value == 'generic':
                con.log.debug(f"Overwriting 'generic' {token_type} device token"
                              f" with '{learned_token_value}' for  {device}")
                setattr(device, token_type, learned_token_value)
                continue

            # If we're overwriting testbed tokens
            if learned_token_value and overwrite_testbed_tokens:
                con.log.debug(f"Overwriting {token_type} token with "
                              f"'{learned_token_value}' for {device}")
                setattr(device, token_type, learned_token_value)
                continue

            # Warn user about mismatched defined vs learned tokens
            if learned_token_value \
                    and learned_token_value != predefined_token_value:

                if token_type == 'version':
                    # Trim letters in version comparison to increase reliability
                    trimmed_learned_token = \
                        re.sub(r'[a-zA-Z]+',
                        r'',
                        str(learned_token_value))
                    trimmed_predefined_token = \
                        re.sub(r'[a-zA-Z]+',
                        r'',
                        str(predefined_token_value))
                    if trimmed_learned_token == trimmed_predefined_token:
                        continue

                con.log.debug(
                    f"Mismatch found between predefined and learned device "
                    f"tokens for {device}. The token for {token_type} defined "
                    f"in the testbed is {predefined_token_value}, but the "
                    f"learned token is {learned_token_value}. The value of the "
                    f"token defined in the testbed will be used.")
                continue

            # Predefined token and learned token are the same, everything is OK
            con.log.debug(f"Predefined and learned {token_type} are the same: "
                          f"{predefined_token_value}")

    def show_results(self):
        """
        Show results of the token learning process as a table.
        Clearly indicate what tokens were defined in the testbed, what
        tokens were learned and which tokens will be used for the job
        """
        device = self.device
        # Make a table and set each column as left "l" justified
        t = PrettyTable(['Token Type', 'Defined in Testbed',
                         'Learned from Device', 'Used for this job'])
        t.align['Token Type'] = \
        t.align['Defined in Testbed'] = \
        t.align['Learned from Device'] = \
        t.align['Used for this job'] = "l"

        for token_type in TOKEN_TYPES:
            t.add_row([token_type,
                       self.predefined_tokens.get(token_type, None),
                       self.learned_tokens.get(token_type, None),
                       getattr(device, token_type, None)])
        table_title = f"Abstract-Token Discovery Results for: {device.name}"
        self.con.log.info(f'\n{t.get_string(title=table_title)}')


    def learn_device_tokens(self, overwrite_testbed_tokens=False):
        if not self.con.device:
            self.con.log.debug('No device object, cannot learn tokens')
            return {}

        if self.con.state_machine.current_state == 'standby_locked':
            self.con.log.info('Device is locked, cannot learn tokens')
            return {}

        if overwrite_testbed_tokens:
            self.con.log.info('+++ Learning device tokens +++')
        else:
            self.con.log.debug('+++ Learning device tokens +++')

        # Parse commands using generic parsers to get device abstraction tokens
        self.discover_tokens()
        # Force tokens to be same format
        self.predefined_tokens = \
            self.standardize_token_values(self.predefined_tokens)
        self.learned_tokens = self.standardize_token_values(self.learned_tokens)

        # Assign tokens to device as attributes based on a few rules
        self.assign_tokens(overwrite_testbed_tokens)

        # Show the results of the process
        self.show_results()
        return self.learned_tokens
