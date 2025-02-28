__author__ = "dwapstra"

from unicon.plugins.generic.patterns import GenericPatterns

class StarosPatterns(GenericPatterns):
    def __init__(self):
        super().__init__()
        self.exec_prompt = r'^(.*?)(\[\S+\] ?%N[#>])\s*$'
        self.config_prompt = r'^(.*?)(\[\S+\] ?%N\(\S+\)[#>])\s*$'
        self.monitor_main_prompt = r'^(.*?\(Q\)uit,\s+<ESC> Prev Menu,\s+<SPACE> Pause,\s+<ENTER> Re-Display Options.*)$'
        self.monitor_sub_prompt = r'^(.*?\(B\)egin Protocol Decoding\s+\(Q\)uit,\s+<ESC> Prev Menu,\s+<ENTER> Re-Display Options\s+Select:)\s*'
        self.yes_no_prompt = r'^(.*?)Are you sure \? \[Yes | No\]:\s*'
        self.monitor_state_update = r'\*\*\* .* \((.*?)\) \*\*\*'
        self.limit_context_state_update = r'\*\*\* Display Events (only )?from (context )?"?(local|ALL)"?'
        self.radius_dict_update = r'\*\*\* RADIUS Dictionary \(?(.*)\)? \*\*\*'
        self.gtpp_dict_update = r'\*\*\* GTPP Dictionary \(?(.*)\)? \*\*\*'
        self.call_finished = r'^(.*?)Call Finished.*'

        self.monitor_date_string = r'(\w+) (\w+) (\d+) .* (\d+)$'
        self.monitor_command_pattern = r'(\S+) ?- (.*?)\s?(\(\S+\))?\s*(\(.*?\)|NONE)'
        self.monitor_app_specific_diameter = r'(\S+) ?- (.*?)\s?\s*(\(.*?\))'