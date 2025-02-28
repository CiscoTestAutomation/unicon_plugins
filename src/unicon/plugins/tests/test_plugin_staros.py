"""
Unittests for staros plugin

Uses the mock_device.py script to test the plugin.

"""

__author__ = "dwapstra"

import time
import unittest
from unittest.mock import patch

import unicon
from unicon import Connection
from unicon.core.errors import SubCommandFailure


@patch.object(unicon.settings.Settings, 'POST_DISCONNECT_WAIT_SEC', 0)
@patch.object(unicon.settings.Settings, 'GRACEFUL_DISCONNECT_WAIT_SEC', 0.2)
class TestStarosPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(hostname='host_name',
                           start=['mock_device_cli --os staros --state staros_connect'],
                           os='staros',
                           username='cisco',
                           tacacs_password='cisco',
                           connection_timeout=15)
        cls.c.connect()

    def test_execute(self):
        r = self.c.execute('')
        self.assertEqual(r, '')

        r = self.c.execute([''])
        self.assertEqual(r, '')

        r = self.c.execute(['']*2)
        self.assertEqual(r, ['', ''])

    def test_configure(self):
        r = self.c.configure('test\ntest123')
        self.assertEqual(r, {'test': '123', 'test123': 'abc'})

    def test_truncation_add_state_pattern(self):
        sm = self.c.state_machine.get_state('config')
        sm.add_state_pattern(r'^(.*?)(newpattern)*#\s?$')
        r = self.c.configure('test_command')
        self.assertEqual(r, 'executing test command')

    def test_exec_failure(self):
        with self.assertRaises(SubCommandFailure):
            self.c.execute('fail')

    def test_monitor(self):
        self.c.monitor('monitor subscriber next-call',
                       radius_dict='custom14',
                       gtpp_dict='custom11',
                       app_specific_diameter={'diabase': 'on'},
                       verbosity_level=3,
                       limit_context='local',
                       ppp='off')
        self.assertTrue(self.c.monitor.monitor_state['ppp']['state'] == 'off')
        self.assertTrue(self.c.monitor.monitor_state['radius_dict']['state'] == 'custom14')
        r = self.c.monitor.tail(timeout=10, return_on_match=True, stop_monitor_on_match=True)
        self.assertTrue('Call Finished - Waiting to trace next matching call' in r)


class TestStarosConnect(unittest.TestCase):

    def test_connect(self):
        c = Connection(hostname='host_name',
                       start=['mock_device_cli --os staros --state staros_connect2'],
                       os='staros',
                       username='cisco',
                       tacacs_password='cisco',
                       connection_timeout=15,
                       mit=True)
        try:
            c.connect()
        finally:
            c.disconnect()


if __name__ == "__main__":
    unittest.main()
