"""Generate template database files for first-time setup"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from metadata_db import MetadataDB
from analysis_db import AnalysisDB

# Create template database in data folder
template_db_path = os.path.join('data', 'metadata.db')

# Remove existing template if present
if os.path.exists(template_db_path):
    os.remove(template_db_path)
    print(f"Removed existing template: {template_db_path}")

# Create fresh databases with all tables
print(f"Creating template database: {template_db_path}")
metadata_db = MetadataDB(template_db_path)
analysis_db = AnalysisDB(template_db_path)

print("Template database created successfully!")
print("\nDatabase schema includes:")
print("- MetadataDB tables: original_files, archived_files, schema_version")
print("- AnalysisDB tables: analysis_results, llm_providers, source_directories,")
print("                     document_bundles, rotation_preferences, audit_trail")

# Close databases
metadata_db.close()
analysis_db.close()

print(f"\n[OK] Template database ready: {template_db_path}")
