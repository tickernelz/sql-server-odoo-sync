# SQL Server to Odoo Sync Application

## Project Overview

This is a Windows desktop application built with Python 3.12 that provides automated synchronization of SQL Server database tables to Odoo 14. The application exports SQL Server tables as CSV files and uploads them as attachments to Odoo using the `ir.attachment` model, creating a seamless data integration pipeline.

## Key Features

### 🖥️ **Modern Desktop Interface**
- Built with PyQt6 for a modern, responsive UI
- System tray integration for background operation
- Configurable settings through GUI or configuration file
- Real-time sync status updates

### 🔄 **Intelligent Synchronization**
- **Multiple Database Support**: Can sync from multiple SQL Server databases simultaneously
- **Selective Table Sync**: Configure specific tables to sync or sync all tables
- **Change Detection**: Uses MD5 hashing to detect data changes and avoid unnecessary uploads
- **Force Sync Option**: Override change detection for manual synchronization
- **Retry Logic**: Built-in retry mechanism with configurable timeout and retry settings

### 📊 **Advanced Data Management**
- **CSV Export**: Converts SQL Server table data to CSV format
- **File Management**: Automatically maintains only the 3 most recent CSV files per table
- **Large File Handling**: Warning system for large files with configurable timeout
- **Schema Information**: Captures and stores table schema details including column types, nullability, and primary keys

### 🔒 **Enterprise-Ready Features**
- **Comprehensive Logging**: Date-time stamped log files with configurable log levels
- **Error Handling**: Robust error handling with detailed exception logging
- **Connection Management**: Automatic connection retry and timeout handling
- **Configuration Management**: Auto-generated configuration with sensible defaults

### 📦 **Deployment Ready**
- **Single-File Executable**: PyInstaller support for creating standalone .exe files
- **Icon Integration**: Built-in application icon support
- **System Service Ready**: Can run minimized to system tray

## Technical Architecture

### **Core Components**

1. **Database Layer**
   - SQL Server connectivity via pyodbc
   - Multi-database connection management
   - Table schema introspection
   - Dynamic SQL query generation

2. **Sync Engine**
   - Change detection via file hashing
   - CSV generation and management
   - Odoo integration via XML-RPC
   - Retry logic and error recovery

3. **User Interface**
   - PyQt6-based desktop application
   - System tray integration
   - Configuration management UI
   - Real-time status updates

4. **Odoo Integration**
   - XML-RPC client for Odoo communication
   - `ir.attachment` model integration
   - Custom Odoo models for sync data tracking:
     - `mssql.sync.data`: Main sync record
     - `mssql.sync.table.details`: Column information
     - `mssql.sync.table.data`: Attachment references

### **Data Flow**

```
SQL Server Database(s) → CSV Files → Hash Comparison → Odoo Upload → Attachment Storage
                                          ↓
                                    Log Generation
```

### **Configuration Structure**

The application uses an INI-based configuration system with four main sections:

- **Database**: SQL Server connection settings and database list
- **Odoo**: Odoo instance connection parameters
- **Sync**: Synchronization behavior and performance settings
- **General**: Application-wide settings like logging level

## File Structure

```
sql-server-odoo-sync/
├── main.py                 # Main application file (complete single-file implementation)
├── config.ini             # Configuration file (auto-generated)
├── main.spec              # PyInstaller specification file
├── README.MD              # User documentation
├── .gitignore             # Git ignore rules
├── logs/                  # Generated log files (ignored)
├── generated_csv/         # Temporary CSV files (managed automatically)
└── dist/                  # PyInstaller output (ignored)
```

## Dependencies

### **Core Requirements**
- **Python 3.12+**: Main runtime environment
- **PyQt6**: Modern GUI framework
- **pyodbc**: SQL Server database connectivity
- **xmlrpc.client**: Odoo API communication (standard library)

### **System Requirements**
- **Windows**: Primary target platform
- **SQL Server ODBC Driver**: Microsoft ODBC Driver for SQL Server
- **Network Access**: To both SQL Server and Odoo instances

## Configuration Options

### **Database Section**
- `server`: SQL Server hostname or IP address
- `databases`: Comma-separated list of databases to sync
- `username`: SQL Server authentication username
- `password`: SQL Server authentication password

### **Odoo Section**
- `url`: Full Odoo instance URL (e.g., http://localhost:8069)
- `db`: Target Odoo database name
- `username`: Odoo user credentials
- `password`: Odoo user password

### **Sync Section**
- `tables_to_sync`: Specific tables (comma-separated) or empty for all
- `sync_period`: Automatic sync interval in seconds
- `force_sync`: Override change detection (True/False)
- `timeout_seconds`: Network timeout for Odoo operations
- `max_retries`: Number of retry attempts for failed operations
- `retry_delay`: Delay between retry attempts

### **General Section**
- `log_level`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)

## Usage Scenarios

### **Development Environment**
- Local SQL Server to local Odoo development instance
- Quick table synchronization for testing
- Schema exploration and data analysis

### **Production Environment**
- Scheduled synchronization between production systems
- Multiple database synchronization
- Enterprise data integration pipeline

### **Migration Projects**
- Data migration from SQL Server to Odoo
- Incremental data transfer
- Schema mapping and validation

## Development Notes

### **Code Organization**
The application is currently implemented as a single-file solution (`main.py`) for simplicity, but the architecture supports modularization into separate files:

- **Database Module**: Connection and query management
- **Sync Module**: Synchronization logic and file handling
- **UI Module**: PyQt6 interface components
- **Config Module**: Configuration management
- **Odoo Module**: Odoo API integration

### **Extensibility**
The application is designed for extension:
- **Custom Data Transformations**: Modify CSV generation logic
- **Additional Database Types**: Extend beyond SQL Server
- **Advanced Filtering**: Table and column-level filtering
- **Scheduling**: Cron-like scheduling capabilities
- **Monitoring**: Health checks and performance metrics

### **Security Considerations**
- Configuration file contains sensitive credentials
- Network communication occurs in plain text (consider HTTPS for Odoo)
- File system permissions for log and CSV directories
- SQL injection protection through parameterized queries

## Build and Distribution

### **Development Setup**
```bash
# Clone repository
git clone <repository-url>
cd sql-server-odoo-sync

# Install dependencies
pip install pyqt6 pyodbc requests

# Run application
python main.py
```

### **Production Build**
```bash
# Create standalone executable
pyinstaller --onefile --windowed --icon=icon.ico main.py

# Output will be in dist/main.exe
```

### **Deployment**
- Distribute single executable file
- Include sample `config.ini` for initial setup
- Ensure ODBC drivers are installed on target systems
- Configure network access to SQL Server and Odoo

## License

This project structure and documentation suggest a utility application for enterprise data integration. License terms should be specified based on intended distribution and usage rights.

## Support and Maintenance

This application provides a foundation for SQL Server to Odoo data synchronization. For production use, consider:

- **Regular Updates**: Keep dependencies current for security
- **Monitoring**: Implement health checks and alerting
- **Backup Strategy**: Ensure CSV and log file management
- **Performance Tuning**: Optimize for large datasets
- **Documentation**: Maintain configuration and deployment guides

---

*This repository contains a complete, production-ready solution for automated SQL Server to Odoo data synchronization with a modern desktop interface.*