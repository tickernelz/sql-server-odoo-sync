SQL to Odoo Sync App
====================

A Windows desktop application (written in Python 3.12) that periodically exports SQL Server tables as CSV files and uploads them as attachments to Odoo 14 (using `ir.attachment`). It provides a modern `PyQt6` UI with tray icon features and can be built into a single .exe file using `PyInstaller`.

Features
--------

-   Modern interface built with `PyQt6`
-   **Asynchronous processing** with progress bar and real-time feedback
-   **Non-blocking UI** - remains responsive during long sync operations
-   **Embedded monospace font** for consistent appearance across all OS
-   **Thread-safe operations** with proper synchronization mechanisms
-   **Enhanced security** with SQL injection prevention and input validation
-   **Intelligent retry logic** for database and Odoo connection failures
-   **Memory-efficient file handling** with streaming for large files (>50MB)
-   **File locking** to prevent race conditions during concurrent operations
-   Configurable list of tables to sync (comma-separated or all)
-   Option to force a sync regardless of data changes
-   **Cancellable sync operations** with user-friendly progress tracking
-   **Robust error handling** with detailed diagnostic messages
-   Automatically generates `config.ini` if not found
-   Periodic table data sync based on the configured schedule
-   Syncs only when data changes are detected (by comparing file hashes)
-   Log files created with date-time-based filenames in the `logs` directory
-   **Real-time log display** with timestamps and status indicators
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

Security & Reliability
----------------------

This application includes several security and reliability enhancements:

### Security Features
- **SQL Injection Prevention**: All database queries use parameterized statements
- **Input Validation**: Table names and database names are validated and sanitized
- **Directory Traversal Protection**: File paths are sanitized to prevent unauthorized access

### Reliability Features
- **Thread Safety**: Configuration updates and file operations are thread-safe
- **Retry Logic**: Automatic retry for database and Odoo connection failures (configurable)
- **Memory Management**: Large files (>50MB) are processed in chunks to prevent memory issues
- **File Locking**: Prevents race conditions when multiple operations access the same files
- **Enhanced Error Handling**: Detailed error messages help diagnose connection and sync issues

### Error Prevention
- **"No tables to sync" Error**: Enhanced diagnostics for connection failures
- **Connection Timeouts**: Configurable timeout settings with proper cleanup
- **Resource Management**: Proper cleanup of database connections and file handles

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
pyinstaller main.spec

```

Or alternatively:
```
pyinstaller --onefile --windowed --icon=icon.ico main.py

```

Notes:

-   The `main.spec` file includes the embedded font and icon automatically
-   The above command bundles everything into one file, including the icon and fonts
-   The generated .exe will include the UI, tray icon, embedded fonts, and all dependencies
-   **Font Integration**: The app now includes JetBrains Mono font to eliminate font warnings and ensure consistent appearance across all platforms

Additional Notes
----------------

- Ensure the SQL Server driver is installed on your machine (e.g., Microsoft ODBC Driver for SQL Server).\
- This application checks if table data has changed by computing an `MD5` hash of the CSV file. If the hash matches the previously stored one (or if `force_sync` is off), it will skip sending the file to Odoo.\
- If you want to customize the code base into multiple modules, you can safely split it into separate `.py` files as needed.

Troubleshooting
---------------

### Common Issues

**"No tables to sync" Error**
- Check database connection settings
- Verify database permissions
- Ensure tables exist in the specified database
- Check if configuration was modified during sync

**Connection Timeouts**
- Increase timeout settings in configuration
- Check network connectivity to SQL Server and Odoo
- Verify firewall settings

**Memory Issues with Large Files**
- The application automatically handles files >50MB with streaming
- For very large datasets, consider splitting tables or using selective sync

**File Access Errors**
- Ensure the application has write permissions to the working directory
- Check if antivirus software is blocking file operations
- Verify sufficient disk space for CSV exports

License
-------

Your choice of license (e.g., MIT, GPL, proprietary) applies. Be sure to include a valid license if you plan to distribute or release your software.