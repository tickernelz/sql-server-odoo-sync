"""
Windows Desktop App (Python 3.12) for Syncing SQL Server tables as CSV to Odoo 14 (ir.attachment).
Features:
- Modern PyQt6 UI with Tray Icon
- Configurable tables to sync (default: all)
- Periodic sync schedule
- Config stored in config.ini (auto-generated if missing)
- Sync only when data has changed, with optional "force sync"
- Logs saved in /logs with date-time filenames
- Packable with PyInstaller (includes a small built-in icon)
- Asynchronous processing with progress bar
- Non-blocking UI during sync operations

Install Requirements (example):
  pip install pyqt6 pyodbc requests xmlrpclib (or use the standard library's xmlrpc)
  # Use 'xmlrpc.client' from Python standard library rather than 'xmlrpclib'
  # Replace with your environment's specifics

Build an EXE:
  pyinstaller --onefile --windowed --icon=icon.ico main.py

Below is a single-file example. Feel free to separate into multiple files for cleanliness.
"""

import sys
import os
import base64
import csv
import logging
import datetime
import configparser
import traceback
import hashlib
import time
import socket
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSystemTrayIcon,
    QMenu,
    QMessageBox,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QTextEdit,
)
from PyQt6.QtGui import QIcon, QAction, QCursor, QFontDatabase, QFont
from PyQt6.QtCore import QTimer, Qt, QThread, pyqtSignal

import pyodbc
import xmlrpc.client

DEFAULT_CONFIG = {
    "Database": {
        "server": "localhost",
        "databases": "testdb1, testdb2",
        "username": "sa",
        "password": "YourPassword123",
    },
    "Odoo": {
        "url": "http://localhost:8069",
        "db": "odoo_db",
        "username": "admin",
        "password": "admin",
    },
    "Sync": {
        "tables_to_sync": "",
        "sync_period": "60",
        "force_sync": "False",
        "timeout_seconds": "300",
        "max_retries": "3",
        "retry_delay": "5",
    },
    "General": {"log_level": "INFO"},
}


def ensure_config_exists(config_path: str):
    if not os.path.exists(config_path):
        config = configparser.ConfigParser()
        for section, values in DEFAULT_CONFIG.items():
            config[section] = values
        with open(config_path, "w", encoding="utf-8") as f:
            config.write(f)


def load_config(config_path: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")
    return config


def setup_logging():
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)
    log_filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S.log")
    log_path = os.path.join(logs_dir, log_filename)

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("Logging started.")


def connect_to_sql_server_for_db(
    config: configparser.ConfigParser, db_name: str
) -> pyodbc.Connection:
    server = config["Database"]["server"]
    username = config["Database"]["username"]
    password = config["Database"]["password"]

    conn_str = (
        f"Driver={{SQL Server}};"
        f"Server={server};"
        f"Database={db_name};"
        f"UID={username};"
        f"PWD={password};"
    )
    return pyodbc.connect(conn_str)


def fetch_tables_list(connection: pyodbc.Connection):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE'
        """)
        return [row[0] for row in cursor.fetchall()]


def fetch_table_data_as_csv(
    connection: pyodbc.Connection, table_name: str, db_name: str
) -> str:
    csv_dir = "generated_csv"
    os.makedirs(csv_dir, exist_ok=True)
    csv_file = os.path.join(
        csv_dir,
        f"{db_name}_{table_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )

    with (
        connection.cursor() as cursor,
        open(csv_file, "w", newline="", encoding="utf-8") as f,
    ):
        writer = csv.writer(f)
        cursor.execute(f"SELECT * FROM [{table_name}]")
        writer.writerow([desc[0] for desc in cursor.description])
        for row in cursor.fetchall():
            writer.writerow(row)

    return csv_file


def compute_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        data = f.read()
        hasher.update(data)
    return hasher.hexdigest()


def check_file_size_warning(filepath: str, max_size_mb: int = 50):
    """Check file size and log warning if it's too large"""
    file_size = os.path.getsize(filepath)
    file_size_mb = file_size / (1024 * 1024)
    
    if file_size_mb > max_size_mb:
        logging.warning(
            f"Large file detected: {filepath} ({file_size_mb:.2f} MB). "
            f"This may cause timeout issues. Consider increasing timeout_seconds in config."
        )
    
    return file_size


def send_csv_to_odoo(
    config: configparser.ConfigParser, csv_file: str, table_name: str, db_name: str
):
    url = config["Odoo"]["url"]
    db = config["Odoo"]["db"]
    username = config["Odoo"]["username"]
    password = config["Odoo"]["password"]
    
    # Get timeout and retry settings
    timeout_seconds = int(config.get("Sync", "timeout_seconds", fallback="300"))
    max_retries = int(config.get("Sync", "max_retries", fallback="3"))
    retry_delay = int(config.get("Sync", "retry_delay", fallback="5"))
    
    # Set socket timeout
    socket.setdefaulttimeout(timeout_seconds)
    
    def create_server_proxy_with_timeout(endpoint):
        """Create ServerProxy with timeout handling"""
        return xmlrpc.client.ServerProxy(
            f"{url}{endpoint}",
            allow_none=True,
            use_builtin_types=True
        )
    
    def execute_with_retry(func, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (xmlrpc.client.ProtocolError, socket.timeout, ConnectionError, OSError) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logging.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logging.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
        raise last_exception
    
    # Authenticate with retry
    common = create_server_proxy_with_timeout("/xmlrpc/2/common")
    uid = execute_with_retry(common.authenticate, db, username, password, {})
    if not uid:
        raise Exception("Failed to authenticate to Odoo.")
    
    models = create_server_proxy_with_timeout("/xmlrpc/2/object")

    # Check file size and warn if large
    file_size = check_file_size_warning(csv_file)
    
    with open(csv_file, "rb") as f:
        file_data = f.read()
    file_base64 = base64.b64encode(file_data).decode("utf-8")
    file_name = os.path.basename(csv_file)

    # Create attachment with retry
    logging.info(f"Creating attachment for {file_name} (size: {file_size} bytes)")
    attachment_id = execute_with_retry(
        models.execute_kw,
        db,
        uid,
        password,
        "ir.attachment",
        "create",
        [{"name": file_name, "datas": file_base64, "mimetype": "text/csv"}],
    )

    with connect_to_sql_server_for_db(config, db_name) as conn, conn.cursor() as cursor:
        cursor.execute(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                CHARACTER_MAXIMUM_LENGTH,
                COLUMNPROPERTY(OBJECT_ID(TABLE_NAME), COLUMN_NAME, 'IsIdentity') as IS_PRIMARY_KEY
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}'
        """)
        columns = cursor.fetchall()

    sync_data = {
        "name": table_name,
        "database_name": db_name,
    }

    existing_ids = execute_with_retry(
        models.execute_kw,
        db,
        uid,
        password,
        "mssql.sync.data",
        "search",
        [
            [
                ["name", "=", table_name],
                ["database_name", "=", db_name],
            ]
        ],
    )

    if existing_ids:
        sync_data_id = existing_ids[0]
        execute_with_retry(
            models.execute_kw,
            db, uid, password, "mssql.sync.data", "write", [[sync_data_id], sync_data]
        )
    else:
        sync_data_id = execute_with_retry(
            models.execute_kw,
            db, uid, password, "mssql.sync.data", "create", [sync_data]
        )

    # Only create details if they do not already exist
    for column in columns:
        column_name = column[0]
        existing_detail_ids = execute_with_retry(
            models.execute_kw,
            db,
            uid,
            password,
            "mssql.sync.table.details",
            "search",
            [
                [
                    ["sync_data_id", "=", sync_data_id],
                    ["column_name", "=", column_name],
                ]
            ],
        )

        if not existing_detail_ids:
            column_data = {
                "sync_data_id": sync_data_id,
                "column_name": column_name,
                "data_type": column[1],
                "is_nullable": column[2] == "YES",
                "max_length": column[3] or 0,
                "is_primary_key": bool(column[4]),
            }
            execute_with_retry(
                models.execute_kw,
                db,
                uid,
                password,
                "mssql.sync.table.details",
                "create",
                [column_data],
            )

    # Clean up any duplicates that may already be in the database
    existing_details = execute_with_retry(
        models.execute_kw,
        db,
        uid,
        password,
        "mssql.sync.table.details",
        "search_read",
        [[["sync_data_id", "=", sync_data_id]]],
        {"fields": ["id", "column_name"], "order": "column_name"},
    )

    duplicates_to_remove = []
    unique_cols = set()
    for detail in existing_details:
        col_name = detail["column_name"]
        if col_name in unique_cols:
            duplicates_to_remove.append(detail["id"])
        else:
            unique_cols.add(col_name)

    if duplicates_to_remove:
        execute_with_retry(
            models.execute_kw,
            db,
            uid,
            password,
            "mssql.sync.table.details",
            "unlink",
            [duplicates_to_remove],
        )

    table_data = {"sync_data_id": sync_data_id, "attachment_id": attachment_id}
    execute_with_retry(
        models.execute_kw,
        db, uid, password, "mssql.sync.table.data", "create", [table_data]
    )

    logging.info(
        f"Uploaded `{file_name}` to Odoo for table `{table_name}` in DB `{db_name}` "
        f"(sync_data_id: {sync_data_id}). Duplicate table details removed if found."
    )


def get_icon_path():
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "icon.ico")  # Used in pyinstaller
    else:
        return "icon.ico"


def get_font_path():
    """Get the path to the embedded font"""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "fonts", "JetBrainsMono-Regular.ttf")
    else:
        return os.path.join("fonts", "JetBrainsMono-Regular.ttf")


def load_custom_font():
    """Load the custom monospace font and return the font family name"""
    font_path = get_font_path()
    
    # Try to load the custom font
    if os.path.exists(font_path):
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_families = QFontDatabase.applicationFontFamilies(font_id)
                if font_families:
                    logging.info(f"Successfully loaded custom font: {font_families[0]}")
                    return font_families[0]
        except Exception as e:
            logging.warning(f"Failed to load custom font from {font_path}: {e}")
    else:
        logging.warning(f"Custom font file not found: {font_path}")
    
    # Fallback to system monospace fonts based on platform
    fallback_fonts = {
        "win32": ["Consolas", "Courier New", "Lucida Console"],
        "darwin": ["SF Mono", "Monaco", "Menlo", "Courier New"],
        "linux": ["DejaVu Sans Mono", "Liberation Mono", "Courier New"]
    }
    
    platform_key = "linux"  # default
    if sys.platform == "win32":
        platform_key = "win32"
    elif sys.platform == "darwin":
        platform_key = "darwin"
    
    # Try each fallback font until we find one that exists
    for font_name in fallback_fonts[platform_key]:
        font = QFont(font_name)
        if QFontDatabase.families().count(font_name) > 0:
            logging.info(f"Using fallback monospace font: {font_name}")
            return font_name
    
    # Ultimate fallback
    logging.warning("No suitable monospace font found, using system default")
    return "monospace"


class SyncWorker(QThread):
    """Worker thread for performing sync operations asynchronously"""
    
    # Signals for communication with main thread
    progress_updated = pyqtSignal(int, str)  # progress percentage, status message
    sync_completed = pyqtSignal(bool, str)   # success, message
    log_message = pyqtSignal(str)            # log message for display
    
    def __init__(self, config, force_sync=False):
        super().__init__()
        self.config = config
        self.force_sync = force_sync
        self.is_cancelled = False
        
    def cancel(self):
        """Cancel the sync operation"""
        self.is_cancelled = True
        
    def run(self):
        """Main sync operation running in separate thread"""
        try:
            self.progress_updated.emit(0, "Starting sync operation...")
            
            databases_str = self.config["Database"]["databases"]
            database_list = [d.strip() for d in databases_str.split(",") if d.strip()]
            
            if not database_list:
                self.sync_completed.emit(False, "No databases configured")
                return
            
            total_operations = 0
            completed_operations = 0
            
            # First pass: count total operations
            for db_name in database_list:
                if self.is_cancelled:
                    self.sync_completed.emit(False, "Sync cancelled by user")
                    return
                    
                try:
                    with connect_to_sql_server_for_db(self.config, db_name) as connection:
                        all_tables = fetch_tables_list(connection)
                        
                        to_sync = self.config["Sync"]["tables_to_sync"].strip()
                        if to_sync:
                            table_list = [x.strip() for x in to_sync.split(",") if x.strip()]
                        else:
                            table_list = all_tables
                        
                        total_operations += len(table_list)
                except Exception as e:
                    self.log_message.emit(f"Error connecting to database {db_name}: {str(e)}")
                    continue
            
            if total_operations == 0:
                self.sync_completed.emit(False, "No tables to sync")
                return
            
            self.progress_updated.emit(5, f"Found {total_operations} tables to process...")
            
            # Second pass: perform actual sync
            for db_name in database_list:
                if self.is_cancelled:
                    self.sync_completed.emit(False, "Sync cancelled by user")
                    return
                
                try:
                    self.progress_updated.emit(
                        int((completed_operations / total_operations) * 100),
                        f"Connecting to database: {db_name}"
                    )
                    
                    with connect_to_sql_server_for_db(self.config, db_name) as connection:
                        all_tables = fetch_tables_list(connection)
                        
                        to_sync = self.config["Sync"]["tables_to_sync"].strip()
                        if to_sync:
                            table_list = [x.strip() for x in to_sync.split(",") if x.strip()]
                        else:
                            table_list = all_tables
                        
                        for table in table_list:
                            if self.is_cancelled:
                                self.sync_completed.emit(False, "Sync cancelled by user")
                                return
                            
                            progress_pct = int((completed_operations / total_operations) * 100)
                            self.progress_updated.emit(
                                progress_pct,
                                f"Processing {db_name}.{table} ({completed_operations + 1}/{total_operations})"
                            )
                            
                            try:
                                # Generate CSV
                                csv_file_path = fetch_table_data_as_csv(connection, table, db_name)
                                self.log_message.emit(f"Generated CSV for {db_name}.{table}")
                                
                                # Clean up old CSV files
                                csv_pattern = os.path.join("generated_csv", f"{db_name}_{table}_*.csv")
                                existing_csvs = sorted(
                                    Path().glob(csv_pattern), key=os.path.getctime, reverse=True
                                )
                                for old_file in existing_csvs[3:]:
                                    try:
                                        os.remove(old_file)
                                        logging.info(f"Removed old CSV file: {old_file}")
                                    except Exception as e:
                                        logging.warning(f"Failed to remove old CSV file {old_file}: {e}")
                                
                                # Check if sync is needed
                                file_hash = compute_file_hash(csv_file_path)
                                prev_hash_path = os.path.join("generated_csv", f"{db_name}_{table}_hash.txt")
                                
                                if os.path.exists(prev_hash_path):
                                    with open(prev_hash_path, "r", encoding="utf-8") as hf:
                                        old_hash = hf.read().strip()
                                else:
                                    old_hash = ""
                                
                                if self.force_sync or (file_hash != old_hash):
                                    self.progress_updated.emit(
                                        progress_pct,
                                        f"Uploading {db_name}.{table} to Odoo..."
                                    )
                                    
                                    send_csv_to_odoo(self.config, csv_file_path, table, db_name)
                                    
                                    with open(prev_hash_path, "w", encoding="utf-8") as hf:
                                        hf.write(file_hash)
                                    
                                    self.log_message.emit(f"✓ Uploaded {db_name}.{table}")
                                else:
                                    self.log_message.emit(f"⚬ No changes in {db_name}.{table}, skipped")
                                
                            except Exception as e:
                                error_msg = f"✗ Error processing {db_name}.{table}: {str(e)}"
                                self.log_message.emit(error_msg)
                                logging.error(f"Error processing table {table} in DB {db_name}: {e}")
                            
                            completed_operations += 1
                            
                except Exception as e:
                    error_msg = f"Error with database {db_name}: {str(e)}"
                    self.log_message.emit(error_msg)
                    logging.error(f"Error with database {db_name}: {e}")
                    continue
            
            if not self.is_cancelled:
                self.progress_updated.emit(100, "Sync completed successfully!")
                self.sync_completed.emit(True, f"Successfully processed {completed_operations} tables")
                logging.info("Sync completed successfully.")
            
        except Exception as e:
            error_msg = f"Fatal error during sync: {str(e)}"
            self.log_message.emit(error_msg)
            logging.error(f"Fatal error during sync: {e}\n{traceback.format_exc()}")
            self.sync_completed.emit(False, error_msg)


class MainWindow(QMainWindow):
    def __init__(self, config_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_path = config_path
        self.config = load_config(config_path)
        self.sync_worker = None

        self.setWindowTitle("SQL to Odoo Sync App")
        self.resize(700, 500)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Database UI
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("SQL Server:"))
        self.db_server_edit = QLineEdit(self.config["Database"]["server"])
        db_layout.addWidget(self.db_server_edit)
        layout.addLayout(db_layout)

        db_layout2 = QHBoxLayout()
        db_layout2.addWidget(QLabel("Databases (comma-separated):"))
        self.db_databases_edit = QLineEdit(self.config["Database"]["databases"])
        db_layout2.addWidget(self.db_databases_edit)
        layout.addLayout(db_layout2)

        db_layout3 = QHBoxLayout()
        db_layout3.addWidget(QLabel("Username:"))
        self.db_user_edit = QLineEdit(self.config["Database"]["username"])
        db_layout3.addWidget(self.db_user_edit)
        layout.addLayout(db_layout3)

        db_layout4 = QHBoxLayout()
        db_layout4.addWidget(QLabel("Password:"))
        self.db_pass_edit = QLineEdit(self.config["Database"]["password"])
        self.db_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        db_layout4.addWidget(self.db_pass_edit)
        layout.addLayout(db_layout4)

        # Odoo UI
        odoo_layout = QHBoxLayout()
        odoo_layout.addWidget(QLabel("Odoo URL:"))
        self.odoo_url_edit = QLineEdit(self.config["Odoo"]["url"])
        odoo_layout.addWidget(self.odoo_url_edit)
        layout.addLayout(odoo_layout)

        odoo_layout2 = QHBoxLayout()
        odoo_layout2.addWidget(QLabel("DB:"))
        self.odoo_db_edit = QLineEdit(self.config["Odoo"]["db"])
        odoo_layout2.addWidget(self.odoo_db_edit)
        layout.addLayout(odoo_layout2)

        odoo_layout3 = QHBoxLayout()
        odoo_layout3.addWidget(QLabel("User:"))
        self.odoo_user_edit = QLineEdit(self.config["Odoo"]["username"])
        odoo_layout3.addWidget(self.odoo_user_edit)
        layout.addLayout(odoo_layout3)

        odoo_layout4 = QHBoxLayout()
        odoo_layout4.addWidget(QLabel("Password:"))
        self.odoo_pass_edit = QLineEdit(self.config["Odoo"]["password"])
        self.odoo_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        odoo_layout4.addWidget(self.odoo_pass_edit)
        layout.addLayout(odoo_layout4)

        # Sync UI
        sync_layout = QHBoxLayout()
        sync_layout.addWidget(QLabel("Tables (comma-separated, empty=all):"))
        self.tables_edit = QLineEdit(self.config["Sync"]["tables_to_sync"])
        sync_layout.addWidget(self.tables_edit)
        layout.addLayout(sync_layout)

        sync_layout2 = QHBoxLayout()
        sync_layout2.addWidget(QLabel("Sync Period (seconds):"))
        self.sync_spin = QSpinBox()
        self.sync_spin.setRange(1, 999999)
        self.sync_spin.setValue(int(self.config["Sync"]["sync_period"]))
        sync_layout2.addWidget(self.sync_spin)
        layout.addLayout(sync_layout2)

        self.force_check = QCheckBox("Force Sync")
        self.force_check.setChecked(self.config["Sync"]["force_sync"].lower() == "true")
        layout.addWidget(self.force_check)

        # Timeout settings
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("Timeout (seconds):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(30, 3600)
        self.timeout_spin.setValue(int(self.config.get("Sync", "timeout_seconds", fallback="300")))
        timeout_layout.addWidget(self.timeout_spin)
        layout.addLayout(timeout_layout)

        retry_layout = QHBoxLayout()
        retry_layout.addWidget(QLabel("Max Retries:"))
        self.retry_spin = QSpinBox()
        self.retry_spin.setRange(1, 10)
        self.retry_spin.setValue(int(self.config.get("Sync", "max_retries", fallback="3")))
        retry_layout.addWidget(self.retry_spin)
        layout.addLayout(retry_layout)

        # Progress section
        progress_layout = QVBoxLayout()
        progress_layout.addWidget(QLabel("Sync Progress:"))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        progress_layout.addWidget(self.status_label)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(120)
        self.log_display.setReadOnly(True)
        
        # Set custom monospace font
        monospace_font_family = load_custom_font()
        self.log_display.setStyleSheet(f"background-color: #f5f5f5; font-family: '{monospace_font_family}'; font-size: 9pt;")
        progress_layout.addWidget(self.log_display)
        
        layout.addLayout(progress_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Config")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)

        self.sync_btn = QPushButton("Sync Now")
        self.sync_btn.clicked.connect(self.perform_sync)
        btn_layout.addWidget(self.sync_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_sync)
        self.cancel_btn.setVisible(False)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(int(self.config["Sync"]["sync_period"]) * 1000)
        self.timer.timeout.connect(self.perform_sync)
        self.timer.start()

        # Tray icon
        icon = QIcon(get_icon_path())
        self.tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show_main_window)
        self.tray_menu.addAction(show_action)

        sync_action = QAction("Sync Now", self)
        sync_action.triggered.connect(self.perform_sync)
        self.tray_menu.addAction(sync_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.exit_app)
        self.tray_menu.addAction(exit_action)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("SQL to Odoo Sync")
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_main_window()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage(
            "Still Running",
            "The app is minimized to tray and running in the background.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def show_main_window(self):
        self.showNormal()
        self.activateWindow()

    def exit_app(self):
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.cancel()
            self.sync_worker.wait(3000)  # Wait up to 3 seconds for graceful shutdown
        self.tray_icon.hide()
        QApplication.quit()

    def save_config(self):
        self.config["Database"]["server"] = self.db_server_edit.text()
        self.config["Database"]["databases"] = self.db_databases_edit.text()
        self.config["Database"]["username"] = self.db_user_edit.text()
        self.config["Database"]["password"] = self.db_pass_edit.text()

        self.config["Odoo"]["url"] = self.odoo_url_edit.text()
        self.config["Odoo"]["db"] = self.odoo_db_edit.text()
        self.config["Odoo"]["username"] = self.odoo_user_edit.text()
        self.config["Odoo"]["password"] = self.odoo_pass_edit.text()

        self.config["Sync"]["tables_to_sync"] = self.tables_edit.text()
        self.config["Sync"]["sync_period"] = str(self.sync_spin.value())
        self.config["Sync"]["force_sync"] = str(self.force_check.isChecked())
        self.config["Sync"]["timeout_seconds"] = str(self.timeout_spin.value())
        self.config["Sync"]["max_retries"] = str(self.retry_spin.value())

        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

        self.timer.setInterval(int(self.config["Sync"]["sync_period"]) * 1000)
        logging.info("Configuration saved.")
        QMessageBox.information(
            self, "Config Saved", "Configuration successfully saved."
        )

    def perform_sync(self):
        """Start asynchronous sync operation"""
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.information(self, "Sync in Progress", "A sync operation is already running.")
            return
        
        # Update config from UI before syncing
        self.update_config_from_ui()
        
        # Create and start worker thread
        force = self.force_check.isChecked()
        self.sync_worker = SyncWorker(self.config, force)
        
        # Connect signals
        self.sync_worker.progress_updated.connect(self.on_progress_updated)
        self.sync_worker.sync_completed.connect(self.on_sync_completed)
        self.sync_worker.log_message.connect(self.on_log_message)
        
        # Update UI state
        self.sync_btn.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_display.clear()
        
        # Start the worker
        self.sync_worker.start()
        
    def cancel_sync(self):
        """Cancel the current sync operation"""
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.cancel()
            self.status_label.setText("Cancelling sync...")
            self.cancel_btn.setEnabled(False)
    
    def update_config_from_ui(self):
        """Update config object from UI values"""
        self.config["Database"]["server"] = self.db_server_edit.text()
        self.config["Database"]["databases"] = self.db_databases_edit.text()
        self.config["Database"]["username"] = self.db_user_edit.text()
        self.config["Database"]["password"] = self.db_pass_edit.text()
        
        self.config["Odoo"]["url"] = self.odoo_url_edit.text()
        self.config["Odoo"]["db"] = self.odoo_db_edit.text()
        self.config["Odoo"]["username"] = self.odoo_user_edit.text()
        self.config["Odoo"]["password"] = self.odoo_pass_edit.text()
        
        self.config["Sync"]["tables_to_sync"] = self.tables_edit.text()
        self.config["Sync"]["timeout_seconds"] = str(self.timeout_spin.value())
        self.config["Sync"]["max_retries"] = str(self.retry_spin.value())
    
    def on_progress_updated(self, percentage, message):
        """Handle progress updates from worker thread"""
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)
    
    def on_sync_completed(self, success, message):
        """Handle sync completion from worker thread"""
        # Reset UI state
        self.sync_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        
        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("Sync completed successfully!")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            
            # Show tray notification
            self.tray_icon.showMessage(
                "Sync Completed",
                message,
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
            
            # Hide progress bar after a delay
            QTimer.singleShot(3000, lambda: self.progress_bar.setVisible(False))
            QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet("color: #666; font-style: italic;"))
            QTimer.singleShot(3000, lambda: self.status_label.setText("Ready"))
        else:
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"Sync failed: {message}")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Show error dialog
            QMessageBox.critical(self, "Sync Error", message)
            
            # Reset status after delay
            QTimer.singleShot(5000, lambda: self.status_label.setStyleSheet("color: #666; font-style: italic;"))
            QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))
    
    def on_log_message(self, message):
        """Handle log messages from worker thread"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_display.append(formatted_message)
        
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    config_path = "config.ini"
    ensure_config_exists(config_path)
    setup_logging()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Load custom font early to avoid font resolution warnings
    monospace_font_family = load_custom_font()
    logging.info(f"Loaded monospace font: {monospace_font_family}")

    icon = QIcon(get_icon_path())
    app.setWindowIcon(icon)

    window = MainWindow(config_path)
    window.show()

    try:
        sys.exit(app.exec())
    except Exception as exc:
        logging.error("Fatal error on exit: %s", exc)


if __name__ == "__main__":
    main()