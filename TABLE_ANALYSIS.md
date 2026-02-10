# Database Schema Analysis - WinScanLLM

**Date:** 2026-02-10
**Purpose:** Rationalize all tables before creating unified migration

---

## Core Tables (KEEP - Essential)

### 1. `image_files` - Image File Registry
**Purpose:** Central registry of all scanned image files with lifecycle tracking
**Status:** ✅ ESSENTIAL - Keep with modifications
**Current Schema:**
```sql
- id (PK)
- file_path (UNIQUE, indexed)
- file_hash (for change detection)
- directory_path, filename, file_size, file_mtime
- status ('registered', 'analyzing', 'analyzed', 'deleted')
- rotation (user-applied rotation in degrees)
- discovered_at, last_seen_at, deleted_at
- analysis_id (FK to analysis_results) ⚠️ PROBLEMATIC
- output_filename
```

**Issues:**
1. `analysis_id` creates 1:1 relationship but image can have MULTIPLE analyses (re-analysis with different providers)
2. Should reference LATEST or PRIMARY analysis, not just any analysis
3. `output_filename` duplicates metadata.output_filename

**Recommendation:**
```sql
CREATE TABLE image_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT UNIQUE NOT NULL,
    file_hash TEXT NOT NULL,

    -- File metadata
    directory_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,

    -- Lifecycle tracking
    status TEXT DEFAULT 'registered',  -- registered, analyzing, analyzed, deleted

    -- Timestamps
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);
```
- **REMOVE:** `analysis_id` (get latest via JOIN), `rotation` (moved to metadata), `output_filename` (moved to metadata)

---

### 2. `analysis_results` - LLM Analysis Audit Trail
**Purpose:** Track all LLM analyses performed (provenance, not metadata)
**Status:** ✅ ESSENTIAL - Keep as-is (after Migration 16)
**Current Schema:**
```sql
- id (PK)
- image_file_id (FK to image_files) ✅ Good
- provider_name, model_name, model_options
- prompt_text, response_text, extracted_metadata (JSON)
- confidence_score (LLM's original confidence)
- had_error
- analyzed_at, processing_time_ms
```

**Assessment:** Perfect after Migration 16 refactor. Purely audit trail.

**Recommendation:** ✅ Keep as-is

---

### 3. `metadata` - Normalized Document Metadata (Single Source of Truth)
**Purpose:** User-editable, normalized metadata for each image
**Status:** ✅ ESSENTIAL - Keep with modifications
**Current Schema:**
```sql
- id (PK)
- image_file_id (FK, UNIQUE) -- One metadata record per image
- analysis_result_id (FK) -- Which analysis created this
- pdf_file_id (FK) -- Which PDF includes this image
- company, document_type, document_date
- page_number, total_pages, belongs_to_same_doc
- confidence_score (user-editable, may differ from LLM original)
- tax_related, document_category
- rotation (normalized degrees)
- output_filename
- user_verified, auto_approved, last_edited_by
- created_at, updated_at
```

**Issues:**
1. `pdf_file_id` creates tight coupling - should be many-to-many (image can be in multiple PDFs)
2. `rotation` duplicates image_files.rotation - which is authoritative?

**Recommendation:**
```sql
CREATE TABLE metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Foreign Keys
    image_file_id INTEGER NOT NULL UNIQUE,  -- One metadata per image
    analysis_result_id INTEGER,  -- Which analysis seeded this (nullable for manual)

    -- Document Metadata (user-editable)
    company TEXT,
    document_type TEXT,
    document_date TEXT,
    page_number INTEGER,
    total_pages INTEGER,
    belongs_to_same_doc BOOLEAN DEFAULT 0,
    confidence_score REAL,
    tax_related BOOLEAN DEFAULT 0,
    document_category TEXT,

    -- Display preferences
    rotation INTEGER DEFAULT 0,  -- User-applied rotation
    output_filename TEXT,

    -- Provenance
    user_verified BOOLEAN DEFAULT 0,
    auto_approved BOOLEAN DEFAULT 1,
    last_edited_by TEXT DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_result_id) REFERENCES analysis_results(id) ON DELETE SET NULL
);
```
- **REMOVE:** `pdf_file_id` (use junction table instead)

---

### 4. `pdf_files` - Generated PDF Tracking
**Purpose:** Track PDFs generated from image bundles
**Status:** ✅ ESSENTIAL - Keep with modifications
**Current Schema:**
```sql
- id (PK)
- pdf_path (UNIQUE)
- pdf_filename, file_hash, file_size, page_count
- bundle_id (FK to document_bundles)
- generation_status
- source_image_ids (JSON array) ⚠️ DENORMALIZED
- generated_at
```

**Issues:**
1. `source_image_ids` as JSON is denormalized - can't query efficiently
2. Should use junction table for many-to-many relationship

**Recommendation:**
```sql
CREATE TABLE pdf_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_path TEXT UNIQUE NOT NULL,
    pdf_filename TEXT NOT NULL,
    file_hash TEXT,
    file_size INTEGER,
    page_count INTEGER,
    bundle_id INTEGER,
    generation_status TEXT DEFAULT 'completed',
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bundle_id) REFERENCES document_bundles(id) ON DELETE SET NULL
);

-- NEW: Junction table for many-to-many
CREATE TABLE pdf_image_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_file_id INTEGER NOT NULL,
    image_file_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL,  -- Page position in PDF

    FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE,
    FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
    UNIQUE(pdf_file_id, page_number)  -- Each page number used once per PDF
);
```

---

### 5. `document_bundles` - AI-Suggested Document Groups
**Purpose:** Track AI suggestions for grouping images into documents
**Status:** ✅ KEEP - Useful for workflow
**Current Schema:**
```sql
- id (PK)
- bundle_name, company, document_type, document_date, total_pages
- confidence_score, confidence_level
- file_paths (JSON array) ⚠️ DENORMALIZED
- status ('suggested', 'approved', 'rejected', 'completed')
- pdf_path
- user_action, action_timestamp
- created_at, updated_at
```

**Issues:**
1. `file_paths` as JSON - should use junction table
2. `pdf_path` redundant with pdf_files.pdf_path (FK better)
3. Metadata fields (company, etc.) duplicate metadata table

**Recommendation:**
```sql
CREATE TABLE document_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_name TEXT,

    -- AI confidence
    confidence_score REAL,
    confidence_level TEXT,  -- 'high', 'medium', 'low'

    -- Workflow status
    status TEXT DEFAULT 'suggested',  -- suggested, approved, rejected, completed
    user_action TEXT,
    action_timestamp TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- NEW: Junction table for bundle images
CREATE TABLE bundle_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bundle_id INTEGER NOT NULL,
    image_file_id INTEGER NOT NULL,
    sequence_order INTEGER NOT NULL,  -- Order within bundle

    FOREIGN KEY (bundle_id) REFERENCES document_bundles(id) ON DELETE CASCADE,
    FOREIGN KEY (image_file_id) REFERENCES image_files(id) ON DELETE CASCADE,
    UNIQUE(bundle_id, image_file_id),  -- Each image once per bundle
    UNIQUE(bundle_id, sequence_order)  -- Each sequence position once
);
```
- **REMOVE:** Metadata fields (derive from metadata table), `file_paths` JSON, `pdf_path`

---

## Configuration Tables (KEEP)

### 6. `source_directories` - Scan Directory Config
**Purpose:** Track which directories to scan for images
**Status:** ✅ KEEP - Necessary for multi-directory support
**Recommendation:** Keep as-is, well-designed

---

### 7. `llm_providers` - LLM Provider Configuration
**Purpose:** Store LLM provider settings (Ollama, Claude CLI, etc.)
**Status:** ⚠️ QUESTIONABLE - Config file might be better
**Analysis:**
- Currently stored in INI file via ConfigManager
- Database storage adds complexity
- Not currently used in codebase

**Recommendation:** ❌ **REMOVE** - Use ConfigManager (INI file) instead

---

## Audit/History Tables (KEEP)

### 8. `audit_trail` - User Action Logging
**Purpose:** Optional tracking of user actions
**Status:** ✅ KEEP - Useful for debugging/compliance
**Recommendation:** Keep as-is

---

## Problematic/Legacy Tables (REMOVE)

### 9. `rotation_preferences` - Legacy Rotation Storage
**Purpose:** Store per-file rotation (DEPRECATED in Migration 12)
**Status:** ❌ **REMOVE** - Replaced by metadata.rotation
**Recommendation:** Delete entirely

---

### 10. `analysis_errors` - Error Tracking
**Purpose:** Track analysis failures
**Status:** ❌ **REMOVE** - Redundant with analysis_results.had_error
**Analysis:**
- Duplicate tracking - `analysis_results` already has `had_error` flag
- Can store error details in `analysis_results.response_text`
- Adds unnecessary complexity

**Recommendation:** ❌ **REMOVE** - Use `analysis_results.had_error` + `response_text`

---

### 11. `archived_metadata` - Completed Document Archive
**Purpose:** Store metadata for bundled/completed documents
**Status:** ⚠️ QUESTIONABLE - Unclear value
**Analysis:**
- Stores JSON blobs of source files and page metadata
- Redundant with `pdf_files` + `metadata` tables
- Not clear when/how this is used

**Recommendation:** ❌ **REMOVE** - Use `pdf_files` with junction tables instead

---

### 12. `schema_version` - Migration Tracking
**Purpose:** Track applied migrations
**Status:** ✅ KEEP - Standard practice
**Recommendation:** Keep for single migration

---

## Summary of Changes

### Tables to KEEP (8):
1. `image_files` - Modified (remove analysis_id, rotation, output_filename)
2. `analysis_results` - As-is ✅
3. `metadata` - Modified (remove pdf_file_id)
4. `pdf_files` - Modified (remove source_image_ids JSON)
5. `document_bundles` - Modified (remove metadata fields, file_paths JSON)
6. `source_directories` - As-is ✅
7. `audit_trail` - As-is ✅
8. `schema_version` - As-is ✅

### New Junction Tables (2):
1. `pdf_image_pages` - Many-to-many: PDFs ↔ Images
2. `bundle_images` - Many-to-many: Bundles ↔ Images

### Tables to REMOVE (4):
1. `llm_providers` - Use ConfigManager instead
2. `rotation_preferences` - Replaced by metadata.rotation
3. `analysis_errors` - Use analysis_results.had_error
4. `archived_metadata` - Use pdf_files instead

---

## Key Design Principles

1. **Single Source of Truth:** `metadata` table is authoritative for document data
2. **Audit Trail:** `analysis_results` tracks ALL analyses (multiple per image)
3. **Normalized Relationships:** Use junction tables, not JSON arrays
4. **No Duplication:** Remove redundant columns across tables
5. **Clear Ownership:** Each table has one clear responsibility

---

## Next Steps

1. Review this analysis
2. Create single unified migration (version 1)
3. Remove all previous migrations (2-16)
4. Update all repositories to match new schema
5. Update tests
