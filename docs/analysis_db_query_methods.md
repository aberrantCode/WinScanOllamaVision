# Analysis DB Query Methods Documentation

## Overview

This document describes the comprehensive query methods added to `src/analysis_db.py` for the Analysis Status Window transformation. These methods provide detailed insights into the document collection, analysis progress, and bundling statistics.

## Implementation Summary

**Date**: 2026-02-04
**Purpose**: Support Collection Dashboard transformation
**Database**: SQLite with optimized indices

---

## Main Query Methods

### 1. `get_collection_summary()` → Dict[str, Any]

Returns comprehensive collection-wide statistics for the dashboard.

**Returns**:
```python
{
    'files_detected': int,           # Total files in source directories
    'files_analyzed': int,            # Count from analysis_results
    'high_confidence_count': int,     # Confidence >= 0.8
    'pages_bundled': int,             # Count of pages in bundles
    'documents_archived': int,        # Count from archived_metadata
    'processing_speed': float,        # Pages per minute (last 100)
    'eta_minutes': float,             # Estimated time remaining
    'avg_confidence': float,          # Average confidence score (0-1)
    'error_rate': float,              # Percentage of errors
    'metadata_completeness': {        # Per-field percentages
        'company': float,
        'document_type': float,
        'document_date': float,
        'page_number': float,
        'total_pages': float
    },
    'cache_hit_rate': float           # Percentage cached
}
```

**Example Usage**:
```python
db = AnalysisDB()
summary = db.get_collection_summary()
print(f"Analyzed: {summary['files_analyzed']} / {summary['files_detected']}")
print(f"Cache Hit Rate: {summary['cache_hit_rate']:.1f}%")
print(f"ETA: {summary['eta_minutes']:.1f} minutes")
```

---

### 2. `get_action_items()` → Dict[str, int]

Returns counts for items requiring user action.

**Returns**:
```python
{
    'pending_analysis': int,    # Files detected but not analyzed
    'pending_bundles': int,     # Bundles in 'suggested' status
    'failed_files': int,        # Files with analysis errors
    'unbundled_files': int      # Analyzed files not in any bundle
}
```

**Example Usage**:
```python
actions = db.get_action_items()
if actions['pending_bundles'] > 0:
    print(f"Review {actions['pending_bundles']} pending bundles")
if actions['failed_files'] > 0:
    print(f"Retry {actions['failed_files']} failed analyses")
```

---

### 3. `get_document_insights()` → Dict[str, Any]

Returns document-level insights and distribution statistics.

**Returns**:
```python
{
    'total_documents': int,              # Total archived documents
    'total_archived_pages': int,         # Total pages in archived docs
    'avg_pages_per_doc': float,          # Average pages per document
    'bundle_acceptance_rate': float,     # Percentage accepted
    'pending_bundle_count': int,         # Number of pending bundles
    'type_distribution': Dict[str, int], # Document type → count
    'company_distribution': Dict[str, int] # Company → count
}
```

**Example Usage**:
```python
insights = db.get_document_insights()
print(f"Archived: {insights['total_documents']} documents")
print(f"Avg Pages: {insights['avg_pages_per_doc']:.1f}")

# Show top 5 document types
for doc_type, count in list(insights['type_distribution'].items())[:5]:
    print(f"  {doc_type}: {count}")
```

---

### 4. `get_analyzed_pages_detailed(filters=None)` → List[Dict[str, Any]]

Returns all analysis results with full metadata for grid display.

**Parameters**:
```python
filters: Optional[Dict[str, Any]] = {
    'company': str,           # Filter by company name (LIKE)
    'document_type': str,     # Filter by document type (LIKE)
    'confidence_min': float,  # Minimum confidence score
    'date_from': str,         # Filter by analyzed_at >= date
    'date_to': str,           # Filter by analyzed_at <= date
    'search_text': str,       # Search in file_path (LIKE)
    'status': str             # 'analyzed', 'cached', or 'failed'
}
```

**Returns** (18 fields per record):
```python
[
    {
        'id': int,
        'file_path': str,
        'file_hash': str,
        'provider_name': str,
        'model_name': str,
        'document_type': str,
        'company': str,
        'document_date': str,
        'page_number': int,
        'total_pages': int,
        'belongs_to_same_doc': bool,
        'confidence_score': float,
        'rotation_needed': bool,
        'suggested_rotation': int,
        'rotation_confidence': str,
        'analyzed_at': str,
        'processing_time_ms': int,
        'is_cached': bool
    },
    ...
]
```

**Example Usage**:
```python
# Get all high-confidence invoices from Company A
filters = {
    'company': 'Company A',
    'document_type': 'Invoice',
    'confidence_min': 0.8
}
pages = db.get_analyzed_pages_detailed(filters=filters)

for page in pages:
    print(f"{page['file_path']}: {page['confidence_score']:.0%} confidence")
```

---

## Helper Methods

These methods are used internally by the main query methods but can also be called directly.

### File Counting

- **`_count_detected_files()`** → int
  Scans all active source directories for image files (.png, .jpg, .jpeg, .tiff, .tif)

- **`_count_high_confidence()`** → int
  Counts analysis results with confidence_score >= 0.8

- **`_count_bundled_pages()`** → int
  Counts total pages in all non-rejected bundles

### Performance Calculations

- **`_calculate_processing_speed()`** → float
  Returns pages per minute based on last 100 analyses

- **`_calculate_eta(files_detected, files_analyzed, processing_speed)`** → float
  Calculates estimated minutes remaining

### Metadata Analysis

- **`_get_metadata_completeness()`** → Dict[str, float]
  Returns per-field completion percentages for company, document_type, document_date, page_number, total_pages

### Bundle Statistics

- **`_count_pending_bundles()`** → int
  Counts bundles with status='suggested'

- **`_calc_bundle_acceptance_rate()`** → float
  Returns percentage of bundles with status='accepted'

### Distribution Analysis

- **`_get_type_distribution()`** → Dict[str, int]
  Returns document type → count mapping (ordered by count descending)

- **`_get_company_distribution()`** → Dict[str, int]
  Returns company → count mapping (ordered by count descending)

---

## Database Indices

For optimal query performance, the following indices were added:

```sql
-- Confidence-based filtering
CREATE INDEX IF NOT EXISTS idx_analysis_confidence
ON analysis_results(confidence_score);

-- Company and type filtering
CREATE INDEX IF NOT EXISTS idx_analysis_company_type
ON analysis_results(company, document_type);

-- Date-based sorting
CREATE INDEX IF NOT EXISTS idx_analysis_date
ON analysis_results(analyzed_at DESC);

-- Bundle status filtering
CREATE INDEX IF NOT EXISTS idx_bundle_status
ON document_bundles(status);
```

---

## Error Handling

All methods handle edge cases gracefully:

- **Empty database**: Returns sensible defaults (0 counts, 0.0 percentages)
- **Missing values**: NULL values excluded from averages
- **Division by zero**: Returns 0 instead of raising exception
- **Missing tables**: `archived_metadata` table may not exist (separate MetadataDB)

Example:
```python
summary = db.get_collection_summary()
# If no files analyzed, avg_confidence will be 0.0 (not error)
```

---

## Performance Considerations

### Optimizations

1. **Indexed queries**: All common filter fields have indices
2. **Aggregate functions**: Use SQL aggregates (COUNT, AVG, SUM) instead of Python loops
3. **Cached results**: Helper methods called once per query
4. **Limit subqueries**: Processing speed uses only last 100 records

### Large Datasets

For collections with 10,000+ files:

- **`get_analyzed_pages_detailed()`**: Use filters to reduce result set
- **File counting**: Only counts files in active directories
- **Distribution queries**: Automatically ordered by count (no full sort needed)

---

## Testing

Comprehensive tests verify:

- Empty database handling
- Various confidence levels
- Missing/NULL values
- Cache hit rate calculations
- Bundle acceptance rates
- Filtered queries
- Distribution statistics
- Performance metrics

Run tests:
```bash
python test_analysis_db_queries.py          # Basic functionality
python test_no_unicode.py                   # Edge cases
```

---

## Integration with UI

These methods are designed for use in the Analysis Status Window:

### Collection Status Tab
- `get_collection_summary()` → Dashboard metrics
- `get_action_items()` → Action buttons with counts

### File Details Grid
- `get_analyzed_pages_detailed()` → Populate table
- Filters → User-configurable filtering

### Document Insights
- `get_document_insights()` → Charts and distribution views

---

## Future Enhancements

Potential improvements:

1. **Caching**: Cache expensive queries (file counting) with TTL
2. **Pagination**: Add LIMIT/OFFSET support to `get_analyzed_pages_detailed()`
3. **Time-based filters**: Add "last 7 days", "last 30 days" presets
4. **Export support**: Add CSV/JSON export methods
5. **Real-time updates**: Add observer pattern for live dashboard updates

---

## Example: Complete Workflow

```python
from analysis_db import AnalysisDB

# Initialize
db = AnalysisDB()

# Get overview
summary = db.get_collection_summary()
print(f"Progress: {summary['files_analyzed']}/{summary['files_detected']}")
print(f"Average Confidence: {summary['avg_confidence']:.0%}")

# Check for actions needed
actions = db.get_action_items()
if actions['pending_bundles'] > 0:
    print(f"Review {actions['pending_bundles']} suggested bundles")

# Get detailed insights
insights = db.get_document_insights()
print(f"Archived {insights['total_documents']} documents")
print(f"Bundle acceptance rate: {insights['bundle_acceptance_rate']:.1f}%")

# View top document types
print("\nTop Document Types:")
for doc_type, count in list(insights['type_distribution'].items())[:5]:
    print(f"  {doc_type}: {count}")

# Get filtered pages
pages = db.get_analyzed_pages_detailed(filters={
    'confidence_min': 0.8,
    'status': 'analyzed'
})
print(f"\nHigh-confidence pages: {len(pages)}")

db.close()
```

---

## Changelog

### 2026-02-04 - Initial Implementation
- Added 3 main query methods
- Added 11 helper calculation methods
- Created 4 database indices
- Comprehensive test coverage
- Edge case handling
- Documentation complete

---

## See Also

- `docs/analysis_status_window_design.md` - UI design specification
- `src/analysis_db.py` - Implementation
- `test_analysis_db_queries.py` - Basic tests
- `test_analysis_db_edge_cases.py` - Edge case tests
