"""
AppData Directory Manager for WinScanLLM

Handles initialization and management of user-specific application data in %APPDATA%\\WinScanLLM.
Ensures settings and databases are properly initialized and updated without data loss.
"""

import configparser
import os
import shutil
import sqlite3


class AppDataManager:
    """Manages application data directory in user's AppData"""

    APP_NAME = "WinScanLLM"

    def __init__(self, solution_data_dir: str = None):
        """
        Initialize AppData manager

        Args:
            solution_data_dir: Path to the solution's data directory containing templates
        """
        # Get AppData path
        appdata_root = os.getenv("APPDATA")
        if not appdata_root:
            # Fallback for cases where APPDATA isn't set
            appdata_root = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")

        self.appdata_dir = os.path.join(appdata_root, self.APP_NAME)

        # Solution data directory (contains templates)
        if solution_data_dir is None:
            # Default: assume we're in src/ and data/ is at solution root
            src_dir = os.path.dirname(os.path.abspath(__file__))
            solution_data_dir = os.path.join(os.path.dirname(src_dir), "data")
        self.solution_data_dir = solution_data_dir

        # Paths for settings and database
        self.settings_path = os.path.join(self.appdata_dir, "settings.ini")
        self.database_path = os.path.join(self.appdata_dir, "metadata.db")

        # Template paths
        self.template_settings = os.path.join(self.solution_data_dir, "settings.ini")
        self.template_database = os.path.join(self.solution_data_dir, "metadata.db")

    def initialize(self) -> tuple[str, str]:
        """
        Initialize AppData directory and ensure all files are present and up-to-date

        Returns:
            Tuple of (settings_path, database_path) in AppData directory
        """
        # Create AppData directory if it doesn't exist
        if not os.path.exists(self.appdata_dir):
            os.makedirs(self.appdata_dir)
            print(f"Created AppData directory: {self.appdata_dir}")

        # Initialize settings.ini
        self._initialize_settings()

        # Initialize database
        self._initialize_database()

        return self.settings_path, self.database_path

    def _initialize_settings(self):
        """Initialize or update settings.ini in AppData"""
        if not os.path.exists(self.settings_path):
            # First run: copy template from solution data directory
            if os.path.exists(self.template_settings):
                shutil.copy2(self.template_settings, self.settings_path)
                print(f"Copied template settings to: {self.settings_path}")
            else:
                print(f"Warning: Template settings not found at {self.template_settings}")
                print("Settings will be created with defaults by ConfigManager")
        else:
            # Settings exist: check if update is needed
            self._update_settings_if_needed()

    def _update_settings_if_needed(self):
        """
        Update settings.ini by adding missing sections/keys while preserving user values
        """
        if not os.path.exists(self.template_settings):
            # No template available, skip update
            return

        # Load both configs
        user_config = configparser.ConfigParser()
        user_config.read(self.settings_path)

        template_config = configparser.ConfigParser()
        template_config.read(self.template_settings)

        # Track if any changes were made
        changes_made = False

        # Add missing sections and keys from template
        for section in template_config.sections():
            if not user_config.has_section(section):
                # Add entire section from template
                user_config.add_section(section)
                for key, value in template_config.items(section):
                    user_config.set(section, key, value)
                changes_made = True
                print(f"Added new section [{section}] to settings.ini")
            else:
                # Section exists: add missing keys only
                for key, value in template_config.items(section):
                    if not user_config.has_option(section, key):
                        user_config.set(section, key, value)
                        changes_made = True
                        print(f"Added new setting [{section}] {key} to settings.ini")

        # Save updated config if changes were made
        if changes_made:
            # Create backup first
            backup_path = self.settings_path + ".backup"
            shutil.copy2(self.settings_path, backup_path)
            print(f"Created backup: {backup_path}")

            with open(self.settings_path, "w") as f:
                user_config.write(f)
            print("Updated settings.ini with new options (user values preserved)")

    def _initialize_database(self):
        """Initialize or migrate database in AppData"""
        if not os.path.exists(self.database_path):
            # First run: copy template from solution data directory
            if os.path.exists(self.template_database):
                shutil.copy2(self.template_database, self.database_path)
                print(f"Copied template database to: {self.database_path}")
            else:
                print(f"Warning: Template database not found at {self.template_database}")
                print("Database will be created by MetadataDB/AnalysisDB")
        else:
            # Database exists: check if migration is needed
            self._migrate_database_if_needed()

    def _migrate_database_if_needed(self):
        """
        Check database schema version and migrate if needed without data loss
        """
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Check if schema_version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)

            if cursor.fetchone() is None:
                # Old database without schema versioning - needs migration
                print("Detected old database schema - migration may be needed")
                print("MetadataDB/AnalysisDB will handle automatic migration")
            else:
                # Check schema version
                cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                result = cursor.fetchone()
                current_version = result[0] if result else 0

                # Get expected version from template
                template_version = self._get_template_schema_version()

                if current_version < template_version:
                    from services.logging_service import get_logger

                    logger = get_logger()
                    logger.info(
                        f"Database schema update available: v{current_version} -> v{template_version}"
                    )
                    logger.info("Creating backup before migration...")
                    self._backup_database()
                    logger.info("MetadataDB/AnalysisDB will handle automatic migration")
                else:
                    from services.logging_service import get_logger

                    logger = get_logger()
                    logger.info(f"Database schema up to date (v{current_version})")

            conn.close()

        except sqlite3.Error as e:
            from services.logging_service import get_logger

            logger = get_logger()
            logger.error(f"Error checking database version: {e}")

    def _get_template_schema_version(self) -> int:
        """Get schema version from template database"""
        if not os.path.exists(self.template_database):
            return 1  # Default version

        try:
            conn = sqlite3.connect(self.template_database)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='schema_version'
            """)

            if cursor.fetchone() is None:
                return 1

            cursor.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            result = cursor.fetchone()
            version = result[0] if result else 1

            conn.close()
            return version

        except sqlite3.Error:
            return 1

    def _backup_database(self):
        """Create a timestamped backup of the database"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.database_path}.backup_{timestamp}"
        shutil.copy2(self.database_path, backup_path)
        print(f"Created database backup: {backup_path}")

    def get_settings_path(self) -> str:
        """Get path to settings.ini in AppData"""
        return self.settings_path

    def get_database_path(self) -> str:
        """Get path to metadata.db in AppData"""
        return self.database_path

    def get_appdata_dir(self) -> str:
        """Get path to AppData directory"""
        return self.appdata_dir


def initialize_appdata() -> tuple[str, str]:
    """
    Convenience function to initialize AppData directory

    Returns:
        Tuple of (settings_path, database_path)
    """
    manager = AppDataManager()
    return manager.initialize()


# Example usage
if __name__ == "__main__":
    print("WinScanLLM AppData Manager\n")
    print("=" * 60)

    settings_path, db_path = initialize_appdata()

    print("\n" + "=" * 60)
    print("Initialization complete!")
    print(f"\nSettings: {settings_path}")
    print(f"Database: {db_path}")
