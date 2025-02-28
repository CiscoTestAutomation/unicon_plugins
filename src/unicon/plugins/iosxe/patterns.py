""" Generic IOS-XE Patterns. """

__author__ = "Myles Dear <pyats-support@cisco.com>"

from unicon.plugins.generic.patterns import GenericPatterns
from unicon.plugins.generic.service_patterns import ReloadPatterns


class IosXEPatterns(GenericPatterns):

    def __init__(self):
        super().__init__()
        self.shell_prompt = r'^(.*?)\[(%N|[Ss]witch|[Rr]outer|eWLC).*?\]\$\s?$'
        self.access_shell = \
            r'^.*Are you sure you want to continue\? \[y/n\]\s?.*$'
        self.overwrite_previous = \
            r'^.*Overwrite the previous NVRAM configuration\?\[confirm\].*$'
        self.are_you_sure = \
            r'^.*Are you sure you want to continue\? \(y\/n\)\[y\]:?\s?$'
        self.delete_filename = r'^.*Delete filename \[.*\]\?\s*$'
        self.wish_continue = r'^.*Do you wish to continue\? \[yes\]:\s*$'
        self.want_continue = r'^.*Do you want to continue\? \[no\]:\s*$'
        self.want_continue_confirm = r'.*Do you want to continue\?\s*\[confirm]\s*$'
        self.want_continue_yes = r'.*Do you want to continue\?\s*\[y/n]\?\s*\[yes]:\s*$'
        self.disable_prompt = \
            r'^(.*?)(\(unlicensed\))?(WLC|Router|RouterRP|Switch|ios|switch|%N)([0-9])?(\(standby\))?(-stby)?(-standby)?(\(boot\))?(\(recovery-mode\))?>\s?$'
        self.enable_prompt = \
            r'^(.*?)(\(unlicensed\))?(WLC|Router|RouterRP|Switch|ios|switch|%N)([0-9])?(\(standby\))?(-stby)?(-standby)?(\(boot\))?(\(recovery-mode\))?#[\s\x07]*$'
        self.maintenance_mode_prompt = \
            r'^(.*?)(\(unlicensed\))?(WLC|Router|RouterRP|Switch|ios|switch|%N)([0-9])?(\(standby\))?(-stby)?(-standby)?(\(boot\))?\(maint-mode\)#[\s\x07]*$'
        self.press_enter = ReloadPatterns().press_enter
        self.config_prompt = r'^(.*)\((?!.*pki-hexmode).*(con|cfg|ipsec-profile|ca-trustpoint|ca-certificate-map|cs-server|ca-profile|gkm-local-server|cloud|host-list|config-gkm-group|gkm-sa-ipsec|gdoi-coop-ks-config|wsma|enforce-rule|DDNS)\S*\)#\s?$'


        self.config_pki_prompt = r'^(.*)\(config-pki-hexmode\)#\s?$'
        self.are_you_sure_ywtdt = r'Are you sure you want to do this\? \[yes/no\]:\s*$'
        self.do_you_want_to = r'^.*Do you want to remove the above files\? \[y\/n]\s*$'
        self.confirm_uncommited_changes = r'Uncommitted changes found, commit them\? \[yes\/no\/CANCEL\]\s*$'
        self.proceed_confirm = r'^.*Proceed\? \[yes,no\]\s*$'
        # Don't use hostname in tclsh prompt, hostname may be truncated
        self.tclsh_prompt = r'^(.*?)\(tcl.*?\)#[\s\x07]*$'
        self.macro_prompt = r'^(.*?)(\{\.\.\}|then.else.fi)\s*>\s*$'
        self.unable_to_create = r'^(.*?)Unable to create.*$'


class IosXEReloadPatterns(ReloadPatterns):
    def __init__(self):
        super().__init__()
        self.escape_char = r"Escape character is .*\n"
        self.connection_refused = r'^.*Connection refused'
        self.login_prompt = r'^.*(Username|login): ?$'
        self.password_prompt = r'^[^\n]*Password:\s?$'
        self.confirm_prompt = r'^.*\[confirm\]\s?$'
        self.useracess = r'^.*User Access Verification'
        self.setup_dialog = r'^.*(initial|basic) configuration dialog.*\s?'
        self.autoinstall_dialog = r'^(.*)Would you like to terminate autoinstall\? ?\[yes\]: $'
        self.default_prompts = r'^(.*?)(WLC|Router|RouterRP|Switch|ios|switch|.*)([0-9])?(\(standby\))?(\(boot\))?(>|#)'
        self.telnet_prompt = r'^.*telnet>\s?'
        self.please_reset = r'^(.*)Please reset'
        self.grub_prompt = r'.*The highlighted entry will be (booted|executed) automatically'

        # The uniclean package expects these patterns to be here.
        self.enable_prompt = IosXEPatterns().enable_prompt
        self.disable_prompt = IosXEPatterns().disable_prompt

class FactoryResetPatterns:
    def __init__(self):
        self.factory_reset_confirm = r'factory reset operation is irreversible for all operations\. Are you sure\? \[confirm\]'
        self.are_you_sure_confirm = r'Are you sure you want to continue\? \[confirm\]'
