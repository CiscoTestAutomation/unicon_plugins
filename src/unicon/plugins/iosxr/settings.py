__author__ = "Syed Raza <syedraza@cisco.com>"

from unicon.plugins.generic.settings import GenericSettings

class IOSXRSettings(GenericSettings):

    def __init__(self):
        super().__init__()
        self.IOSXR_INIT_EXEC_COMMANDS = [
            'terminal length 0',
            'terminal width 0'
        ]
        self.IOSXR_INIT_CONFIG_COMMANDS = [
            'no logging console',
            'logging console disable',
            'line console',
            'exec-timeout 0 0',
            'absolute-timeout 0',
            'session-timeout 0',
            'line default',
            'exec-timeout 0 0',
            'absolute-timeout 0',
            'session-timeout 0'
        ]
        self.SWITCHOVER_TIMEOUT = 700
        self.SWITCHOVER_COUNTER = 50

        self.INITIAL_LAUNCH_DISCOVERY_WAIT_SEC = 2
        self.INITIAL_DISCOVERY_RETRIES = 3

        self.RELOAD_TIMEOUT = 400
        self.RELOAD_WAIT = 60
        # number of retries to reconnect after reloading
        self.RELOAD_RECONNECT_ATTEMPTS = 3

        self.STANDBY_STATE_REGEX = r'Backup node .* is (.*)'
        self.STANDBY_EXPECTED_STATE = ['ready', 'NSR-ready']
        self.STANDBY_STATE_INTERVAL = 15
        self.ERROR_PATTERN = [
            r'^%\s*Failed to commit.*',
            r'^%\s*[Ii]nvalid (command|input).*',
            r'^%\s*[Ii]ncomplete (command|input).*',
            r'^%\s*[Aa]mbiguous (command|input).*',
            r'^%\s*Unmatched +quote.*',
            r'^%\s*Error +parsing +piping+ string\. +Quitting.*'
        ]
        self.CONFIGURE_ERROR_PATTERN = [
            r'^%\s*[Ii]nvalid (command|input|number)',
            r'^%\s*Failed to commit.*'
        ]

        self.HA_STANDBY_UNLOCK_COMMANDS = []

        self.EXECUTE_MATCHED_RETRIES = 1
        self.EXECUTE_MATCHED_RETRY_SLEEP = 0.1

        self.CONFIG_LOCK_RETRIES = 5
        self.CONFIG_LOCK_RETRY_SLEEP = 30

        self.SHOW_REDUNDANCY_CMD = 'show redundancy | inc ^Node'
        self.REDUNDANCY_STATE_PATTERN = r'^Node \S+ is in (.*?) role'

        self.SHOW_CONFIG_FAILED_CMD = 'show configuration failed'
        self.UNICON_BACKEND_DECODE_ERROR_LIMIT = 10

        # more prompt pattern is defined in plugins/iosxr/patterns.py as more_prompt
        self.MORE_REPLACE_PATTERN = r'( *--\s?[Mm]ore\s?-- *|\(END\))'
