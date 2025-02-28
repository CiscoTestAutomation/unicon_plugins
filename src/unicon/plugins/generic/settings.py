"""
Module:
    unicon.plugins.generic

Authors:
    pyATS TEAM (pyats-support@cisco.com, pyats-support-ext@cisco.com)

Description:
  This module defines the Generic settings to setup
  the unicon environment required for generic based
  unicon connection
"""
from unicon.settings import Settings
from unicon.plugins.generic.patterns import GenericPatterns

genpat = GenericPatterns()


class GenericSettings(Settings):
    """" Generic platform settings """
    def __init__(self):
        """ initialize
        """
        super().__init__()
        self.HA_INIT_EXEC_COMMANDS = [
            'term length 0',
            'term width 0',
            'show version'
        ]
        self.HA_INIT_CONFIG_COMMANDS = [
            'no logging console',
            'line console 0',
            'exec-timeout 0',
            'line vty 0 4',
            'exec-timeout 0'
        ]
        self.HA_STANDBY_UNLOCK_COMMANDS = [
            'redundancy',
            'main-cpu',
            'standby console enable'
        ]
        self.BASH_INIT_COMMANDS = [
            'stty cols 200',
            'stty rows 200'
        ]
        self.ROMMON_INIT_COMMANDS = []

        self.SWITCHOVER_COUNTER = 50
        self.SWITCHOVER_TIMEOUT = 500
        self.HA_RELOAD_TIMEOUT = 500
        self.RELOAD_TIMEOUT = 300
        self.RELOAD_WAIT = 240
        self.POST_RELOAD_WAIT = 60
        self.RELOAD_RECONNECT_ATTEMPTS = 3
        self.CONSOLE_TIMEOUT = 60
        self.BOOT_TIMEOUT = 600
        self.MAX_BOOT_ATTEMPTS = 3
        self.CONNECTION_REFUSED_MAX_COUNT = 3

        # Temporary enable secret used during setup
        # this is used if no password is available
        # and would not be saved by default
        self.TEMP_ENABLE_SECRET = 'Secret12345'
        # Minimum length for enable secret password:
        # if the password specified is shorter,
        # use the TEMP_ENABLE_SECRET instead.
        self.ENABLE_SECRET_MIN_LENGTH = 10

        # for rommon boot, try to find image on flash
        self.FIND_BOOT_IMAGE = True
        self.BOOT_FILESYSTEM = 'bootflash:'
        self.BOOT_FILE_REGEX = r'(\S+\.bin)'

        # Wait for the config prompt to appear
        # before checking for the config prompt.
        # This may need to be adjusted if the RTT between
        # the execution host and lab device is high.
        self.CONFIG_TRANSITION_WAIT = 0.2

        # If learn_hostname is requested but no hostname was actually learned,
        # substitute this default hostname when occurances of HOSTNAME_SUBST_PAT
        # occur in state patterns.
        self.DEFAULT_LEARNED_HOSTNAME = r'([^# \t\n\r\f\v\(\)]+)'

        # Pattern to avoid sending 'enter' after Escape character pattern is seen
        self.ESCAPE_CHAR_PROMPT_PATTERN = r'.*(User Access Verification|sername:\s*$|assword:\s*$|login:\s*$|The highlighted entry will)'

        # When connecting to a device via telnet, how long (in seconds)
        # to pause before checking the spawn buffer
        self.ESCAPE_CHAR_CHATTY_TERM_WAIT = 0.5

        # number of cycles to wait for if the terminal is still chatty
        self.ESCAPE_CHAR_CHATTY_TERM_WAIT_RETRIES = 6

        # prompt wait delay
        self.ESCAPE_CHAR_PROMPT_WAIT = 1

        # prompt wait retries
        # (wait time: 0.5, 1, 1.5, 2, 2.5, 3, 3.5 == total wait: 14.0s)
        self.ESCAPE_CHAR_PROMPT_WAIT_RETRIES = 7

        # syslog message handling timers
        self.SYSLOG_WAIT = 1
        # syslog wait time for reload service
        self.RELOAD_SYSLOG_WAIT = 10

        # pattern to replace "more" string
        # command to continue for more_prompt_stmt
        # when changing MORE_REPLACE_PATTERN, please also change unicon/patterns.py more_prompt
        self.MORE_REPLACE_PATTERN = r' *--\s?[Mm]ore\s?-- *'
        self.MORE_CONTINUE = ' '

        # Sometimes a copy operation can fail due to network issues,
        # so copy at most this many times.
        self.MAX_COPY_ATTEMPTS = 2
        self.COPY_INTERRUPT = '\x03'

        # If configuration mode cannot be entered on a newly reloaded device
        # because HA sync is in progress, wait this many times and for this long
        self.CONFIG_POST_RELOAD_MAX_RETRIES = 20
        self.CONFIG_POST_RELOAD_RETRY_DELAY_SEC = 9

        self.GUESTSHELL_RETRIES = 20
        self.GUESTSHELL_RETRY_SLEEP = 5

        self.SHOW_REDUNDANCY_CMD = 'sh redundancy stat | inc my state'
        self.REDUNDANCY_STATE_PATTERN = r'my state = (.*?)\s*$'

        # Default error pattern
        self.ERROR_PATTERN = [r"% Invalid command at",
                              r"% Invalid input detected at",
                              r"% String is invalid, 'all' is not an allowed string at",
                              r"Incomplete command",
                              r'% Unrecognized host or address.',
                              r'Error: Could not open file .*',
                              r'Unable to deactivate Capture.',
                              ]
        self.CONFIGURE_ERROR_PATTERN = [r"overlaps with",
                                        r"% Class-map .* is being used",
                                        r'% ?Insertion failed .*',
                                        r'%Failed to add ace to access-list'
                                        r'Insufficient bandwidth .*',
                                        r'BGP is already running; AS is .*',
                                        r'% Failed to commit one or more configuration items.*',
                                        r'% Configuring IP routing on a LAN subinterface is only allowed if that '
                                        r'subinterface is already configured as part of an IEEE 802.10, IEEE 802.1Q, '
                                        r'or ISL vLAN.',
                                        r'% OSPF: Please enable segment-routing globally',
                                        r"% Invalid input detected at '^' marker"
                                        ]

        # Number of times to retry for config mode by configure service.
        self.CONFIG_LOCK_RETRIES = 3
        self.CONFIG_LOCK_RETRY_SLEEP = 10

        # for bulk configure
        self.BULK_CONFIG = False
        self.BULK_CONFIG_END_INDICATOR = '!end indicator for bulk configure'
        self.BULK_CONFIG_CHUNK_LINES = 50
        self.BULK_CONFIG_CHUNK_SLEEP = 0.5

        # for execute matched retry on statement pattern
        self.EXECUTE_MATCHED_RETRIES = 1
        self.EXECUTE_MATCHED_RETRY_SLEEP = 0.05

        # for configure matched retry on statement pattern
        self.CONFIGURE_MATCHED_RETRIES = 1
        self.CONFIGURE_MATCHED_RETRY_SLEEP = 0.05

        # execute statement match retry for state change patterns
        self.EXECUTE_STATE_CHANGE_MATCH_RETRIES = 1
        self.EXECUTE_STATE_CHANGE_MATCH_RETRY_SLEEP = 3

        # User defined login and password prompt pattern.
        self.LOGIN_PROMPT = None
        self.PASSWORD_PROMPT = None

        # Maximum number of retries for password handler
        self.PASSWORD_ATTEMPTS = 3

        # Ignore log messages before executing command
        self.IGNORE_CHATTY_TERM_OUTPUT = False

        # How long to wait for config sync after an HA reload.
        self.POST_HA_RELOAD_CONFIG_SYNC_WAIT = 400

        self.DEFAULT_HOSTNAME_PATTERN = genpat.default_hostname_pattern

        # Traceroute error Patterns
        self.TRACEROUTE_ERROR_PATTERN = [\
                              '^.*(% )?DSCP.*does not match any topology',
                              'Bad IP (A|a)ddress', 'Ping transmit failed',
                              'Invalid vrf', 'Unable to find',
                              'No Route to Host.*',
                              'Destination Host Unreachable',
                              'Unable to initialize Windows Socket Interface',
                              'IP routing table .* does not exist',
                              'Invalid input',
                              'Unknown protocol -',
                              'bad context', 'Failed to resolve',
                              '(U|u)nknown (H|h)ost']

        # Overwite testbed tokens during token discovery
        self.LEARN_DEVICE_TOKENS = False
        self.OVERWRITE_TESTBED_TOKENS = False

        self.LEARN_OS_COMMANDS = [
            'show version',
            'uname',
        ]

        self.OS_MAPPING = {
            'nxos': {
                'os': ['Nexus Operating System'],
                'platform': {
                    'aci': ['aci'],
                    'mds': ['mds'],
                    'n5k': ['n5k'],
                    'n9k': ['n9k'],
                    'nxosv': ['nxosv'],
                },
            },
            'iosxe': {
                'os': ['IOS( |-)XE Software'],
                'platform': {
                    'cat3k': ['cat3k'],
                    'cat9k': ['cat9k'],
                    'csr1000v': ['csr1000v'],
                    'sdwan': ['sdwan'],
                    'nxosv': ['nxosv'],
                },
            },
            'iosxr': {
                'os': ['IOS XR Software'],
                'platform': {
                    'asr9k': ['asr9k'],
                    'iosxrv': ['iosxrv'],
                    'iosxrv9k': ['iosxrv9k'],
                    'moonshine': ['moonshine'],
                    'ncs5k': ['ncs5k'],
                    'spitfire': ['spitfire'],
                },
            },
            'ios': {
                'os': ['IOS Software'],
                'platform': {
                    'ap': ['TBD'],
                    'iol': ['TBD'],
                    'iosv': ['TBD'],
                    'pagent': ['TBD'],
                },
            },
            'junos': {
                'os': ['JUNOS Software'],
                'platform': {
                    'vsrx': ['vsrx'],
                },
            },
            'linux': {
                'os': ['Linux'],
            },
            'aireos': {
                'os': ['aireos'],
            },
            'cheetah': {
                'os': ['cheetah'],
            },
            'ise': {
                'os': ['ise'],
            },
            'asa': {
                'os': ['asa'],
            },
            'nso': {
                'os': ['nso'],
            },
            'confd': {
                'os': ['confd'],
            },
            'vos': {
                'os': ['vos'],
            },
            'cimc': {
                'os': ['cimc'],
            },
            'fxos': {
                'os': ['fxos'],
            },
            'staros': {
                'os': ['staros'],
            },
            'aci': {
                'os': ['aci'],
            },
            'sdwan': {
                'os': ['sdwan'],
            },
            'sros': {
                'os': ['sros'],
            },
            'apic': {
                'os': ['apic'],
            },
            'windows': {
                'os': ['windows'],
            },
        }
