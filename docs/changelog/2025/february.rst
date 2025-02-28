February 2025
==========

February 25 - Unicon v25.2 
------------------------



.. csv-table:: Module Versions
    :header: "Modules", "Versions"

        ``unicon.plugins``, v25.2 
        ``unicon``, v25.2 




Changelogs
^^^^^^^^^^
--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* router.connection_provider
    * Modified disconnect
        * Added sendline('exit') on disconnect


--------------------------------------------------------------------------------
                                      Fix                                       
--------------------------------------------------------------------------------

* generic
    * updated exception for Recover device using golden image if reload is failed.


--------------------------------------------------------------------------------
                                      New                                       
--------------------------------------------------------------------------------

* iosxe/vpagent
    * Add connection provider for vpagent

* iosxe
    * Added to Configure Error Patterns
        * Added the regex to match error pattern "127.0 / 255.0 is an invalid network."


