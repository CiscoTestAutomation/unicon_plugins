January 2025
==========

 - Unicon v25.1 
------------------------



.. csv-table:: Module Versions
    :header: "Modules", "Versions"

        ``unicon.plugins``, v25.1 
        ``unicon``, v25.1 




Changelogs
^^^^^^^^^^
--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* backend
    * New match mode support for last line ignoring whitespace

* learn_tokens
    * Update learn_os_prompt to account for config mode

* unicon
    * Fix the dialog processor to trigger actions only when statements match patterns(HA/Stack)


--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* iosxr
    * Added SwitchoverDisallowedError exception to raise when redundancy switchover is disallowed on the device.

* unicon.plugins
    * Added Reload
        * Added support to pick max value of RELOAD_RECONNECT_WAIT or POST_RELOAD_WAIT
    * Base Execute
        * pass backend decode error
    * generic
        * Updated regex patterns to prevent matching of test case names that contain the words "failure" or "fail_". This change ensures that test cases with failure-related names no longer trigger errors during processing.

* iosxe/pattern
    * Allow 'DDNS' to config prompt patterns

* generic
    * Added 'copy_overwrite_handler' in the service_statements.py to handle

* iosxe
    * Added below config error patterns
        * % VLAN [<vlan_id>] already in use
    * Added below config error patterns
        * % VNI <VNI_ID> is either already in use or exceeds the maximum allowable VNIs.