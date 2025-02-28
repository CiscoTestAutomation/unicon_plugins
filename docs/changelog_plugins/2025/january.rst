January 2025
==========

 - Unicon.Plugins v25.1 
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

* iosxr
    * Update monitor service prompt pattern
    * Fix action pattern regex
    * Update logic support matching case and space insensitive actions
    * SPITFIRE plugin
        * Added a new pattern to recognize the prompt seen when showtech collection times out and the script tries to exit by sending kill signal. Also, added the statement to run while the pattern matches
    * Added UNICON_BACKEND_DECODE_ERROR_LIMIT with a default value of 10, to handle scenarios when the device is slow
    * Add statements to reload dialog
    * Add pattern for "Do you wish to continue"
    * Add syslog statement to config state transition

* generic
    * Update learn_os_prompt to account for config mode
    * update syslog message pattern

* unicon.plugins
    * Fix syntax warning