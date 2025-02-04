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
)
from PyQt6.QtGui import QIcon, QAction, QCursor
from PyQt6.QtCore import QTimer, Qt

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


def send_csv_to_odoo(
    config: configparser.ConfigParser, csv_file: str, table_name: str, db_name: str
):
    url = config["Odoo"]["url"]
    db = config["Odoo"]["db"]
    username = config["Odoo"]["username"]
    password = config["Odoo"]["password"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, password, {})
    if not uid:
        raise Exception("Failed to authenticate to Odoo.")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    with open(csv_file, "rb") as f:
        file_data = f.read()
    file_base64 = base64.b64encode(file_data).decode("utf-8")
    file_name = os.path.basename(csv_file)

    attachment_id = models.execute_kw(
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

    existing_ids = models.execute_kw(
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
        models.execute_kw(
            db, uid, password, "mssql.sync.data", "write", [[sync_data_id], sync_data]
        )
    else:
        sync_data_id = models.execute_kw(
            db, uid, password, "mssql.sync.data", "create", [sync_data]
        )

    # Only create details if they do not already exist
    for column in columns:
        column_name = column[0]
        existing_detail_ids = models.execute_kw(
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
            models.execute_kw(
                db,
                uid,
                password,
                "mssql.sync.table.details",
                "create",
                [column_data],
            )

    # Clean up any duplicates that may already be in the database
    existing_details = models.execute_kw(
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
        models.execute_kw(
            db,
            uid,
            password,
            "mssql.sync.table.details",
            "unlink",
            [duplicates_to_remove],
        )

    table_data = {"sync_data_id": sync_data_id, "attachment_id": attachment_id}
    models.execute_kw(
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


class MainWindow(QMainWindow):
    def __init__(self, config_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config_path = config_path
        self.config = load_config(config_path)

        self.setWindowTitle("SQL to Odoo Sync App")
        self.resize(600, 300)

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

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Config")
        self.save_btn.clicked.connect(self.save_config)
        btn_layout.addWidget(self.save_btn)

        self.sync_btn = QPushButton("Sync Now")
        self.sync_btn.clicked.connect(self.perform_sync)
        btn_layout.addWidget(self.sync_btn)
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

        with open(self.config_path, "w", encoding="utf-8") as f:
            self.config.write(f)

        self.timer.setInterval(int(self.config["Sync"]["sync_period"]) * 1000)
        logging.info("Configuration saved.")
        QMessageBox.information(
            self, "Config Saved", "Configuration successfully saved."
        )

    def perform_sync(self):
        force = self.force_check.isChecked()
        try:
            databases_str = self.config["Database"]["databases"]
            database_list = [d.strip() for d in databases_str.split(",") if d.strip()]

            for db_name in database_list:
                with connect_to_sql_server_for_db(self.config, db_name) as connection:
                    all_tables = fetch_tables_list(connection)

                    to_sync = self.tables_edit.text().strip()
                    if to_sync:
                        table_list = [
                            x.strip() for x in to_sync.split(",") if x.strip()
                        ]
                    else:
                        table_list = all_tables

                    for table in table_list:
                        csv_file_path = fetch_table_data_as_csv(
                            connection, table, db_name
                        )

                        # Keep only 3 latest CSV files for this table
                        csv_pattern = os.path.join(
                            "generated_csv", f"{db_name}_{table}_*.csv"
                        )
                        existing_csvs = sorted(
                            Path().glob(csv_pattern), key=os.path.getctime, reverse=True
                        )
                        # Skip the newest file (just created) and remove all but 2 older files
                        for old_file in existing_csvs[3:]:
                            try:
                                os.remove(old_file)
                                logging.info(f"Removed old CSV file: {old_file}")
                            except Exception as e:
                                logging.warning(
                                    f"Failed to remove old CSV file {old_file}: {e}"
                                )

                        file_hash = compute_file_hash(csv_file_path)
                        prev_hash_path = os.path.join(
                            "generated_csv", f"{db_name}_{table}_hash.txt"
                        )

                        if os.path.exists(prev_hash_path):
                            with open(prev_hash_path, "r", encoding="utf-8") as hf:
                                old_hash = hf.read().strip()
                        else:
                            old_hash = ""

                        if force or (file_hash != old_hash):
                            send_csv_to_odoo(self.config, csv_file_path, table, db_name)
                            with open(prev_hash_path, "w", encoding="utf-8") as hf:
                                hf.write(file_hash)
                        else:
                            logging.info(
                                f"No change detected for table `{table}` in DB `{db_name}`. Skipping upload."
                            )

            logging.info("Sync completed successfully.")
            self.tray_icon.showMessage(
                "Sync Completed",
                "Data sync to Odoo finished.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        except Exception as e:
            logging.error("Error during sync: %s\n%s", e, traceback.format_exc())
            QMessageBox.critical(self, "Sync Error", str(e))


def main():
    config_path = "config.ini"
    ensure_config_exists(config_path)
    setup_logging()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

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
