SQL to Odoo Sync App
====================

A Windows desktop application (written in Python 3.12) that periodically exports SQL Server tables as CSV files and uploads them as attachments to Odoo 14 (using `ir.attachment`). It provides a modern `PyQt6` UI with tray icon features and can be built into a single .exe file using `PyInstaller`.

Features
--------

-   Modern interface built with `PyQt6`
-   Configurable list of tables to sync (comma-separated or all)
-   Option to force a sync regardless of data changes
-   Automatically generates `config.ini` if not found
-   Periodic table data sync based on the configured schedule
-   Syncs only when data changes are detected (by comparing file hashes)
-   Log files created with date-time-based filenames in the `logs` directory
-   Packable into a single-file executable with `PyInstaller`

Requirements
------------

1.  Python 3.12 (or compatible version that can run `PyQt6` and `pyodbc`)
2.  SQL Server instance (local or remote)
3.  Odoo 14 instance
4.  (Recommended) A Python virtual environment

Installation
------------

1.  Clone or download the project files into a directory.

2.  Ensure you have Python 3.12+ installed.

3.  Install the required dependencies:

    ```
    pip install pyqt6 pyodbc requests

    ```

    Note: For XML-RPC, use Python's standard library `xmlrpc.client` rather than installing `xmlrpclib`.

4.  If you prefer a virtual environment, create and activate it before installing dependencies.

Configuration
-------------

The application will look for a file named `config.ini` in the same directory as `main.py`. If it does not exist, the application will create it automatically with default values (see `DEFAULT_CONFIG` in the code). The configuration sections include:

- `Database`

-   `server`: SQL Server name or IP
-   `database`: The database name
-   `username`: Login username
-   `password`: Login password

- `Odoo`

-   `url`: Full URL to the Odoo instance (e.g. http://localhost:8069)
-   `db`: Odoo database name
-   `username`: Odoo login
-   `password`: Odoo password

- `Sync`

-   `tables_to_sync`: Comma-separated list of tables; blank for all
-   `sync_period`: Sync frequency in seconds
-   `force_sync`: Whether to force a sync every time

- `General`

-   `log_level`: Logging level (e.g. INFO, DEBUG)

You can edit `config.ini` manually or via the app's UI.

Usage
-----

1.  Run the application via:

    ```
    python main.py

    ```

2.  A window will appear showing configuration fields:

    -   SQL Server settings
    -   Odoo settings
    -   Sync settings (tables, period, and force)
3.  Click `Save Config` to store your changes to `config.ini`.

4.  Click `Sync Now` to immediately perform the sync.

5.  The app runs in the system tray by default. Closing the window only minimizes it to the tray.\
    Right-click the tray icon for options:

    -   Show main window
    -   Sync now
    -   Exit the application

Logging
-------

Log files are created under the `logs` folder. Each file name contains a date-time stamp to keep logs organized by run or session.

Building an Executable
----------------------

To build a single-file `.exe` using `PyInstaller`, run:

```
pyinstaller --onefile --windowed --icon=icon.ico main.py

```

Notes:

-   The above command bundles everything into one file, including the icon (if provided).
-   The generated .exe will include the UI, tray icon, and all dependencies.

Additional Notes
----------------

- Ensure the SQL Server driver is installed on your machine (e.g., Microsoft ODBC Driver for SQL Server).\
- This application checks if table data has changed by computing an `MD5` hash of the CSV file. If the hash matches the previously stored one (or if `force_sync` is off), it will skip sending the file to Odoo.\
- If you want to customize the code base into multiple modules, you can safely split it into separate `.py` files as needed.

License
-------

Your choice of license (e.g., MIT, GPL, proprietary) applies. Be sure to include a valid license if you plan to distribute or release your software.