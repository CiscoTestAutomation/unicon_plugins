'''
Tests for Unicon Gaia Plugin

Author: Sam Johnson
Contact: samuel.johnson@gmail.com
https://github.com/TestingBytes

Contents largely inspired by sample Unicon repo:
https://github.com/CiscoDevNet/pyats-plugin-examples/tree/master/unicon_plugin_example/src/unicon_plugin_example
'''

import os
import unittest
import yaml

from unicon import Connection
from unicon.mock.mock_device import mockdata_path

with open(os.path.join(mockdata_path, 'gaia/gaia_mock_data.yaml'), 'rb') as datafile:
    mock_data = yaml.safe_load(datafile.read())


class TestGaiaPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = Connection(hostname='gaia-gw',
                        start=['mock_device_cli --os gaia --state login'],
                        os='gaia',
                        credentials={
                            'default': {
                                'username': 'gaia-user', 
                                'password': 'gaia-password'
                                },
                            'expert': {
                                'password': 'gaia-expert-pass'
                                }
                            }
                        )

        cls.c.connect()

    def test_execute(self):
        response = self.c.execute('show version all')
        self.assertIn("Product version", response)

        # check hostname
        self.assertIn("gaia-gw", self.c.hostname)

    def test_ping(self):
        response = self.c.execute('ping 192.168.1.1')
        self.assertIn("PING 192.168.1.1 (192.168.1.1) 56(84) bytes of data.", response)

    def test_traceroute(self):
        response = self.c.execute('traceroute 192.168.1.1')
        self.assertIn("traceroute to 192.168.1.1 (192.168.1.1), 30 hops max, 40 byte packets", response)

    def test_state_transitions(self):
        sm = self.c.state_machine
        self.assertIn("clish", sm.current_state)

        self.c.switchto('expert')
        self.assertIn("expert", sm.current_state)

        self.c.switchto('clish')
        self.assertIn("clish", sm.current_state)

if __name__ == "__main__":
    unittest.main()
