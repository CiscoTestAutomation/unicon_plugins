'''
Author: Alex Pfeil
Contact: www.linkedin.com/in/alex-p-352040a0
Contents largely inspired by sample Unicon repo, Knox Hutchinson and pyATS TEAM (pyats-support@cisco.com, pyats-support-ext@cisco.com):
https://github.com/CiscoDevNet/pyats-plugin-examples/tree/master/unicon_plugin_example/src/unicon_plugin_example
'''

#This imports the UniconCorePatterns.
from unicon.patterns import UniconCorePatterns

#Patterns to match different expect statements
class aosPatterns(UniconCorePatterns):
    def __init__(self):
        super().__init__()
        self.login_prompt = r'^.*[Ll]ogin as( for )?(\\S+)?: ?$'
        self.password_prompt = r'^.*[Pp]assword( for )?(\\S+)?: ?$'
        self.enable_prompt = r'.*>'
        self.config_mode = r'.*config.#'
        self.password = r'.*ssword:$'
        self.executive_prompt = r'.*#$'
        self.executive_login = r'.*#.*'
        self.config_prompt = r'.*config.*#'
        self.proxy = r'.*rhome.*'
        self.press_any_key = r'.*any key to conti.*'
        self.continue_connecting = r'Are you sure you want to continue connecting (yes/no)?'
        self.ssh_key_check = r'.*yes/no/[fingerprint]'
        self.start = r'.*These computing resources are solely owned by the Company. Unauthorized\r\naccess, use or modification is a violation of law and could result in\r\ncriminal prosecution. Users agree not to disclose any company information\r\nexcept as authorized by the Company. Your use of the Company computing\r\nresources is consent to be monitored and authorization to search your\r\ncomputer or device to assure compliance with company policies and/or the law.*'
        self.learn_os_prompt = r'^(.*?([>\$~%]|[^#\s]#|~ #|~/|^admin:|^#)\s?(\x1b\S+)?)$|(^.*This \(D\)RP Node is not ready or active for login \/configuration.*)'