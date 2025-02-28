""" Generic IOS-XE Settings. """

__author__ = "Myles Dear <mdear@cisco.com>"

from unicon.plugins.generic.settings import GenericSettings

class IosXESettings(GenericSettings):

    def __init__(self):
        super().__init__()

        # A single cycle of retries wasn't enough to recover an iosxe device
        # just rebooted after a "write erase".
        self.PROMPT_RECOVERY_RETRIES = 2
        self.PROMPT_RECOVERY_COMMANDS = ['\r', '\x1e', '\x03']

        self.ERROR_PATTERN = [
            r'^%\s*[Ii]nvalid (command|input)',
            r'^%\s*[Ii]ncomplete (command|input)',
            r'^%\s*[Aa]mbiguous (command|input)',
            r'% Bad IP address or host name',
            r'% Unknown command or computer name, or unable to find computer address'
        ]
        self.CONFIGURE_ERROR_PATTERN = [
            r'^%\s*[Ii]nvalid (command|input|number|address)',
            r'routing table \S+ does not exist',
            r'^%\s*SR feature is not configured yet, please enable Segment-routing first.',
            r'^%\s*\S+ overlaps with \S+',
            r'^\S+ / \S+ is an [Ii]nvalid network\.',
            r'^%\S+ is linked to a VRF. Enable \S+ on that VRF first.',
            r'% VRF \S+ not configured',
            r'% Incomplete command.',
            r'%CLNS: System ID (\S+) must not change when defining additional area addresses',
            r'% Specify remote-as or peer-group commands first',
            r'% Policy commands not allowed without an address family',
            r'% Color set already. Deconfigure first',
            r'Invalid policy name, \S+ does not exist',
            r'% Deletion of RD in progress; wait for it to complete',
            r'% VLAN \[\d+\] already in use',
            r'% VNI \d+ is either already in use or exceeds the maximum allowable VNIs.'
        ]

        self.EXECUTE_MATCHED_RETRIES = 1
        self.EXECUTE_MATCHED_RETRY_SLEEP = 0.1

        self.RELOAD_WAIT = 300

        # wait time for buffer to settle down
        self.CONTROLLER_MODE_CHATTY_WAIT_TIME = 5

        self.CONFIG_LOCK_RETRY_SLEEP = 30
        self.CONFIG_LOCK_RETRIES = 10

        self.POST_BOOT_TIMEOUT = 300
        self.BOOT_POSTCHECK_INTERVAL = 30

        self.SERVICE_PROMPT_CONFIG_CMD = 'service prompt config'
        self.CONFIG_PROMPT_WAIT = 2

        self.GUESTSHELL_CONFIG_CMDS = ['iox', 'app-hosting appid guestshell', 'app-vnic management guest-interface 0']
        self.GUESTSHELL_CONFIG_VERIFY_CMDS = ['show iox-service', 'show app-hosting list']
        self.GUESTSHELL_CONFIG_VERIFY_PATTERN = r'guestshell\s+RUNNING'
        self.GUESTSHELL_ENABLE_CMDS = 'guestshell enable'
        self.GUESTSHELL_ENABLE_VERIFY_CMDS = []
        self.GUESTSHELL_ENABLE_VERIFY_PATTERN = r''

        # Regex to match the entries on the grub boot screen
        self.GRUB_REGEX_PATTERN = r'(?:\x1b\[7m)?\x1b\[\d;3H.*?   '

        self.MAINTENANCE_MODE_WAIT_TIME = 30   # 30 seconds
        self.MAINTENANCE_MODE_TIMEOUT = 60*40  # 40 minutes
        self.MAINTENANCE_START_COMMAND = 'start maintenance'
        self.MAINTENANCE_STOP_COMMAND = 'stop maintenance'
