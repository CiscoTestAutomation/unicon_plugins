""" Vpagent IOS-XE Settings. """

from unicon.plugins.iosxe.settings import IosXESettings

class VpagentIosxeSettings(IosXESettings):

    def __init__(self):
        super().__init__()
        self.WAITE_TIMEOUT = 60