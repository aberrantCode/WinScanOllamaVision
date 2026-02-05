# Editable Dropdowns for Document Type and Company

## Overview

Updated both the File Details Dialog and Bundle Review Window to use editable dropdowns (QComboBox with `setEditable(True)`) for Document Type and Company fields. These dropdowns are populated with distinct values from the database, while still allowing users to type new values.

---

## Changes to File Details Dialog

### 1. Updated `__init__` to Accept Database

**File:** `src/ui/file_details_grid.py`

```python
def __init__(self, file_data: dict[str, Any], parent=None, analysis_db=None):
    super().__init__(parent)
    self.file_data = file_data
    self.analysis_db = analysis_db  # Store database reference
```

### 2. Added Method to Get Distinct Values

```python
def _get_distinct_values(self, field_name):
    """Get distinct values for a field from database."""
    if not self.analysis_db:
        return []

    try:
        query = f"SELECT DISTINCT {field_name} FROM analyses WHERE {field_name} IS NOT NULL AND {field_name} != '' ORDER BY {field_name}"
        result = self.analysis_db.conn.execute(query).fetchall()
        return [row[0] for row in result if row[0]]
    except Exception as e:
        print(f"Error getting distinct values for {field_name}: {e}")
        return []
```

### 3. Added Editable Dropdown Widget Type

Added new `widget_type="editable_dropdown"` option to `add_editable_row()`:

```python
elif widget_type == "editable_dropdown":
    input_widget = QComboBox()
    input_widget.setEditable(True)  # Allow typing new values

    # Add distinct values from database
    if distinct_values:
        input_widget.addItems(sorted(distinct_values))

    # Set current value
    if current_value:
        input_widget.setCurrentText(str(current_value))

    input_widget.setStyleSheet(f"""
        QComboBox {{
            background-color: {self.theme_colors["bg_primary"]};
            color: {self.theme_colors["text_primary"]};
            border: 1px solid {self.theme_colors["border"]};
            border-radius: 4px;
            padding: 4px 8px;
        }}
        QComboBox:focus {{
            border: 1px solid {self.theme_colors["accent"]};
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {self.theme_colors["bg_primary"]};
            color: {self.theme_colors["text_primary"]};
            selection-background-color: {self.theme_colors["accent"]};
        }}
    """)
```

### 4. Updated Metadata Fields

```python
# Get distinct values from database
distinct_document_types = self._get_distinct_values("document_type")
distinct_companies = self._get_distinct_values("company")

# Document Type - editable dropdown
add_editable_row(
    "Document Type",
    "document_type",
    self.file_data.get("document_type"),
    "e.g., invoice, receipt, contract",
    widget_type="editable_dropdown",
    distinct_values=distinct_document_types
)

# Company - editable dropdown
add_editable_row(
    "Company",
    "company",
    self.file_data.get("company"),
    "Company or organization name",
    widget_type="editable_dropdown",
    distinct_values=distinct_companies
)
```

### 5. Updated FileDetailsGrid

Added `analysis_db` parameter:

```python
def __init__(self, parent=None, analysis_db=None):
    super().__init__(parent)
    self.analysis_db = analysis_db  # Store database reference
```

Updated dialog instantiation:

```python
if row_data:
    dialog = FileDetailsDialog(row_data, self, analysis_db=self.analysis_db)
    dialog.re_analyze_requested.connect(lambda path: self.re_analyze_requested.emit([path]))
    dialog.exec()
```

---

## Changes to Bundle Review Window

### 1. Added Mock Distinct Values Method

**File:** `src/ui/bundle_review_window_v2.py`

```python
def _get_mock_distinct_values(self, field_name):
    """Get mock distinct values for prototype."""
    if field_name == "document_type":
        return ["Invoice", "Receipt", "Statement", "Contract", "Purchase Order", "Bill of Lading"]
    elif field_name == "company":
        return ["Acme Corporation", "TechCorp Industries", "Global Shipping Co", "ABC Manufacturing", "XYZ Logistics"]
    return []
```

### 2. Added Editable Dropdown Support

Same implementation as File Details Dialog:
- Added `distinct_values` parameter to `add_editable_row()`
- Added `widget_type="editable_dropdown"` case
- Exact same styling as File Details Dialog for consistency

### 3. Updated Metadata Fields

```python
# Get mock distinct values
distinct_document_types = self._get_mock_distinct_values("document_type")
distinct_companies = self._get_mock_distinct_values("company")

# Document Type - editable dropdown
add_editable_row(
    "Document Type",
    "document_type",
    analysis.get("document_type"),
    "e.g., invoice, receipt, contract",
    widget_type="editable_dropdown",
    distinct_values=distinct_document_types
)

# Company - editable dropdown
add_editable_row(
    "Company",
    "company",
    analysis.get("company"),
    "Company or organization name",
    widget_type="editable_dropdown",
    distinct_values=distinct_companies
)
```

---

## User Experience

### Editable Dropdown Features

1. **Dropdown Arrow:** Click to see list of existing values
2. **Type to Filter:** Start typing to filter the list
3. **Type New Value:** Can type a completely new value not in the list
4. **Sorted List:** Values are sorted alphabetically
5. **Current Value:** Pre-populated with existing value if present

### Example Usage

**Document Type Field:**
- Dropdown shows: "Bill of Lading", "Contract", "Invoice", "Purchase Order", "Receipt", "Statement"
- User can select "Invoice" from dropdown
- OR user can type "Credit Note" (new value)

**Company Field:**
- Dropdown shows: "ABC Manufacturing", "Acme Corporation", "Global Shipping Co", "TechCorp Industries", "XYZ Logistics"
- User can select "Acme Corporation" from dropdown
- OR user can type "New Company Inc" (new value)

---

## Backend Integration

### File Details Dialog

When instantiating from main GUI:

```python
from db.analysis_db import AnalysisDB

# Initialize
analysis_db = AnalysisDB()

# Create grid with database
file_details_grid = FileDetailsGrid(parent=self, analysis_db=analysis_db)
```

The dialog will automatically:
1. Query distinct values: `SELECT DISTINCT document_type FROM analyses WHERE document_type IS NOT NULL`
2. Populate dropdown with sorted results
3. Allow user to select existing or type new value

### Bundle Review Window

For production mode, replace `_get_mock_distinct_values()`:

```python
def _get_distinct_values(self, field_name):
    """Get distinct values from database."""
    if not self.analysis_db:
        return self._get_mock_distinct_values(field_name)

    try:
        query = f"SELECT DISTINCT {field_name} FROM analyses WHERE {field_name} IS NOT NULL AND {field_name} != '' ORDER BY {field_name}"
        result = self.analysis_db.conn.execute(query).fetchall()
        return [row[0] for row in result if row[0]]
    except Exception:
        return self._get_mock_distinct_values(field_name)
```

---

## Database Queries

### Distinct Document Types

```sql
SELECT DISTINCT document_type
FROM analyses
WHERE document_type IS NOT NULL
  AND document_type != ''
ORDER BY document_type
```

### Distinct Companies

```sql
SELECT DISTINCT company
FROM analyses
WHERE company IS NOT NULL
  AND company != ''
ORDER BY company
```

---

## Testing

### Test File Details Dialog

1. Ensure `analysis_db` is passed when creating `FileDetailsGrid`
2. Open a file's details
3. Click on Document Type field - should show dropdown arrow
4. Click dropdown - should show distinct document types from database
5. Type a new value - should accept and save it
6. Same for Company field

### Test Bundle Review Window

```bash
python scripts/test_bundle_review_window.py
```

1. Open window
2. Click on Document Type field
3. Should see dropdown with: "Bill of Lading", "Contract", "Invoice", "Purchase Order", "Receipt", "Statement"
4. Click on Company field
5. Should see dropdown with: "ABC Manufacturing", "Acme Corporation", "Global Shipping Co", "TechCorp Industries", "XYZ Logistics"
6. Can select from list OR type new values

---

## Benefits

1. **Consistency:** Users see previously used values, promoting standardization
2. **Speed:** Faster data entry by selecting from existing values
3. **Flexibility:** Still allows new values to be entered
4. **Accuracy:** Reduces typos by selecting from known-good values
5. **Auto-Complete:** Type-to-filter makes finding values quick

---

## Files Modified

- `src/ui/file_details_grid.py` - Added editable dropdown support, database queries
- `src/ui/bundle_review_window_v2.py` - Added editable dropdown with mock data

---

## Future Enhancements

1. **Frequency Sorting:** Sort by most commonly used values first
2. **Recent Values:** Show recently used values at top
3. **Fuzzy Matching:** Suggest similar values when typing
4. **Validation:** Warn if entering unusual values
5. **Bulk Edit:** Apply same value to multiple files

---

## Success Criteria

✅ File Details Dialog uses editable dropdowns for Document Type and Company
✅ Dropdowns populated from distinct database values
✅ Bundle Review Window uses editable dropdowns with mock data
✅ Users can select existing or type new values
✅ Consistent styling between both dialogs
✅ Values sorted alphabetically
✅ All existing functionality preserved

**Status:** Complete and ready for testing!
