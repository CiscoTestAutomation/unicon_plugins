__author__ = 'Difu Hu <pyats-support@cisco.com;pyats-support-ext@cisco.com>'

import unittest

from unicon import Connection
from unicon.mock.mock_device import MockDevice
from unicon.core.errors import SubCommandFailure


class TestSrosPlugin(unittest.TestCase):

    def setUp(self):
        self.md = MockDevice(device_os='sros', state='execute')
        self.joined = lambda string: '\n'.join(string.splitlines())
        self.con = Connection(
            os='sros',
            hostname='Router',
            start=['mock_device_cli --os sros --state connect_ssh'],
            credentials={'default': {'username': 'grpc', 'password': 'nokia'}}
        )
        self.con.connect()

    def test_connect(self):
        self.assertIn('Router#', self.con.spawn.match.match_output)

    def test_mdcli_execute(self):
        cmd = 'show router interface coreloop'
        output = self.con.mdcli_execute(cmd)
        expect = self.md.mock_data['mdcli_execute']['commands'][cmd]
        self.assertEqual(self.joined(output), self.joined(expect))

    def test_mdcli_1_execute(self):
        cmd = "show port description"
        out = self.con.mdcli_execute(cmd)
        expect = self.md.mock_data['mdcli_execute']['commands'][cmd]
        self.assertEqual(self.joined(out), self.joined(expect))

    def test_mdcli_configure(self):
        cmd = 'router interface coreloop ipv4 primary address 1.1.1.1 prefix-length 32'
        output = self.con.mdcli_configure(cmd, mode='global')
        expect = self.md.mock_data['mdcli_configure_global']['commands'][cmd]
        # self.assertIn(self.joined(expect), self.joined(output))

#    def test_mdcli_configure_commit_fail(self):
#        cmd = 'router interface coreloop ipv4 primary address 2.2.2.2 prefix-length 32'
#        output = self.con.mdcli_configure(cmd)
#        expect = self.md.mock_data['mdcli_configure_private']['commands'][cmd]
#        commit = self.md.mock_data['mdcli_configure_private']['commands']['commit']
#        self.assertIn(self.joined(expect), self.joined(output))
#        self.assertIn(self.joined(commit), self.joined(output))

    def test_classiccli_execute(self):
        cmd = 'show router interface coreloop'
        output = self.con.classiccli_execute(cmd)
        expect = self.md.mock_data['classiccli_execute']['commands'][cmd]
        self.assertEqual(self.joined(output), self.joined(expect))

    def test_classiccli_configure(self):
        cmd = 'configure router interface coreloop address 111.1.1.1 255.255.255.255'
        output = self.con.classiccli_configure(cmd)
        expect = self.md.mock_data['classiccli_execute']['commands'][cmd]['response']
        self.assertIn(self.joined(expect), self.joined(output))

    def test_execute_and_cli_engine(self):
        self.con.switch_cli_engine('classiccli')
        engine = self.con.get_cli_engine()
        self.assertEqual(engine, 'classiccli')
        cmd = 'show router interface coreloop'
        output = self.con.execute(cmd)
        expect = self.md.mock_data['classiccli_execute']['commands'][cmd]
        self.assertEqual(self.joined(output), self.joined(expect))

        self.con.switch_cli_engine('mdcli')
        engine = self.con.get_cli_engine()
        self.assertEqual(engine, 'mdcli')
        cmd = 'show router interface coreloop'
        output = self.con.execute(cmd)
        expect = self.md.mock_data['mdcli_execute']['commands'][cmd]
        self.assertEqual(self.joined(output), self.joined(expect))

    def test_configure_and_cli_engine(self):
        self.con.switch_cli_engine('mdcli')
        engine = self.con.get_cli_engine()
        self.assertEqual(engine, 'mdcli')
        self.con.mdcli_configure.mode = 'global'
        cmd = 'router interface coreloop ipv4 primary address 1.1.1.1 prefix-length 32'
        output = self.con.configure(cmd)
        expect = self.md.mock_data['mdcli_configure_global']['commands'][cmd]
        # self.assertIn(self.joined(expect), self.joined(output))

        self.con.switch_cli_engine('classiccli')
        engine = self.con.get_cli_engine()
        self.assertEqual(engine, 'classiccli')
        cmd = 'configure router interface coreloop address 111.1.1.1 255.255.255.255'
        output = self.con.configure(cmd)
        expect = self.md.mock_data['classiccli_execute']['commands'][cmd]['response']
        self.assertIn(self.joined(expect), self.joined(output))


class TestLearnHostname(unittest.TestCase):

    def test_connect_learn_hostname(self):
        con = Connection(
            os='sros',
            hostname='R1',
            start=['mock_device_cli --os sros --state classiccli_execute --hostname CR1-LOC-1'],
            credentials={'default': {'username': 'grpc', 'password': 'nokia'}},
            learn_hostname=True
        )
        con.connect()
        self.assertEqual(con.hostname, 'CR1-LOC-1')


class TestConnect(unittest.TestCase):

    def test_execute_before_connect(self):
        con = Connection(
            os='sros',
            hostname='Router',
            start=['mock_device_cli --os sros --state connect_ssh'],
            credentials={'default': {'username': 'grpc', 'password': 'nokia'}}
        )
        con.execute('show version')


class TestInitCommands(unittest.TestCase):

    def test_connect_classiccli_init_commands(self):
        con = Connection(
            os='sros',
            hostname='CR1-LOC-1',
            start=['mock_device_cli --os sros --state classiccli_execute --hostname CR1-LOC-1'],
            learn_hostname=True,
            settings=dict(DEFAULT_CLI_ENGINE='classiccli'),
            log_buffer=True
        )
        con.connect()
        for cmd in ["executing command 'environment no more'",
                    "executing command 'environment no saved-ind-prompt'"]:
            self.assertTrue(cmd in con.log_buffer)

    def test_connect_mdcli_init_commands(self):
        con = Connection(
            os='sros',
            hostname='CR1-LOC-1',
            start=['mock_device_cli --os sros --state mdcli_execute --hostname CR1-LOC-1'],
            learn_hostname=True,
            settings=dict(DEFAULT_CLI_ENGINE='mdcli'),
            log_buffer=True
        )
        con.connect()
        for cmd in ["executing command 'environment console length 512'",
                    "executing command 'environment console width 512'"]:
            self.assertTrue(cmd in con.log_buffer)


class TestClassisCliExecute(unittest.TestCase):
    def setUp(self):
        self.con = Connection(
            os='sros',
            hostname='Router',
            start=['mock_device_cli --os sros --state classiccli_execute'],
            settings=dict(DEFAULT_CLI_ENGINE='classiccli'),
            log_buffer=True
        )
        self.con.connect()
        self.joined = lambda string: '\n'.join(string.splitlines())
        self.md = MockDevice(device_os='sros', state='classiccli_execute')

    def test_execute(self):
        cmd = "show version"
        out = self.con.execute(cmd)
        expect = self.md.mock_data['classiccli_execute']['commands'][cmd]
        self.assertEqual(self.joined(out), self.joined(expect))

    def test_unsupported_execute(self):
        self.assertRaises(SubCommandFailure, self.con.execute, "show vresion")

    def tearDown(self):
        self.con.disconnect()


class TestClassicCliConfigure(unittest.TestCase):

    def setUp(self):
        self.con = Connection(
            os='sros',
            hostname='Router',
            start=['mock_device_cli --os sros --state classiccli_execute'],
            settings=dict(DEFAULT_CLI_ENGINE='classiccli'),
            log_buffer=True
        )
        self.con.connect()

    def test_configure_full(self):
        self.con.configure(["configure",
                            "lag 800",
                            "no shutdown",
                            "mode hybrid",
                            "access",
                            "adapt-qos link"])

    def test_configure_short(self):
        self.con.configure(["lag 800",
                            "no shutdown",
                            "mode hybrid",
                            "access",
                            "adapt-qos link"])

    def test_configure_unsupported(self):
        self.assertRaises(SubCommandFailure, self.con.configure, ["laag 800"])

    def tearDown(self):
        self.con.disconnect()


if __name__ == '__main__':
    unittest.main()
