"""Test script to check directory configuration."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config.config_manager import ConfigManager


def main():
    """Test directory retrieval."""
    print("Testing ConfigManager.get_directories()...\n")

    config = ConfigManager()
    directories = config.get_directories()

    print(f"Number of directories: {len(directories)}")
    print(f"Directories: {directories}\n")

    if not directories:
        print("WARNING: No directories found!")
        print("Checking raw config value...")
        raw_value = config.get_setting("SourceDirectories", "directories", "NOT_FOUND")
        print(f"Raw config value: {raw_value}\n")

        # Check if section exists
        if "SourceDirectories" in config.config:
            print("SourceDirectories section exists in config")
            print(f"Section contents: {dict(config.config['SourceDirectories'])}\n")
        else:
            print("SourceDirectories section NOT FOUND in config!\n")

        # Show config file location
        print(f"Config file location: {config.config_file}")
        if os.path.exists(config.config_file):
            print("Config file exists")
            with open(config.config_file) as f:
                print("\nConfig file contents:")
                print("=" * 60)
                print(f.read())
                print("=" * 60)
        else:
            print("Config file DOES NOT EXIST!")
    else:
        print("Directories found successfully!")
        for i, directory in enumerate(directories, 1):
            print(f"  {i}. {directory}")
            if os.path.exists(directory):
                print("     ✓ Directory exists on disk")
            else:
                print("     ✗ Directory does NOT exist on disk")


if __name__ == "__main__":
    main()
