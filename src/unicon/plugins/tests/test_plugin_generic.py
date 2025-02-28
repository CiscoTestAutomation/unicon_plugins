"""
Unittests for Generic plugin

"""

__author__ = "Dave Wapstra <dwapstra@cisco.com>"

import os
import re
import time
import logging
import unittest
from unittest.mock import Mock, call, patch
from concurrent.futures import ThreadPoolExecutor

multiprocessing = __import__('multiprocessing').get_context('fork')

from pyats.datastructures import AttrDict

import unicon
from unicon import Connection
from unicon.eal.dialogs import Dialog, Statement
from unicon.plugins.utils import sanitize
from unicon.plugins.tests.mock.mock_device_ios import MockDeviceTcpWrapperIOS
from unicon.mock.mock_device import MockDevice, MockDeviceTcpWrapper
from unicon.plugins.generic.statements import login_handler, password_handler, passphrase_handler
from pyats.topology import loader
from pyats.topology.credentials import Credentials


from unicon.core.errors import (SubCommandFailure, StateMachineError,
    SpawnInitError, CredentialsExhaustedError, UniconAuthenticationError,
    ConnectionError )


unicon.settings.Settings.POST_DISCONNECT_WAIT_SEC=0
unicon.settings.Settings.GRACEFUL_DISCONNECT_WAIT_SEC=0.2


class TestPasswordHandler(unittest.TestCase):

    def setUp(self):
        """ Prepare the mock objects for use with the tests
        """
        self.session = AttrDict()
        self.context = AttrDict({
            'username': 'admin',
            'tacacs_password': 'cisco',
            'enable_password': "admin",
            'line_password': "letmein"
            })

        class MockSpawn:
            pass

        def mock_sendline(*args, **kwargs):
            print("Sendline called with: %s %s" % (args, kwargs))

        self.spawn = MockSpawn()
        self.spawn.buffer = ''
        self.spawn.spawn_command = 'ssh -l cisco@router'
        self.spawn.last_sent = 'ssh -l cisco@router'
        self.spawn.sendline = Mock(side_effect=mock_sendline)
        self.spawn.match = AttrDict()
        self.spawn.match.match_output = ""
        self.spawn.settings = Mock()
        self.spawn.settings.PASSWORD_ATTEMPTS = 3

    def _test_password_handler(self):
        """ Execute password handler twice
        """
        password_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)

    def test_ssh_password_handler_without_tacacs_with_l(self):
        """ Check if password handler detects '-l' and sends tacacs password.
            Send tacacs password only in retry attempt. Should not try enable passwd.
        """
        self.session.tacacs_login = 0
        self.spawn.spawn_command = 'ssh -l admin localhost'
        self.spawn.last_sent = 'ssh -l admin localhost'
        self._test_password_handler()
        self.spawn.sendline.assert_has_calls([call('cisco'), call('cisco')])

    def test_ssh_password_handler_without_tacacs_with_at(self):
        """ Check if password handler detects 'user@host' and sends tacacs password.
            Send tacacs password only in retry attempt. Should not try enable passwd.
        """
        self.session.tacacs_login = 0
        self.spawn.spawn_command = 'ssh admin@localhost'
        self.spawn.last_sent = 'ssh admin@localhost'
        self.spawn.match.match_output = """admin@locahost's password: """
        self._test_password_handler()
        self.spawn.sendline.assert_has_calls([call('cisco'), call('cisco')])

    def test_ssh_password_handler_without_tacacs_without_indicator(self):
        """ If last command is not username and start command does not contain username login
            then send line password.
        """
        self.session.tacacs_login = 0
        self.spawn.spawn_command = 'ssh localhost'
        self.spawn.last_sent = 'ssh localhost'
        self._test_password_handler()
        self.spawn.sendline.assert_has_calls([call('letmein'), call('letmein')])

    def test_non_ssh_password_handler_without_tacacs(self):
        """ Check if line password is sent, for first password prompt.
        """
        self.session.tacacs_login = 0
        self.spawn.spawn_command = 'telnet 127.0.0.1 2001'
        self.spawn.last_sent = 'telnet 127.0.0.1 2001'
        self._test_password_handler()
        self.spawn.sendline.assert_has_calls([call('letmein'), call('letmein')])

    def test_non_ssh_password_handler_with_tacacs(self):
        """ Check if tacacs password is sent if last command sent is username.
        """
        self.session.tacacs_login = 1
        self.spawn.spawn_command = 'telnet 127.0.0.1 2001'
        self.spawn.last_sent = self.context.username
        self._test_password_handler()
        self.spawn.sendline.assert_has_calls([call('cisco'), call('cisco')])

    def test_enable_password(self):
        d = Connection(hostname='Router',
                start=['mock_device_cli --os ios --state console_test_enable'],
                os='ios', enable_password='enpasswd', connection_timeout=15, mit=True)
        d.connect()

    def test_password_retries(self):
        with self.assertRaises(UniconAuthenticationError):
            for x in range(4):
                password_handler(self.spawn, self.context, self.session)


class TestCredentialLoginPasswordHandlers(unittest.TestCase):

    def setUp(self):
        """ Prepare the mock objects for use with the tests
        """
        self.session = AttrDict()
        self.context = AttrDict({
            'default_cred_name': 'default',
            'credentials': Credentials({
                'default': {
                    'username': 'defun',
                    'password': 'defpw',
                    'passphrase': 'this is a secret'
                },
                'mycred': {'username': 'admin', 'password': 'cisco'},
                'enable': {'password': 'enpasswd'},
                'ssh': {'passphrase': 'this is another secret'}
            })
        })

        class MockSpawn:
            pass

        def mock_sendline(*args, **kwargs):
            print("Sendline called with: %s %s" % (args, kwargs))

        self.spawn = MockSpawn()
        self.spawn.spawn_command = 'ssh -l cisco@router'
        self.spawn.last_sent = 'ssh -l cisco@router'
        self.spawn.sendline = Mock(side_effect=mock_sendline)
        self.spawn.match = AttrDict()
        self.spawn.match.match_output = ""
        self.spawn.settings = Mock()

    def test_default_cred_sent_if_no_creds_given(self):
        password_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('defpw')])

    def test_default_cred_sent_if_no_creds_given_with_login(self):
        login_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('defun'), call('defpw')])

    def test_default_cred_sent_when_unknown_cred_given_with_login(self):
        self.context['cred_list'] = ['badcred']
        login_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('defun'), call('defpw')])

    def test_unknown_cred_given_with_login(self):
        self.context['cred_list'] = ['badcred']
        self.context['credentials']['default'].pop('username')
        with self.assertRaisesRegex(UniconAuthenticationError,
                '.*No username.*badcred'):
            login_handler(self.spawn, self.context, self.session)
            password_handler(self.spawn, self.context, self.session)

    def test_no_password_specified(self):
        self.context['credentials']['default'].pop('password')
        with self.assertRaisesRegex(UniconAuthenticationError,
                '.*No password.*default'):
            login_handler(self.spawn, self.context, self.session)
            password_handler(self.spawn, self.context, self.session)

    def test_alt_cred_send_login_password(self):
        self.context['cred_list'] = ['mycred']
        login_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('admin'), call('cisco')])

    def test_default_cred_send_passphrase(self):
        passphrase_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('this is a secret')])

    def test_alt_cred_send_passphrase(self):
        self.context['cred_list'] = ['ssh']
        passphrase_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls([call('this is another secret')])

    def test_cred_seq_login_password(self):
        self.context['cred_list'] = ['mycred', 'default']
        login_handler(self.spawn, self.context, self.session)
        login_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)
        login_handler(self.spawn, self.context, self.session)
        password_handler(self.spawn, self.context, self.session)
        self.spawn.sendline.assert_has_calls(
            [call('admin'), call('cisco'),
             call('defun'), call('defpw')])

    def test_password_failed(self):
        with self.assertRaisesRegex(CredentialsExhaustedError,
                '.*tried without success.*default'):
            login_handler(self.spawn, self.context, self.session)
            password_handler(self.spawn, self.context, self.session)
            password_handler(self.spawn, self.context, self.session)

    def test_enable_password(self):
        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios', connection_timeout=15,
                       credentials=self.context.credentials,
                       mit=True)
        d.connect()

    def test_enable_password_default_cred_explicit(self):
        credentials = Credentials({
            'default': {'username': 'admin', 'password': 'cisco', 'enable_password': 'enpasswd'},
            'enable': {'password': 'enpasswd2'},
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios', connection_timeout=15,
                       credentials=credentials,
                       login_creds=None,
                       mit=True
                       )
        d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios', connection_timeout=15,
                       credentials=credentials,
                       mit=True
                       )
        d.connect()

    def test_enable_password_default_cred_revert_enable(self):
        credentials = Credentials({
            'default': {'username': 'admin', 'password': 'cisco', },
            'enable': {'password': 'enpasswd'},
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios', connection_timeout=15,
                       credentials=credentials,
                       mit=True
                       )
        d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios', connection_timeout=15,
                       credentials=credentials,
                       mit=True
                       )
        d.connect()

    def test_enable_password_default_cred_default_enable(self):
        credentials = Credentials({
            'default': {'username': 'admin', 'password': 'cisco', },
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials
                       )
        with self.assertRaises(CredentialsExhaustedError):
            d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials
                       )
        with self.assertRaises(CredentialsExhaustedError):
            d.connect()

    def test_enable_password_explicit(self):
        credentials = Credentials({
            'default': {'username': 'defun', 'password': 'defpw', 'enable_password': 'enpasswd2'},
            'mycred': {'username': 'admin', 'password': 'cisco', 'enable_password': 'enpasswd'},
            'enable': {'password': 'enpasswd3'},
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

    def test_enable_password_explicit_revert_default(self):
        credentials = Credentials({
            'default': {'username': 'defun', 'password': 'defpw', 'enable_password': 'enpasswd'},
            'mycred': {'username': 'admin', 'password': 'cisco', },
            'enable': {'password': 'enpasswd2'},
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

    def test_enable_password_explicit_revert_enable(self):
        credentials = Credentials({
            'default': {'username': 'defun', 'password': 'defpw', },
            'mycred': {'username': 'admin', 'password': 'cisco', },
            'enable': {'password': 'enpasswd'},
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        d.connect()

    def test_enable_password_explicit_revert_default_enable(self):
        credentials = Credentials({
            'default': {'username': 'defun', 'password': 'defpw', },
            'mycred': {'username': 'admin', 'password': 'cisco', },
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state console_test_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        with self.assertRaises(CredentialsExhaustedError):
            d.connect()

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state login_enable'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       login_creds='mycred')
        with self.assertRaises(CredentialsExhaustedError):
            d.connect()

    def test_connect_ssh_passphrase(self):
        credentials = Credentials({
            'default': {'passphrase': 'this is a secret'}
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state connect_ssh_passphrase'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       init_exec_commands=[],
                       init_config_commands=[])
        d.connect()
        d.disconnect()

    def test_connect_ssh_no_passphrase(self):
        credentials = Credentials({
            'default': {'password': 'cisco'}
        })

        d = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state connect_ssh_passphrase'],
                       os='ios',
                       connection_timeout=15,
                       credentials=credentials,
                       init_exec_commands=[],
                       init_config_commands=[])

        with self.assertRaises(UniconAuthenticationError):
            d.connect()


class TestGenericServices(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.d = Connection(hostname='Router',
                           start=['mock_device_cli --os ios --state exec'],
                           os='ios',
                           credentials=dict(default=dict(
                               username='cisco',
                               password='cisco',
                           )),
                           service_attributes=dict(ping=dict(timeout=2468)))
        cls.d.connect()
        cls.md = MockDevice(device_os='ios', state='exec')
        cls.ha = MockDeviceTcpWrapperIOS(port=0, state='login,exec_standby')

        # Add command output with 80K lines
        cls.ha.mockdevice.mock_data['enable']['commands']['show ospf dummy'] = \
        "123.123.123.123     123.123.123.123 1000        0x80000003 0x000000 0\n" * 80000

        cls.ha.start()
        cls.ha_device = Connection(hostname='Router',
                                   start=['telnet 127.0.0.1 ' + str(cls.ha.ports[0]),
                                          'telnet 127.0.0.1 ' + str(cls.ha.ports[1])],
                                   os='ios',
                                   credentials=dict(default=dict(
                                       username='cisco',
                                       password='cisco',
                                   )),
                                   init_config_commands=[],
                                   init_exec_commands=[])
        cls.ha_device.connect()
        cls.logfile_testfile = '/tmp/test_log_file.log'

    @classmethod
    def tearDownClass(cls):
        cls.d.disconnect()
        cls.ha_device.disconnect()
        cls.ha.stop()
        try:
            os.remove(cls.logfile_testfile)
        except:
            pass

    def test_config_multiple_command_output(self):
        cmd = 'do show version'
        cmd_list = ['do show version', 'do show version']
        ret = self.d.configure(cmd_list)
        test_output =  ret.replace('\r\n', '\n')
        single_cmd_output = cmd + '\n' + self.md.mock_data['exec']['commands']['show version']
        expected_output = single_cmd_output + single_cmd_output
        self.assertEqual(expected_output, test_output)

    def test_config_ha_multiple_command_output(self):
        cmd = 'do show version'
        cmd_list = ['do show version', 'do show version']
        ret = self.ha_device.configure(cmd_list)
        test_output =  ret.replace('\r', '')
        single_cmd_output = cmd + '\n' + self.md.mock_data['exec']['commands']['show version']
        self.maxDiff = None
        expected_output = single_cmd_output + single_cmd_output
        self.assertEqual(expected_output, test_output)

    def test_log_file(self):
        self.assertIn('/tmp/', self.d.log_file())
        org_file = self.d.logfile
        self.d.log_file(self.logfile_testfile)
        self.d.execute('show version')
        with open(self.logfile_testfile) as fh:
            self.assertIn('show version', fh.read())
        self.d.log_file(org_file)

    def test_sync_state(self):
        try:
            self.ha_device.sync_state()
            result = True
        except Exception as e:
            print('Error in sync_state service: {}'.format(e))
            result = False
        self.assertTrue(result)

    def test_execute_large_output(self):
        self.ha_device.log_user(enable=False)
        # If matching is slow, this command will take longer than 60 seconds
        # (which is the default timeout)
        self.ha_device.execute('show ospf dummy')

    def test_expect_large_output(self):
        self.ha_device.log_user(enable=False)
        # If matching is slow, this command will take longer than 60 seconds
        self.ha_device.sendline('show ospf dummy')
        self.ha_device.expect('^(.*?)#', timeout=60)

    def test_search_size(self):
        self.assertEqual(self.d.spawn.search_size, self.d.settings.SEARCH_SIZE)
        self.d.execute('', search_size=1234)
        self.assertEqual(self.d.spawn.search_size, self.d.settings.SEARCH_SIZE)

    def test_search_size_ha(self):
        self.assertEqual(self.ha_device.active.spawn.search_size, self.ha_device.settings.SEARCH_SIZE)
        self.ha_device.execute('', search_size=1234)
        self.assertEqual(self.ha_device.active.spawn.search_size, self.ha_device.settings.SEARCH_SIZE)

    def test_error_pattern(self):
        with self.assertRaises(SubCommandFailure):
            self.d.execute('unkown command', error_pattern=['^% '])

        with self.assertRaises(SubCommandFailure):
            self.ha_device.execute('unkown command', error_pattern=['^% '])

    def test_append_error_pattern(self):
        with self.assertRaises(SubCommandFailure):
            self.d.execute('unkown command', append_error_pattern=['unkown command'])

        with self.assertRaises(SubCommandFailure):
            self.ha_device.execute('unkown command', append_error_pattern=['unkown command'])

    def test_multi_thread_execute(self):
        commands = ['show version'] * 3
        with ThreadPoolExecutor(max_workers=3) as executor:
            all_task = [executor.submit(self.d.execute, cmd)
                        for cmd in commands]
            results = [task.result() for task in all_task]

    def test_multi_process_execute(self):
        class Child(multiprocessing.Process):
            pass

        commands = ['show version'] * 3
        processes = [Child(target=self.d.execute, args=(cmd,))
                     for cmd in commands]
        for process in processes:
            process.start()
        for process in processes:
            process.join()

    def test_execute_remove_backspace(self):
        # output with a single backspae
        r = self.d.execute('show command with backspace')
        self.assertEqual(r, 'test')

        # user sending ctrl-u to remove the command, this has multiple backspaces
        self.d.send('abcdef\x15')
        r = self.d.execute('show redundancy sta |  in peer')
        self.assertEqual(r, 'peer state = 8  -STANDBY HOT')

    def test_service_attribute_patching(self):
        self.assertEqual(self.d.ping.timeout, 2468)
        self.assertEqual(self.ha_device.ping.timeout, 60)


class TestConfigureService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.d = Connection(
            hostname='Router',
            start=['mock_device_cli --os ios --state enable'],
            os='ios',
            username='cisco',
            tacacs_password='cisco',
            enable_password='cisco',
            mit=True,
            log_buffer=True,
        )
        cls.d.connect()
    

        cls.ha = MockDeviceTcpWrapperIOS(port=0, state='enable,exec_standby')
        cls.ha.start()
        cls.d_ha = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 ' + str(cls.ha.ports[0]),
                   'telnet 127.0.0.1 ' + str(cls.ha.ports[1])],
            os='ios',
            username='cisco',
            tacacs_password='cisco',
            enable_password='cisco',
            log_buffer=True
        )
        cls.d_ha.connect()

    def test_config(self):
        out = self.d.configure('no logging console')
        self.assertEqual(out.count('no logging console'), 1)
        out = self.d.configure(['no logging console'] * 3)
        self.assertEqual(out.count('no logging console'), 3)

    def test_ha_config(self):
        out = self.d_ha.configure('no logging console')
        self.assertEqual(out.count('no logging console'), 1)
        out = self.d_ha.configure(['no logging console'] * 3)
        self.assertEqual(out.count('no logging console'), 3)

    def test_bulk_config(self):
        out = self.d.configure('no logging console', bulk=True)
        self.assertEqual(out.count('no logging console'), 1)
        out = self.d.configure(['no logging console'] * 3, bulk=True)
        self.assertEqual(out.count('no logging console'), 3)

        start = time.time()
        out = self.d.configure(['no logging console'] * 3, bulk=True,
                               bulk_chunk_lines=2, bulk_chunk_sleep=4)
        self.assertEqual(out.count('no logging console'), 3)
        stop = time.time()
        self.assertGreater(stop - start, 4)

        self.d.configure.bulk = True
        self.d.configure.bulk_chunk_lines = 2
        self.d.configure.bulk_chunk_sleep = 3
        start = time.time()
        out = self.d.configure(['no logging console'] * 5)
        self.assertEqual(out.count('no logging console'), 5)
        stop = time.time()
        self.assertGreater(stop - start, 6)
        self.d.configure.bulk = False

    def test_ha_bulk_config(self):
        out = self.d_ha.configure('no logging console', bulk=True)
        self.assertEqual(out.count('no logging console'), 1)
        out = self.d_ha.configure(['no logging console'] * 3, bulk=True)
        self.assertEqual(out.count('no logging console'), 3)

        start = time.time()
        out = self.d_ha.configure(['no logging console'] * 3, bulk=True,
                                  bulk_chunk_lines=2, bulk_chunk_sleep=4)
        self.assertEqual(out.count('no logging console'), 3)
        stop = time.time()
        self.assertGreater(stop - start, 4)

        self.d_ha.configure.bulk = True
        self.d_ha.configure.bulk_chunk_lines = 2
        self.d_ha.configure.bulk_chunk_sleep = 3
        start = time.time()
        out = self.d_ha.configure(['no logging console'] * 5)
        self.assertEqual(out.count('no logging console'), 5)
        stop = time.time()
        self.assertGreater(stop - start, 6)
        self.d_ha.configure.bulk = False

    def test_config_lock_retries_succeed(self):
        self.d.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        self.d.execute('set config lock count 1')
        self.d.configure('no logging console',
                         lock_retries=2, lock_retry_sleep=1)
        self.d.configure('no logging console')

    def test_config_lock_retries_fail(self):
        self.d.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        self.d.execute('set config lock count 3')
        with self.assertRaises(StateMachineError):
            self.d.configure('no logging console', lock_retries=2)

    def test_change_state(self):
        with self.assertRaises(StateMachineError):
            self.d.configure(['go to enable','go to config'], allow_state_change = False)
        self.d.configure(['go to enable','go to config'], allow_state_change = True)
        self.assertEqual(self.d.state_machine.current_state, 'enable')


    def test_configure_error_pattern(self):
        with self.assertRaises(SubCommandFailure):
            self.d.configure('Not valid configuration',
                             error_pattern=[r'% Invalid command'])
        self.assertEqual(self.d.state_machine.current_state,
                         self.d.configure.end_state)

    def test_configure_append_error_pattern(self):
        with self.assertRaises(SubCommandFailure):
            self.d.configure('Not valid configuration',
                             append_error_pattern=[r'Not valid configuration'])

    def test_configure_error_pattern2(self):
        error_pattern = [r'% Invalid command']
        try:
            self.d.settings.CONFIGURE_ERROR_PATTERN, error_pattern = \
                error_pattern, self.d.settings.CONFIGURE_ERROR_PATTERN
            with self.assertRaises(SubCommandFailure):
                r = self.d.configure('Not valid configuration')
        finally:
            self.d.settings.CONFIGURE_ERROR_PATTERN, error_pattern = \
                error_pattern, self.d.settings.CONFIGURE_ERROR_PATTERN
        self.assertEqual(self.d.state_machine.current_state,
                         self.d.configure.end_state)

    def test_ha_config_lock_retries_succeed(self):
        self.d_ha.execute('set config lock count 2')
        self.d_ha.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        self.d_ha.configure('no logging console',
                            lock_retries=2, lock_retry_sleep=1)
        self.d_ha.configure('no logging console')

    def test_ha_config_lock_retries_fail(self):
        self.d_ha.execute('set config lock count 3')
        self.d_ha.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        with self.assertRaises(StateMachineError):
            self.d_ha.configure('no logging console', lock_retries=2)

    def test_configure_ca_trustpoint(self):
        self.d.configure(['crypto pki trustpoint KEYPAIR', 'rsakeypair SSHKEYS'])

    def test_configure_commit_cmd_attribute(self):
        c = Connection(
            hostname='Router',
            start=['mock_device_cli --os ios --state enable'],
            os='ios',
            mit=True,
            settings=dict(POST_DISCONNECT_WAIT_SEC=0,GRACEFUL_DISCONNECT_WAIT_SEC=0.2),
            service_attributes=dict(configure=dict(commit_cmd="mycommit cmd")),
            log_buffer=True
        )
        c.connect()
        self.assertEqual(c.configure.commit_cmd, 'mycommit cmd')

    def test_configure_user_end_exit(self):
        c = Connection(
            hostname='switch',
            start=['mock_device_cli --os nxos --state exec'],
            os='nxos',
            mit=True,
            settings=dict(POST_DISCONNECT_WAIT_SEC=0,GRACEFUL_DISCONNECT_WAIT_SEC=0.2),
            log_buffer=True
        )
        c.connect()
        c.configure('end')
        self.assertEqual(c.state_machine.current_state, 'enable')

        c.configure('exit')
        self.assertEqual(c.state_machine.current_state, 'enable')

        with self.assertRaises(StateMachineError):
            c.configure('exitt')

        c.configure(['line console', 'exit', 'exit'])
        self.assertEqual(c.state_machine.current_state, 'enable')
        c.disconnect()

    @classmethod
    def tearDownClass(cls):
        cls.d.disconnect()
        cls.d_ha.disconnect()
        cls.ha.stop()

class TestExecuteService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.d = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state exec'],
                            os='ios', enable_password='cisco',
                            username='cisco',
                            tacacs_password='cisco')
        cls.d.connect()
        cls.md = MockDevice(device_os='ios', state='exec')
        cls.ha = MockDeviceTcpWrapperIOS(port=0, state='login,exec_standby')
        cls.ha.start()
        cls.ha_device = Connection(hostname='Router',
                        start=['telnet 127.0.0.1 '+  str(cls.ha.ports[0]), 'telnet 127.0.0.1 '+ str(cls.ha.ports[1]) ],
                        os='ios', username='cisco', tacacs_password='cisco', enable_password='cisco',
                        init_config_commands=[], init_exec_commands=[])
        cls.ha_device.connect()

    @classmethod
    def tearDownClass(cls):
        cls.d.disconnect()
        cls.ha_device.disconnect()
        cls.ha.stop()

    def setUp(self):
        self.d.enable()
        self.ha_device.enable()
        self.d.settings.EXEC_ALLOW_STATE_CHANGE = False

    def test_universal_execute(self):
        self.d.execute('config term', allow_state_change=True)
        self.assertEqual(self.d.state_machine.current_state, 'config')
        self.d.execute('line console 0')
        self.assertEqual(self.d.state_machine.current_state, 'config')
        self.d.settings.EXEC_ALLOW_STATE_CHANGE = True
        self.d.execute('end')
        self.assertEqual(self.d.state_machine.current_state, 'enable')
        self.d.execute('disable')
        self.assertEqual(self.d.state_machine.current_state, 'disable')
        self.d.execute('enable', reply=Dialog([[r'^(.*?)Password:', 'sendline_ctx(tacacs_password)', None, False, False]]))
        self.assertEqual(self.d.state_machine.current_state, 'enable')
        self.d.execute('disable')
        self.assertEqual(self.d.state_machine.current_state, 'disable')
        self.ha_device.execute('config term', allow_state_change=True)
        self.assertEqual(self.ha_device.active.state_machine.current_state, 'config')

    def test_execute_allow_state_change(self):
        with self.assertRaises(StateMachineError) as e1:
            self.d.execute('config term')
        self.assertEqual(self.d.state_machine.current_state, 'config')
        self.ha_device.settings.EXEC_ALLOW_STATE_CHANGE = True
        with self.assertRaises(StateMachineError) as e2:
            self.ha_device.execute('config term', allow_state_change=False)
        self.assertEqual(self.ha_device.active.state_machine.current_state, 'config')

    def test_execute_with_more_backspace(self):
        self.d.settings.MORE_CONTINUE = '\r'
        output = self.d.execute('show command with more backspace')
        self.assertEqual(output, 'first\r\n\r\nsecond\r\n\r\nthird')
        self.assertEqual(repr(output), repr('first\r\n\r\nsecond\r\n\r\nthird'))

    def test_execute_with_escape_more_backspace(self):
        self.d.settings.MORE_CONTINUE = '\r'
        output = self.d.execute('show command with escape more backspace')
        self.assertEqual(output, 'first\r\n\r\nsecond\r\n\r\nthird')
        self.assertEqual(repr(output), repr('first\r\n\r\nsecond\r\n\r\nthird'))

    def test_execute_with_escape_more(self):
        self.d.settings.MORE_CONTINUE = '\r'
        output = self.d.execute('show command with escape more')
        self.assertEqual(output, 'first\r\n\r\nsecond\r\n\r\nthird')
        self.assertEqual(repr(output), repr('first\r\n\r\nsecond\r\n\r\nthird'))

    def test_execute_with_more(self):
        self.d.settings.MORE_CONTINUE = '\r'
        output = self.d.execute('show command with more')
        self.assertEqual(output, 'first\r\n\r\nsecond\r\n\r\nthird')
        self.assertEqual(repr(output), repr('first\r\n\r\nsecond\r\n\r\nthird'))

    def test_execute_with_transient_match_1(self):
        output = self.d.execute('show command with transient match',
                                matched_retries=3,
                                matched_retry_sleep=7)
        self.assertEqual(output, 'head\r\nRouter#\r\ntail')

    def test_execute_with_transient_match_2(self):
        self.d.execute.matched_retry_sleep = 20
        try:
            output = self.d.execute('show command with transient match')
            self.assertEqual(output, 'head\r\nRouter#\r\ntail')
        finally:
            self.d.execute.matched_retry_sleep = \
                self.d.settings.EXECUTE_MATCHED_RETRY_SLEEP


class TestServiceLogging(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        testbed = """
        devices:
          R1:
            os: iosxe
            alias: uut
            connections:
              defaults:
                class: unicon.Unicon
              a:
                command: mock_device_cli --os iosxe --state general_enable --hostname R1
        """
        t = loader.load(testbed)
        cls.d = t.devices.uut
        cls.d.connect(mit=True)

    @classmethod
    def tearDownClass(cls):
        cls.d.disconnect()

    def test_execute_logging(self):
        self.maxDiff = None
        with self.assertLogs(self.d.log.name, logging.INFO) as cm:
            self.d.execute('show version')
            self.assertIn("R1(alias=uut) with via 'a'", cm.output[0])


class TestTransmitReceive(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.d = Connection(
            hostname='Router',
            start=['mock_device_cli --os ios --state exec'],
            os='ios', enable_password='cisco',
            username='cisco',
            tacacs_password='cisco'
        )
        cls.d.connect()
        cls.term_buffer_pattern = re.compile(r'term width 0.*#', re.S)

    @classmethod
    def tearDownClass(cls):
        cls.d.disconnect()

    def test_transmit(self):
        self.assertTrue(self.d.transmit('term width 0\r'))

    def test_receive_when_match(self):
        self.d.send('term width 0\r')
        self.assertTrue(self.d.receive(r'.*#'))
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_buffer(self):
        self.d.sendline('term width 0')
        self.d.receive(r'^.*#')
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_nopattern(self):
        self.d.transmit('term width 0\r')
        self.assertFalse(self.d.receive(r'nopattern^', timeout=10))
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_no_match(self):
        self.d.transmit('term width 0\r')
        self.assertFalse(self.d.receive(r'somepattern', timeout=10))
        self.assertEqual(self.d.receive_buffer(), '')

    def test_receive_after_receive_no_match(self):
        self.d.sendline('term width 0')
        self.assertFalse(self.d.receive(r'wrongpattern', timeout=10))
        self.assertEqual(self.d.receive_buffer(), '')
        self.assertTrue(self.d.receive(r'term width 0.*#', timeout=10))
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_nopattern_after_receive_no_match(self):
        self.d.sendline('term width 0')
        self.assertFalse(self.d.receive(r'wrongpattern', timeout=10))
        self.assertEqual(self.d.receive_buffer(), '')
        self.assertFalse(self.d.receive(r'nopattern^', timeout=10))
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_buffer_without_receive(self):
        self.d.send('term width 0\r')
        with self.assertRaisesRegex(SubCommandFailure,
                 r"receive_buffer should be invoked after receive call"):
            (self.d.receive_buffer(), self.term_buffer_pattern)

    def test_receive_buffer_without_receive_after_successful_receive(self):
        self.d.send('term width 0\r')
        self.assertTrue(self.d.receive(r'.*#'))
        self.assertRegex(self.d.receive_buffer(), self.term_buffer_pattern)
        self.d.send('term width 0\r')
        with self.assertRaisesRegex(SubCommandFailure,
                 r"receive_buffer should be invoked after receive call"):
            (self.d.receive_buffer(), self.term_buffer_pattern)


class TestEscapeHandler(unittest.TestCase):

    def setUp(self):
        self.old_term_setting = os.environ.get('TERM')
        os.environ['TERM'] = 'VT100'

    def test_escape_handler_uav(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state ios_connect_console_server_with_uav'],
                       os='ios', line_password="cisco",
                       username='cisco',
                       tacacs_password='cisco',
                       enable_password='cisco',
                       settings={'ESCAPE_CHAR_CHATTY_TERM_WAIT': 3,
                                 'ESCAPE_CHAR_PROMPT_WAIT': 3},
                       init_config_commands=[],
                       init_exec_commands=[])
        r = c.connect()
        self.assertEqual(sanitize(r.replace('\r', '')), sanitize("""\
Trying 127.0.0.1...
Connected to localhost.
Escape character is '^]'.

#######################
#          #    ######
#         # #   #     #
#        #   #  #     #
#       #     # ######
#       ####### #     #
#       #     # #     #
####### #     # ######
#######################

User Access Verification

Password: cisco
Router>
enable
Password: cisco
Router#"""))

    def test_escape_handler_username(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state ios_connect_console_server_with_username'],
                       os='ios', line_password="cisco",
                       username='cisco',
                       tacacs_password='cisco',
                       enable_password='cisco',
                       settings={'ESCAPE_CHAR_CHATTY_TERM_WAIT': 3,
                                 'ESCAPE_CHAR_PROMPT_WAIT': 3},
                       init_config_commands=[],
                       init_exec_commands=[])
        r = c.connect()
        self.assertEqual(sanitize(r.replace('\r', '')), sanitize("""\
Trying 127.0.0.1...
Connected to localhost.
Escape character is '^]'.

#######################
#          #    ######
#         # #   #     #
#        #   #  #     #
#       #     # ######
#       ####### #     #
#       #     # #     #
####### #     # ######
#######################

username: cisco
Password: cisco
Router>
enable
Password: cisco
Router#"""))

    def test_escape_handler_password(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os ios --state ios_connect_console_server_with_password'],
                       os='ios', line_password="cisco",
                       username='cisco',
                       tacacs_password='cisco',
                       enable_password='cisco',
                       settings={'ESCAPE_CHAR_CHATTY_TERM_WAIT': 3,
                                 'ESCAPE_CHAR_PROMPT_WAIT': 3},
                       init_config_commands=[],
                       init_exec_commands=[])
        r = c.connect()
        self.assertEqual(sanitize(r.replace('\r', '')), sanitize("""\
Trying 127.0.0.1...
Connected to localhost.
Escape character is '^]'.

password: cisco
Router>
enable
Password: cisco
Router#"""))

    def tearDown(self):
        if self.old_term_setting:
            os.environ['TERM'] = self.old_term_setting
        else:
            os.environ.pop('TERM')


class TestLearnHostname(unittest.TestCase):

    def test_learn_hostname_default(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state exec'],
                            os='ios', enable_password='cisco',
                            username='cisco',
                            tacacs_password='cisco',
                            learn_hostname=True)
        c.settings.TERM='vt100'
        c.connect()
        md = MockDevice(device_os='ios', state='exec')
        expected_output = md.mock_data['exec']['commands']['show version'].rstrip()
        output = c.execute('show version').replace('\r', '')
        self.assertEqual(output, expected_output)

    def test_learn_hostname_r1(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state exec --hostname R1'],
                            os='ios', enable_password='cisco',
                            username='cisco',
                            tacacs_password='cisco',
                            learn_hostname=True)
        c.settings.TERM='vt100'
        c.connect()
        self.assertEqual(c.hostname, 'R1')
        md = MockDevice(device_os='ios', state='exec')
        expected_output = md.mock_data['exec']['commands']['show version'].rstrip()
        output = c.execute('show version').replace('\r', '')
        self.assertEqual(output, expected_output)

    def test_learn_default_hostname(self):
        d = Connection(hostname='X',
                            start=['mock_device_cli --os ios --state enable --hostname Switch'],
                            os='ios', enable_password='cisco',
                            username='cisco',
                            tacacs_password='cisco',
                            learn_hostname=True)
        d.settings.TERM='vt100'
        d.connect()
        self.assertEqual(d.hostname, 'Switch')
        d.disconnect()

    def test_learn_hostname_hash_characters(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state execHashCharacters'],
                            os='ios', enable_password='cisco',
                            username='cisco',
                            tacacs_password='cisco',
                            learn_hostname=True)
        c.settings.TERM='vt100'
        c.connect()
        self.assertNotIn('#',c.hostname)
        c.disconnect()


class TestLargeConfigOnXR(unittest.TestCase):

    def test_exception(self):
        d = Connection(hostname='Router', start=['mock_device_cli --os iosxr --state enable'], os='iosxr')
        d.connect()
        with self.assertRaises(StateMachineError):
            d.configure('large config', timeout=2)
        d.disconnect()

    def test_config_timeout(self):
        d = Connection(hostname='Router', start=['mock_device_cli --os iosxr --state enable'], os='iosxr')
        d.connect()
        d.configure('large config', timeout=20)
        d.disconnect()


class TestConnect(unittest.TestCase):

    def test_connect_start_cmd_not_present(self):
        d = Connection(hostname='Router', start=['xtelnetx 127.0.0.1'], os='ios')
        with self.assertRaises(unicon.core.errors.SpawnInitError):
            d.connect()

    def test_connect_with_setup(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state ios_setup'],
                            os='ios',
                            username='cisco',
                            enable_password='cisco',
                            tacacs_password='cisco',
                            init_exec_commands=[],
                            init_config_commands=[])
        c.connect()
        self.assertEqual(c.state_machine.current_state, 'enable')


    def test_connect_with_setup_mgmt(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os ios --state enable'],
                            os='ios',
                            username='cisco',
                            enable_password='cisco',
                            tacacs_password='cisco',
                            # init_exec_commands=[],
                            init_config_commands=[]
                            )
        c.connect()
        c.sendline('setup_mgmt')
        c.connection_provider.connect()
        self.assertEqual(c.state_machine.current_state, 'enable')

    def test_connect_serial_console(self):
        c = Connection(hostname='Router',
                            start=['mock_device_cli --os iosxr --state connect_serial'],
                            os='iosxr',
                            username='admin',
                            enable_password='admin',
                            tacacs_password='admin',
                            init_config_commands=[]
                            )
        c.connect()

    def test_multi_thread_connect(self):
        dev_dic = {
            'os': 'ios',
            'hostname': 'Router',
            'start': ['mock_device_cli --os ios --state login'],
            'username': 'cisco',
            'tacacs_password': 'cisco',
            'enable_password': 'cisco'
        }
        with ThreadPoolExecutor(max_workers=3) as executor:
            all_task = [executor.submit(Connection(**dev_dic).connect)
                        for _ in range(3)]
            results = [task.result() for task in all_task]


class TestClearLinePasswords(unittest.TestCase):
    def setUp(self):
        from unicon.utils import Utils
        self.utils = Utils()

    def test_clear_line_username_password(self):
         md = MockDeviceTcpWrapper(device_os='ios', port=0, state='ts_login', vty=True)
         md.start()
         term_server = "127.0.0.1 " + str(md.ports[0])
         self.utils.clear_line(term_server, 35, 'admin', 'lab', 'cisco')
         md.stop()

    def test_clear_line_enable_password(self):
         md = MockDeviceTcpWrapper(device_os='ios', port=0, state='console_test_enable', vty=True)
         md.start()
         term_server = "127.0.0.1 " + str(md.ports[0])
         self.utils.clear_line(term_server, 35, 'admin', 'lab', 'enpasswd')
         md.stop()


class TestTacacsLoginPasswordPrompt(unittest.TestCase):

    def test_connect_with_custom_auth_prompt(self):
        d = Connection(hostname='Router', start=['mock_device_cli --os ios --state custom_login'],
                         username='cisco', tacacs_password='cisco', os='ios', enable_password='cisco')
        d.settings.LOGIN_PROMPT = r'Identifier:'
        d.settings.PASSWORD_PROMPT = r'Passe:'
        d.connect()
        d.disconnect()

    def test_topology_connect_with_custom_auth_prompt(self):
        md = MockDeviceTcpWrapper(device_os='ios',port=0, state='custom_login')
        md.start()
        template_testbed = """
        devices:
          Router:
            os: ios
            type: router
            tacacs:
              username: cisco
              login_prompt: 'Identifier:'
              password_prompt: 'Passe:'
            passwords:
              tacacs: cisco
              enable: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
        """.format(md.ports[0])
        t = loader.load(template_testbed)
        d = t.devices['Router']
        d.connect()
        d.disconnect()
        md.stop()

    def test_ha_connect_with_custom_auth_prompt(self):
        d = Connection(hostname='Router', start=['mock_device_cli --os ios --state custom_login,exec_standby'],
                       username='cisco', tacacs_password='cisco', os='ios', enable_password='cisco',
                       mit=True)
        d.settings.LOGIN_PROMPT = r'Identifier:'
        d.settings.PASSWORD_PROMPT = r'Passe:'
        d.connect()
        d.disconnect()

    def test_topology_ha_connect_with_custom_auth_prompt(self):
        md = MockDeviceTcpWrapper(device_os='ios',port=0, state='custom_login,exec_standby')
        md.start()
        template_testbed = """
        devices:
          Router:
            os: ios
            type: router
            tacacs:
              username: cisco
              login_prompt: 'Identifier:'
              password_prompt: 'Passe:'
            passwords:
              tacacs: cisco
              enable: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
              b:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
        """.format(md.ports[0], md.ports[1])
        t = loader.load(template_testbed)
        d = t.devices['Router']
        d.connect()
        d.disconnect()
        md.stop()


class TestLearnOS(unittest.TestCase):

    def test_learn_os(self):
        template_testbed = """
        devices:
          Router:
            os: generic
            type: router
            credentials:
              default:
                password: cisco
                username: cisco
              enable:
                password: cisco
                username: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                command: mock_device_cli --os ios --state exec
        """
        t = loader.load(template_testbed)
        d = t.devices['Router']
        d.connect(learn_hostname=True, learn_os=True, mit=True)
        self.assertEqual(d.os, 'ios')
        d.disconnect()

    def test_learn_os_ha(self):
        template_testbed = """
        devices:
          Router:
            os: generic
            type: router
            credentials:
              default:
                password: cisco
                username: cisco
              enable:
                password: cisco
                username: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                command: mock_device_cli --os ios --state exec
              b:
                command: mock_device_cli --os ios --state exec_standby
        """
        t = loader.load(template_testbed)
        d = t.devices['Router']
        d.connect(learn_hostname=True, learn_os=True)
        self.assertEqual(d.os, 'ios')
        d.disconnect()


class TestSwitchTo(unittest.TestCase):

    def test_switchto(self):
        d = Connection(hostname='Router', start=['mock_device_cli --os ios --state exec'],
                       credentials=dict(default=dict(password='cisco')), mit=True)
        d.connect()
        d.switchto('enable')
        d.switchto(['disable', 'config', 'enable'])
        d.switchto(to_state='disable')
        self.assertEqual(d.state_machine.current_state, 'disable')

class TestGenericReload(unittest.TestCase):

    def test_reload_with_error_pattern(self):
        d = Connection(hostname='Router',
                    start=['mock_device_cli --os ios --state exec --hostname R1'],
                    os='ios', enable_password='cisco',
                    username='cisco',
                    tacacs_password='cisco',
                    learn_hostname=True)

        install_add_one_shot_dialog = Dialog([
                Statement(pattern=r"FAILED:.* ",
                          action=None,
                          loop_continue=False,
                          continue_timer=False),
         ])

        error_pattern=[r"FAILED:.* ",]

        try:
            d.connect()
            d.settings.STACK_POST_RELOAD_SLEEP = 0
            d.reload(error_pattern = error_pattern)
            self.assertEqual(d.reload.error_pattern, error_pattern)
        finally:
             d.disconnect()


class TestGenericConnectionRefused(unittest.TestCase):

    def test_connection_refused_handler_with_peripheral(self):
        md = MockDeviceTcpWrapper(device_os='iosxe', hostname='R1',
            port=0, state='connection_refused')
        md.start()
        template_testbed = """
        devices:
          R1:
            os: iosxe
            credentials:
                default:
                    username: cisco
                    password: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
            peripherals:
                terminal_server:
                    ts: [20]
          ts:
            os: ios
            credentials:
                default:
                    username: cisco
                    password: cisco
            connections:
                cli:
                    command: mock_device_cli --os ios --state exec --hostname ts
        """.format(md.ports[0])
        t = loader.load(template_testbed)
        d = t.devices.R1
        try:
            d.connect()
        finally:
            d.disconnect()
            md.stop()

    def test_connection_refused_handler_without_peripheral(self):
        md = MockDeviceTcpWrapper(device_os='iosxe', hostname='R1',
            port=0, state='connection_refused')
        md.start()
        template_testbed = """
        devices:
          R1:
            os: iosxe
            credentials:
                default:
                    username: cisco
                    password: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
        """.format(md.ports[0])
        t = loader.load(template_testbed)
        d = t.devices.R1
        with self.assertRaisesRegex(unicon.core.errors.ConnectionError,
            'failed to connect to R1'):
            try:
                d.connect()
            finally:
                d.disconnect()
                md.stop()

    def test_connection_refused_handler_repeat(self):
        md = MockDeviceTcpWrapper(device_os='iosxe', hostname='R1',
            port=0, state='connection_refused_loop')
        md.start()
        template_testbed = """
        devices:
          R1:
            os: iosxe
            credentials:
                default:
                    username: cisco
                    password: cisco
            connections:
              defaults:
                class: unicon.Unicon
              a:
                protocol: telnet
                ip: 127.0.0.1
                port: {}
            peripherals:
                terminal_server:
                    ts: [20]
          ts:
            os: ios
            credentials:
                default:
                    username: cisco
                    password: cisco
            connections:
                cli:
                    command: mock_device_cli --os ios --state exec --hostname ts
        """.format(md.ports[0])
        t = loader.load(template_testbed)
        d = t.devices.R1
        with self.assertRaisesRegex(unicon.core.errors.ConnectionError,
                'failed to connect to R1'):
            try:
                d.connect()
            finally:
                d.disconnect()
                md.stop()


if __name__ == "__main__":
    unittest.main()
