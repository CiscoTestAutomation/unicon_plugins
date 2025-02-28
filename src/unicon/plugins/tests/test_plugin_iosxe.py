"""
Unittests for Generic/IOSXE plugin

Uses the unicon.plugins.tests.mock.mock_device_ios script to test IOSXE plugin.

"""

__author__ = "Myles Dear <mdear@cisco.com>"

import re
import time
import unittest
from unittest.mock import patch

from pyats.topology import loader

import unicon
from unicon import Connection
from unicon.eal.dialogs import Dialog, Statement
from unicon.eal.utils import ExpectMatch, MatchMode
from unicon.core.errors import SubCommandFailure, StateMachineError, UniconAuthenticationError, ConnectionError as UniconConnectionError
from unicon.plugins.tests.mock.mock_device_iosxe import MockDeviceTcpWrapperIOSXE

unicon.settings.Settings.POST_DISCONNECT_WAIT_SEC = 0
unicon.settings.Settings.GRACEFUL_DISCONNECT_WAIT_SEC = 0.2


class TestIosXEPluginConnect(unittest.TestCase):

    def test_asr_login_connect(self):
        c = Connection(hostname='Router',
                start=['mock_device_cli --os iosxe --state asr_login --hostname Router'],
                os='iosxe',
                credentials=dict(default=dict(username='cisco', password='cisco')),
                log_buffer=True)
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_isr_controller_mode_connect(self):
        testbed = '''
            devices:
                Router:
                    type: router
                    os: iosxe
                    platform: isr
                    credentials:
                        default:
                            username: cisco
                            password: cisco
                    connections:
                        defaults:
                            class: 'unicon.Unicon'
                        cli:
                            command: mock_device_cli --os iosxe --state isr_exec_1 --hostname Router
        '''
        t = loader.load(testbed)
        d = t.devices.Router
        try:
            d.connect()
        finally:
            d.disconnect()
        self.assertEqual(d.os, 'iosxe')
        self.assertEqual(d.version, '17.14')
        self.assertEqual(d.platform, 'sdwan')
        self.assertEqual(d.model, 'isr4200')
        self.assertEqual(d.pid, 'ISR4221/K9')


    def test_isr_controller_mode_connect(self):
        testbed = '''
            devices:
                Router:
                    type: router
                    os: iosxe
                    platform: isr
                    credentials:
                        default:
                            username: cisco
                            password: cisco
                    connections:
                        defaults:
                            class: 'unicon.Unicon'
                        cli:
                            command: mock_device_cli --os iosxe --state isr_exec_1 --hostname Router
        '''
        t = loader.load(testbed)
        d = t.devices.Router
        try:
            d.connect()
        finally:
            d.disconnect()
        self.assertEqual(d.os, 'iosxe')
        self.assertEqual(d.version, '17.14')
        self.assertEqual(d.platform, 'sdwan')
        self.assertEqual(d.model, 'isr4200')
        self.assertEqual(d.pid, 'ISR4221/K9')


    def test_isr_login_connect(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state isr_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_edison_login_connect(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state cat3k_login --hostname Router'],
                       os='iosxe',
                       platform='cat3k',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_edison_login_connect_password_ok(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state cat3k_login --hostname Router'],
                       os='iosxe',
                       platform='cat3k',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_general_login_connect(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_general_login_connect_syslog(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state connect_syslog --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_general_configure(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
        finally:
            c.disconnect()

        cmd = ['crypto key generate rsa general-keys modulus 2048 label ca',
               'crypto pki server ca', 'grant auto', 'hash sha256', 'lifetime ca-certificate 3650',
               'lifetime certificate 3650', 'database archive pkcs12 password 0 cisco123', 'no shutdown']
        c.configure(cmd, timeout=60, error_pattern=[], service_dialogue=None)
        self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')

    def test_general_config_ca_profile(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))

        try:
            c.connect()
            c.configure("crypto pki profile enrollment test", timeout=60)
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_general_config_ca_cert_map(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_config_certificate_map --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))

        try:
            c.connect()
            self.assertEqual(c.state_machine.current_state, 'enable')
        finally:
            c.disconnect()

    def test_gkm_local_server(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            cmd = [
                "crypto gkm group g1",
                "identity number 101",
                "server local",
                "end",
                "end"
            ]
            c.configure(cmd, timeout=60)
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_login_console_server_sendline_after(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='ts_login')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            settings=dict(SENDLINE_AFTER_CRED='ts'),
            credentials=dict(default=dict(username='cisco', password='cisco'),
                             ts=dict(username='ts_user', password='ts_pw')),
            login_creds=['ts', 'default'],
            connection_timeout=10
        )
        try:
            c.connect()
        finally:
            c.disconnect()
            md.stop()

    def test_login_console_server_post_cred_action(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='ts_login')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco'),
                             ts=dict(username='ts_user', password='ts_pw')),
            login_creds=['ts', 'default'],
            cred_action=dict(ts=dict(post='sendline()')),
            connection_timeout=10
        )
        try:
            c.connect()
        finally:
            c.disconnect()
            md.stop()

    def test_operating_mode_check(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_enable_no_operating_mode --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
        finally:
            c.disconnect()

    def test_vpagent_connect(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state vpagent_login --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')))
        try:
            c.connect()
            self.assertEqual(c.spawn.match.match_output, 'end\r\nRouter#')
        finally:
            c.disconnect()

    def test_unlicensed_prompt(self):
        c = Connection(hostname='UUT',
                       start=['mock_device_cli --os iosxe --state unlicensed_prompt --hostname UUT'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       mit=True)
        try:
            c.connect()
            self.assertEqual(c.spawn.match.last_match.group(2), '(unlicensed)')
        finally:
            c.disconnect()


class TestIosXEPluginExecute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(hostname='switch',
                           start=['mock_device_cli --os iosxe --state isr_exec'],
                           os='iosxe',
                           credentials=dict(default=dict(username='cisco', password='cisco')),
                           log_buffer=True
                           )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
        cls.c.disconnect()

    def test_execute_error_pattern(self):
      for cmd in ['not a real command', 'badcommand']:
        with self.assertRaises(SubCommandFailure) as err:
            r = self.c.execute(cmd)

    def test_execute_error_pattern_negative(self):
        r = self.c.execute('not a real command partial')

    def test_execute_stmt_list(self):
      for cmd in ['install remove inactive']:
        r = self.c.execute(cmd)

    def test_execute_with_msgs(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='enable_with_msgs')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco')),
            mit=True
        )
        try:
            c.connect()
            c.execute('msg')
        finally:
            c.disconnect()
            md.stop()


class TestIosXEPluginDisableEnable(unittest.TestCase):

    def test_disable_enable(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state isr_exec --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )

        r = c.disable()
        self.assertEqual(c.spawn.match.match_output, 'disable\r\nRouter>')

        r = c.enable()
        self.assertEqual(c.spawn.match.match_output, 'cisco\r\nRouter#')

        r = c.disable()
        self.assertEqual(c.spawn.match.match_output, 'disable\r\nRouter>')

        r = c.enable(command='enable 7')
        self.assertEqual(c.spawn.match.match_output, 'cisco\r\nRouter#')

        c.disconnect()

    def test_disable_to_enable_with_msg(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state disable_to_enable_with_msg'],
                       os='iosxe',
                       credentials=dict(default=dict(password='cisco')),
                       log_buffer=True
                       )
        c.connect()
        c.disconnect()


class TestIosXEPluginPing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(hostname='Router',
                           start=['mock_device_cli --os iosxe --state isr_exec --hostname Router'],
                           os='iosxe',
                           credentials=dict(default=dict(username='cisco', password='cisco')),
                           log_buffer=True
                           )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
        cls.c.disconnect()

    def test_ping_success_no_vrf(self):
        r = self.c.ping('192.0.0.5', count=30)
        self.maxDiff = None
        self.assertEqual(r.strip(), "\r\n".join("""ping
Protocol [ip]: 
Target IP address: 192.0.0.5
Repeat count [5]: 30
Datagram size [100]: 
Timeout in seconds [2]: 
Extended commands [n]: n
Sweep range of sizes [n]: n
Type escape sequence to abort.
Sending 30, 100-byte ICMP Echos to 192.0.0.5, timeout is 2 seconds:
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Success rate is 100 percent (30/30), round-trip min/avg/max = 1/1/3 ms""".\
splitlines()))

    def test_ping_success_vrf(self):
        r = self.c.ping('192.0.0.6', vrf='test', count=30)
        self.assertEqual(r.strip(), "\r\n".join("""ping vrf test
Protocol [ip]: 
Target IP address: 192.0.0.6
Repeat count [5]: 30
Datagram size [100]: 
Timeout in seconds [2]: 
Extended commands [n]: n
Sweep range of sizes [n]: n
Type escape sequence to abort.
Sending 30, 100-byte ICMP Echos to 192.0.0.6, timeout is 2 seconds:
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Success rate is 100 percent (30/30), round-trip min/avg/max = 1/1/3 ms""".\
splitlines()))

    def test_ping_success_vrf_in_cmd(self):
        r = self.c.ping('192.0.0.6', command='ping vrf test', vrf='dont_use_this_vrf', count=30)
        self.assertEqual(r.strip(), "\r\n".join("""ping vrf test
Protocol [ip]: 
Target IP address: 192.0.0.6
Repeat count [5]: 30
Datagram size [100]: 
Timeout in seconds [2]: 
Extended commands [n]: n
Sweep range of sizes [n]: n
Type escape sequence to abort.
Sending 30, 100-byte ICMP Echos to 192.0.0.6, timeout is 2 seconds:
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Success rate is 100 percent (30/30), round-trip min/avg/max = 1/1/3 ms""".\
splitlines()))


class TestIosxePlugingTraceroute(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(hostname='Router',
                           start=['mock_device_cli --os iosxe --state isr_exec --hostname Router'],
                           os='iosxe',
                           credentials=dict(default=dict(username='cisco', password='cisco')),
                           log_buffer=True
                           )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
        cls.c.disconnect()

    def test_traceroute_success(self):
        r = self.c.traceroute('192.0.0.5', probe=30)
        self.maxDiff = None
        self.assertEqual(r.strip(), "\r\n".join("""traceroute
Protocol [ip]: 
Target IP address: 192.0.0.5
Ingress traceroute [n]: 
Source address or interface: 
DSCP Value [0]: 
Numeric display [n]: 
Timeout in seconds [3]: 
Probe count [3]: 30
Minimum Time to Live [1]: 
Maximum Time to Live [30]: 
Port Number [33434]: 
Loose, Strict, Record, Timestamp, Verbose[none]: 
Type escape sequence to abort.
Tracing the route to 192.0.0.5
VRF info: (vrf in name/id, vrf out name/id)
  1 192.0.0.5 msec *  1 msec""".\
splitlines()))

    def test_traceroute_vrf(self):
        r = self.c.traceroute('192.0.0.5', vrf='MG501', probe=30)
        self.maxDiff = None
        self.assertEqual(r.strip(), "\r\n".join("""traceroute vrf MG501
Protocol [ip]: 
Target IP address: 192.0.0.5
Ingress traceroute [n]: 
Source address or interface: 
DSCP Value [0]: 
Numeric display [n]: 
Timeout in seconds [3]: 
Probe count [3]: 30
Minimum Time to Live [1]: 
Maximum Time to Live [30]: 
Port Number [33434]: 
Loose, Strict, Record, Timestamp, Verbose[none]: 
Type escape sequence to abort.
Tracing the route to 192.0.0.5
VRF info: (vrf in name/id, vrf out name/id)
  1 192.0.0.5 msec *  1 msec""".\
splitlines()))


class TestIosXEluginBashService(unittest.TestCase):

    def test_bash(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state isr_exec --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.bash_console() as console:
            console.execute('ls')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_asr(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state asr_exec --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.bash_console() as console:
            console.execute('df /bootflash/')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_standby(self):
        c = Connection(hostname='R1',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname R1'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.bash_console(switch='standby', rp='active') as console:
            console.execute('ls')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('R1#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_chassis_active(self):
        c = Connection(hostname='WLC1',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname WLC1'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True)
        with c.bash_console(chassis='active r0') as console:
            console.execute('ls')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('WLC1#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_chassis_standby(self):
        c = Connection(hostname='WLC1',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname WLC1'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True)
        with c.bash_console(chassis='standby r0') as console:
            console.execute('ls')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('WLC1#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_disable_selinux(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.bash_console(disable_selinux=True) as console:
            self.assertIn('[Router_RP_0:/]$', c.spawn.match.match_output)
            console.execute('df /bootflash/')
        self.assertIn('set platform software selinux default', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_disable_selinux_invalid_cmds(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state enable_isr --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.bash_console(disable_selinux=True) as console:
            self.assertIn('[Router:/]$', c.spawn.match.match_output)
            console.execute('ls')
        self.assertIn('set platform software selinux default', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_bash_parse(self):
        testbed = '''
            devices:
                R1:
                    os: iosxe
                    connections:
                        defaults:
                            class: 'unicon.Unicon'
                        cli:
                            command: mock_device_cli --os iosxe --state general_enable --hostname R1
        '''
        tb = loader.load(testbed)
        dev = tb.devices.R1
        try:
            dev.connect(mit=True, log_buffer=True)
            with dev.bash_console() as console:
                output = console.parse('ls -l')
            expected_output = {
                'files': {'bin': {'day': 10,
                    'filename': 'bin',
                    'group': 'root',
                    'linked_filename': 'usr/bin',
                    'links': 1,
                    'mode': 'lrwxrwxrwx.',
                    'month': 'Sep',
                    'size': 7,
                    'user': 'root',
                    'year': 2024},
                'boot': {'day': 9,
                        'filename': 'boot',
                        'group': 'root',
                        'hour': 20,
                        'links': 2,
                        'minute': 41,
                        'mode': 'drwxr-xr-x.',
                        'month': 'Jan',
                        'size': 60,
                        'user': 'root'}},
                'total': 55000
            }
            self.assertEqual(output, expected_output)
        finally:
            dev.disconnect()


class TestIosXESDWANConfigure(unittest.TestCase):

    def test_config_transaction(self):
        d = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state sdwan_enable --hostname Router'],
                       os='iosxe', platform='sdwan',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )

        d.connect()
        d.configure('no logging console')
        d.disconnect()

    def test_config_transaction_sdwan_iosxe(self):
        d = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state sdwan_enable --hostname Router'],
                       os='sdwan', platform='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )

        d.connect()
        d.configure('no logging console')
        d.disconnect()

    def test_config_transaction_sdwan_iosxe_confirm(self):
        d = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state sdwan_enable2 --hostname Router'],
                       os='iosxe', platform='sdwan',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True,
                       mit=True
                       )

        d.connect()
        d.configure('no logging console')
        d.disconnect()

class TestIosXEC8KVPlugin(unittest.TestCase):
    def test_connect(self):
        d = Connection(hostname="switch",
                       start=["mock_device_cli --os iosxe --state c8kv_rommon --hostname switch"],
                       os="iosxe",
                       platform="cat8k",
                       log_buffer=True)
        d.connect()
        d.disconnect()

class TestIosXEC8KvPluginReload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Connection(
            hostname='switch',
            start=['mock_device_cli --os iosxe --state c8kv_exec --hostname switch'],
            os='iosxe',
            platform='c8kv',
            credentials=dict(default=dict(
                username='cisco', password='cisco'),
                alt=dict(
                username='admin', password='lab')),
            log_buffer=True
            )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
         cls.c.disconnect()

    def test_reload(self):
        self.c.settings.POST_RELOAD_WAIT = 1
        self.c.reload(grub_boot_image='GOLDEN')

    def test_rommon(self):
        self.c.rommon(config_register="0x40")

class TestIosXECat9kPluginReload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(
            hostname='switch',
            start=['mock_device_cli --os iosxe --state general_enable --hostname switch'],
            os='iosxe',
            platform='cat9k',
            credentials=dict(default=dict(
                username='cisco', password='cisco', enable_password='Secret12345')),
            log_buffer=True,
            mit=True
            )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
         cls.c.disconnect()

    def test_reload1(self):
         self.c.reload(reload_command='reload1', post_reload_wait_time=1)
         self.assertEqual(self.c.reload.post_reload_wait_time, 1)

class TestIosXECat3kPluginReload(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(
            hostname='switch',
            start=['mock_device_cli --os iosxe --state cat3k_exec --hostname switch'],
            os='iosxe',
            platform='cat3k',
            credentials=dict(default=dict(
                username='cisco', password='cisco'),
                alt=dict(
                username='admin', password='lab')),
            log_buffer=True
            )

        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
         cls.c.disconnect()
    def test_reload(self):
        self.c.reload()


class TestIosXEDiol(unittest.TestCase):

    def test_connection(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state standby_exec --hostname Router'],
                       os='iosxe',
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(
                       username='cisco', password='cisco'),
                       alt=dict(
                       username='admin', password='lab')),
                       log_buffer=True
                       )

        c.connect()
        c.disconnect()

    def test_connection_diol_exec(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state diol_exec --hostname RouterRP'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(
                       username='cisco', password='cisco'),
                       alt=dict(
                       username='admin', password='lab')),
                       log_buffer=True
                       )

        c.connect()
        c.disconnect()

    def test_connection_diol_enable(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state diol_enable --hostname RouterRP'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(
                       username='cisco', password='cisco'),
                       alt=dict(
                       username='admin', password='lab')),
                       log_buffer=True
                       )

        c.connect()
        c.disconnect()

    def test_connection_diol_disable(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state diol_disable --hostname RouterRP'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(
                       username='cisco', password='cisco'),
                       alt=dict(
                       username='admin', password='lab')),
                       log_buffer=True
                       )

        c.connect()
        c.disconnect()


class TestIosXEConfigure(unittest.TestCase):

    def test_configure_are_you_sure_ywtdt(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname RouterRP'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        c.configure(['crypto pki trustpoint test', 'no crypto pki trustpoint test'])
        c.disconnect()

    def test_configure_error_pattern(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname RouterRP'],
                       os='iosxe',
                       init_exec_commands=[],
                       log_buffer=True
                       )
        c.connect()
        for cmd in ['ntp server vrf foo 1.2.3.4']:
          with self.assertRaises(SubCommandFailure) as err:
              r = c.configure(cmd)
        c.disconnect()

    def test_configure_with_msgs(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='config_with_msgs')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco')),
            mit=True,
        )
        try:
            c.connect()
            c.configure('msg')
        finally:
            c.disconnect()
            md.stop()

    def test_configure_with_msgs2(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='config_with_msgs2')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco')),
            mit=True
        )
        try:
            c.connect()
            c.configure('msg')
        finally:
            c.disconnect()
            md.stop()

    def test_config_locked(self):
        c = Connection(hostname='RouterRP',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname RouterRP'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()

        c.execute('set config lock count 2')
        c.settings.CONFIG_LOCK_RETRIES = 0
        c.settings.CONFIG_LOCK_RETRY_SLEEP = 0

        with self.assertRaises(StateMachineError):
            c.configure('')

        c.execute('set config lock count 2')
        with self.assertRaises(StateMachineError):
            c.configure('', lock_retries=1, lock_retry_sleep=1)

        c.execute('set config lock count 3')
        c.settings.CONFIG_LOCK_RETRIES = 1
        c.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        with self.assertRaises(StateMachineError):
            c.configure('')

        c.execute('set config lock count 3')
        c.settings.CONFIG_LOCK_RETRIES = 5
        c.settings.CONFIG_LOCK_RETRY_SLEEP = 1
        c.configure('')

        c.disconnect()

    def test_slow_config_mode(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state slow_config_mode --hostname Switch'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        c.configure(['no logging console'])
        c.disconnect()

    def test_slow_config_mode2(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state slow_config_mode2 --hostname Switch'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True,
                       settings=dict(CONFIG_TIMEOUT=10),
                       debug=True
                       )
        c.connect()
        c.configure(['no logging console'])
        c.disconnect()

    def test_slow_config_lock(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='config_locked')
        md.start()

        c = Connection(
            hostname='Router',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            mit=True,
            log_buffer=True,
        )
        try:
            c.connect()
            c.settings.CONFIG_TIMEOUT=5
            c.settings.CONFIG_LOCK_RETRY_SLEEP=3
            c.configure(['no logging console'])
        finally:
            c.disconnect()
            md.stop()

    def test_config_no_service_prompt_config(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state enable_no_service_prompt_config --hostname Switch'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        c.configure(['no logging console'])
        c.disconnect()

    def test_configure_host_list(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state general_enable'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        try:
            c.configure(['ip host-list host1'])
        finally:
            c.disconnect()


    def test_configure_macro(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state general_enable'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        cfg = [
            "macro auto execute TEST {",
            "if [[ $LINKUP == YES ]]",
            "then conf t",
            "end",
            "fi",
            "}"
        ]
        try:
            c.configure(cfg)
        finally:
            c.disconnect()

    def test_configure_trailing_prompt_stripping(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state general_enable'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        config_service = c.configure

        con_state = 'config'
        pattern = re.compile(c.state_machine.get_state('config').pattern, flags=re.S)

        output = 'help\r\nSwitch(ca-trustpoint)#'

        result = output
        result_match = ExpectMatch()
        result_match.last_match = pattern.match(output)
        result_match.last_match_index = 1
        result_match.last_match_mode = MatchMode(mode_id=1, mode_name='search only last line')
        result_match.match_output = output

        new_result = config_service.utils.truncate_trailing_prompt(
            con_state,
            result,
            hostname='Switch',
            result_match=result_match
        )
        self.assertEqual(new_result, 'help\r\n')

        new_result = config_service.utils.truncate_trailing_prompt(
            con_state,
            result,
            hostname='PE1',
            result_match=result_match
        )
        self.assertEqual(new_result, 'help\r\nSwitch(ca-trustpoint)#')

    def test_configure_wsma_agent_exec(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state general_enable'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True
                       )
        c.connect()
        c.configure('wsma agent exec')
        c.disconnect()

    def test_configure_pki_hexmode(self):
        c = Connection(hostname='Switch',
                       start=['mock_device_cli --os iosxe --state general_enable'],
                       os='iosxe',
                       mit=True,
                       init_exec_commands=[],
                       init_config_commands=[],
                       log_buffer=True,
                       )
        try:
            c.connect()
            c.configure(['crypto pki certificate chain SLA-TrustPoint', 'certificate ca 01'])
        finally:
            c.disconnect()
class TestIosXEEnableSecret(unittest.TestCase):

    def test_enable_secret(self):
        c = Connection(hostname='R1',
                       start=['mock_device_cli --os iosxe --state initial_config_dialog --hostname R1'],
                       os='iosxe',
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(password='Secret12345')),
                       log_buffer=True
                       )
        c.connect()
        c.configure(['no logging console'])
        c.disconnect()

    def test_bad_enable_secret(self):
        c = Connection(hostname='R1',
                       start=['mock_device_cli --os iosxe --state initial_config_dialog --hostname R1'],
                       os='iosxe',
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(password='veryverybadpw')),
                       log_buffer=True
                       )
        with self.assertRaisesRegex(UniconAuthenticationError, 'Too many enable password retries'):
            c.connect()
        c.disconnect()

    def test_enable_secret_topology_legacy(self):
        tb = loader.load("""
        devices:
          R1:
            os: iosxe
            passwords:
                enable: Secret12345
            connections:
              cli:
                command: mock_device_cli --os iosxe --state initial_config_dialog --hostname R1
                arguments:
                  log_buffer: True
                  init_exec_commands: []
                  init_config_commands: []
        """)
        dev = tb.devices.R1
        dev.connect()
        dev.disconnect()

    def test_enable_secret_topology(self):
        tb = loader.load("""
        devices:
          R1:
            os: iosxe
            credentials:
              default:
                password: Secret12345
            connections:
              cli:
                command: mock_device_cli --os iosxe --state initial_config_dialog --hostname R1
                arguments:
                  log_buffer: True
                  init_exec_commands: []
                  init_config_commands: []
        """)
        dev = tb.devices.R1
        try:
            output = dev.connect()
            self.assertIn('Enter your selection [2]: 2\r\n', output)
        finally:
            dev.disconnect()

    def test_enable_secret_no_password(self):
        self.maxDiff = None
        c = Connection(hostname='R1',
                       start=['mock_device_cli --os iosxe --state initial_config_dialog --hostname R1'],
                       os='iosxe',
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(password='')),
                       log_buffer=True
                       )
        try:
            output = c.connect()
            self.assertIn('Enter your selection [2]: \n0', output)
        finally:
            c.disconnect()

    def test_enable_secret_short_password(self):
        self.maxDiff = None
        c = Connection(hostname='R1',
                       start=['mock_device_cli --os iosxe --state initial_config_dialog --hostname R1'],
                       os='iosxe',
                       init_exec_commands=[],
                       init_config_commands=[],
                       credentials=dict(default=dict(password='lab')),
                       log_buffer=True
                       )
        try:
            output = c.connect()
            self.assertIn('Enter your selection [2]: \n0', output)
        finally:
            c.disconnect()


class TestIosXEluginGuestShellService(unittest.TestCase):

    def test_guestshell(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.guestshell() as console:
            output = console.execute('pwd')
            self.assertEqual(output, '/home/guestshell')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_guestshell_activate(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state general_enable --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True
                       )
        with c.guestshell(enable_guestshell=True) as console:
            output = console.execute('pwd')
            self.assertEqual(output, '/home/guestshell')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

    def test_guestshell_activate_configure(self):
        c = Connection(hostname='Router',
                       start=['mock_device_cli --os iosxe --state enable_guestshell --hostname Router'],
                       os='iosxe',
                       credentials=dict(default=dict(username='cisco', password='cisco')),
                       log_buffer=True,
                       mit=True
                       )
        with c.guestshell(enable_guestshell=True) as console:
            output = console.execute('pwd')
            self.assertEqual(output, '/home/guestshell')
        self.assertIn('exit', c.spawn.match.match_output)
        self.assertIn('Router#', c.spawn.match.match_output)
        c.disconnect()

class TestIosXEping(unittest.TestCase):

    def test_ping_failed_protocol(self):
        md = MockDeviceTcpWrapperIOSXE(hostname='PE1', port=0, state='ping_fail')
        md.start()

        c = Connection(
            hostname='PE1',
            start=['telnet 127.0.0.1 {}'.format(md.ports[0])],
            os='iosxe',
            connection_timeout=10,
            mit=True
        )
        try:
            c.connect()
            try:
                c.ping('10.10.10.10')
            except Exception:
                pass
            c.configure()
        except Exception:
            raise
        finally:
            c.disconnect()
            md.stop()


class TestSyslogHandler(unittest.TestCase):

    def test_syslog_handler_timeout(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state endless_syslog --hostname PE1'],
            os='iosxe',
            connection_timeout=5,
            settings=dict(PROMPT_RECOVERY_COMMANDS = ['\x06']),
            prompt_recovery=True
        )
        try:
            c.connect()
        except Exception:
            raise
        finally:
            c.disconnect()

    def test_syslog_handler_error_opening_pattern(self):
        d = Connection(
            hostname='Router',
            start=['mock_device_cli --os iosxe --state error_opening_syslog --hostname Router'],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco')),
            log_buffer=True
        )

        d.connect()
        d.disconnect()

    def test_syslog_handler_guestshell(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state guestshell_prompt_obscure_enable --hostname PE1'],
            os='iosxe',
            mit=True,
        )
        try:
            c.connect()
            c.execute('show version')
        except Exception:
            raise
        finally:
            c.disconnect()
    
    def test_handler_ddns_pattern(self):
        d = Connection(
            hostname='Router',
            start=['mock_device_cli --os iosxe --state ip_ddns_update_method --hostname Router'],
            os='iosxe',
            credentials=dict(default=dict(username='cisco', password='cisco')),
            log_buffer=True
        )

        d.connect()
        d.disconnect()


class TestIosxeAsr1k(unittest.TestCase):
    def test_connect_asr1k_ha(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='ha_asr1k_exec,ha_asr1k_stby_exec', hostname='R1')
        md.start()

        c = Connection(
            hostname='R1',
            start=[
                'telnet 127.0.0.1 {}'.format(md.ports[0]),
                'telnet 127.0.0.1 {}'.format(md.ports[1])
            ],
            os='iosxe',
            connection_timeout=10,
            mit=True
        )
        try:
            c.connect()
        except Exception:
            raise
        finally:
            c.disconnect()
            md.stop()

    def test_connect_asr1k_ha_rommon(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='ha_asr1k_exec,ha_asr1k_stby_exec', hostname='R1')
        md.start()

        c = Connection(
            hostname='R1',
            start=[
                'telnet 127.0.0.1 {}'.format(md.ports[0]),
                'telnet 127.0.0.1 {}'.format(md.ports[1])
            ],
            os='iosxe',
            connection_timeout=10,
            credentials=dict(default=dict(password='lab'))
        )
        try:
            c.connect()
            c.execute('reload_to_rommon')
            c.rommon()
            c.enable(target='active')
            c.enable(target='standby')
        except Exception:
            raise
        finally:
            c.disconnect()
            md.stop()

    def test_connect_asr1k_ha_rommon_boot_image(self):
        md = MockDeviceTcpWrapperIOSXE(port=0, state='ha_asr1k_exec,ha_asr1k_stby_exec', hostname='R1')
        md.start()

        c = Connection(
            hostname='R1',
            start=[
                'telnet 127.0.0.1 {}'.format(md.ports[0]),
                'telnet 127.0.0.1 {}'.format(md.ports[1])
            ],
            os='iosxe',
            connection_timeout=10,
            credentials=dict(default=dict(password='lab'))
        )
        try:
            c.connect()
            c.execute('reload_to_rommon')
            c.rommon()
            c.enable(target='active', image='test/packages.conf')
            c.enable(target='standby', image='test/packages.conf')

            c.execute('reload_to_rommon')
            c.rommon()
            c.enable(target='active', image_to_boot='test/packages.conf')
            c.enable(target='standby', image_to_boot='test/packages.conf')
        except Exception:
            raise
        finally:
            c.disconnect()
            md.stop()


class TestIosxeTclsh(unittest.TestCase):

    def test_tclsh(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state general_enable --hostname PE1'],
            os='iosxe',
            mit=True
        )
        c.connect()
        c.tclsh()
        c.enable()
        c.disconnect()

    def test_tclsh_long_hostname(self):
        c = Connection(
            hostname='very-very-long-hostname',
            start=['mock_device_cli --os iosxe --state general_enable --hostname very-very-long-hostname'],
            os='iosxe',
            mit=True
        )
        c.connect()
        c.execute('long_hostname')
        c.tclsh()
        c.enable()
        c.disconnect()

class TestConfigTransition(unittest.TestCase):

    def test_config_transition_setting(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state general_enable --hostname PE1'],
            os='iosxe',
            mit=True
        )
        c.connect()
        self.assertEqual(c.settings.CONFIG_TRANSITION_WAIT, 0.2)
        self.assertEqual(c.spawn.settings.CONFIG_TRANSITION_WAIT, 0.2)
        c.configure()
        c.settings.CONFIG_TRANSITION_WAIT = 1
        c.configure()
        self.assertEqual(c.settings.CONFIG_TRANSITION_WAIT, 1)
        self.assertEqual(c.spawn.settings.CONFIG_TRANSITION_WAIT, 1)
        c.disconnect()

    def test_config_transition_learn_hostname(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state enable_slow_config --hostname PE1'],
            os='iosxe',
            mit=True
        )
        c.connect()
        # Force hostname learning to be enabled so default prompt pattern is used
        # This was causing issues and should not fail with this test
        c.state_machine.learn_hostname = True
        c.configure()


class TestRommonCommands(unittest.TestCase):

    def test_rommon_command_false_prompt_avoidance(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state rommon_command_output_not_a_prompt --hostname PE1'],
            os='iosxe',
            learn_hostname=True,
            credentials=dict(default=dict(username='cisco', password='cisco')),
            settings={'ROMMON_INIT_COMMANDS': ['notaprompt'], 'EXECUTE_STATE_CHANGE_MATCH_RETRY_SLEEP': 3}
        )
        try:
            c.connect()
        finally:
            c.disconnect()

    def test_rommon_command_false_prompt(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state rommon_command_output_not_a_prompt2 --hostname PE1'],
            os='iosxe',
            learn_hostname=True,
            credentials=dict(default=dict(username='cisco', password='cisco')),
            settings={
                'ROMMON_INIT_COMMANDS': ['notaprompt'],
                'EXECUTE_STATE_CHANGE_MATCH_RETRIES': 0,
                'EXECUTE_STATE_CHANGE_MATCH_RETRY_SLEEP': 1
            },
            debug=True
        )
        with self.assertRaisesRegex(UniconConnectionError,
            "Expected device to reach 'rommon' state, but landed on 'enable' state."):
            try:
                c.connect()
            finally:
                c.disconnect()


class TestCopy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state general_enable --hostname PE1'],
            os='iosxe',
            mit=True
        )
        cls.c.connect()

    @classmethod
    def tearDownClass(cls):
        cls.c.disconnect()

    def test_copy(self):
        self.c.copy(source='test.cfg', dest='running-config')

    def test_copy_abort_n(self):
        self.c.copy(source='somefile.bin', dest='flash:')


class TestMaintenanceMode(unittest.TestCase):

    def test_maintenance_mode_context_manager(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state general_enable --hostname PE1'],
            os='iosxe',
            mit=True
        )
        c.connect()
        c.settings.MAINTENANCE_MODE_WAIT_TIME = 1
        c.settings.MAINTENANCE_MODE_TIMEOUT = 10
        with c.maintenance_mode() as m:
            output = m.execute('help')
            self.assertEqual(output, 'help')
        c.disconnect()

    def test_switchto_maintenance(self):
        c = Connection(
            hostname='PE1',
            start=['mock_device_cli --os iosxe --state general_enable --hostname PE1'],
            os='iosxe',
            mit=True
        )
        c.connect()
        c.settings.MAINTENANCE_MODE_WAIT_TIME = 1
        c.settings.MAINTENANCE_MODE_TIMEOUT = 10
        c.switchto('maintenance')
        c.switchto('enable')
        c.disconnect()



if __name__ == "__main__":
    unittest.main()
