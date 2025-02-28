from unicon.plugins.iosxe import IosXESingleRpConnection
from unicon.plugins.iosxe.vpagent.settings import VpagentIosxeSettings
from unicon.plugins.iosxe.vpagent.connection_provider import  VpagentSingleRpConnectionProvider



class VpagentSingleRpConnection(IosXESingleRpConnection):
    platform = 'vpagent'
    chassis_type = 'single_rp'
    connection_provider_class = VpagentSingleRpConnectionProvider
    settings = VpagentIosxeSettings()