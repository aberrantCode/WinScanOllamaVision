"""Tests for MetadataNormalizer service."""

from services.metadata_normalizer import MetadataNormalizer


class TestMetadataNormalizer:
    """Test suite for MetadataNormalizer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.normalizer = MetadataNormalizer()

    def test_normalize_company_basic(self):
        """Test basic company name normalization."""
        assert self.normalizer.normalize_company("acme corp") == "Acme Corp"
        assert self.normalizer.normalize_company("test company") == "Test Company"

    def test_normalize_company_acronyms(self):
        """Test company name with acronyms."""
        assert self.normalizer.normalize_company("ibm") == "IBM"
        assert self.normalizer.normalize_company("nasa research") == "NASA Research"
        assert self.normalizer.normalize_company("acme inc") == "Acme Inc"
        assert self.normalizer.normalize_company("test corp") == "Test Corp"

    def test_normalize_company_hyphenated(self):
        """Test company names with hyphens."""
        assert self.normalizer.normalize_company("smith-jones llc") == "Smith-Jones LLC"

    def test_normalize_company_empty(self):
        """Test company normalization with empty/None values."""
        assert self.normalizer.normalize_company(None) is None
        assert self.normalizer.normalize_company("") is None
        assert self.normalizer.normalize_company("   ") is None

    def test_normalize_document_type(self):
        """Test document type normalization."""
        assert self.normalizer.normalize_document_type("invoice") == "Invoice"
        assert self.normalizer.normalize_document_type("tax document") == "Tax Document"
        assert self.normalizer.normalize_document_type("RECEIPT") == "Receipt"

    def test_normalize_document_type_empty(self):
        """Test document type with empty values."""
        assert self.normalizer.normalize_document_type(None) is None
        assert self.normalizer.normalize_document_type("") is None

    def test_normalize_date_iso_format(self):
        """Test date normalization with ISO formats."""
        assert self.normalizer.normalize_date("2024-01-15") == "2024-01-15T00:00:00Z"
        assert self.normalizer.normalize_date("2024-01-15T10:30:00") == "2024-01-15T10:30:00Z"
        assert self.normalizer.normalize_date("2024-01-15T10:30:00Z") == "2024-01-15T10:30:00Z"

    def test_normalize_date_us_format(self):
        """Test date normalization with US format."""
        assert self.normalizer.normalize_date("01/15/2024") == "2024-01-15T00:00:00Z"

    def test_normalize_date_european_format(self):
        """Test date normalization with European format."""
        result = self.normalizer.normalize_date("15/01/2024")
        # Could match either US or European interpretation
        assert result is not None

    def test_normalize_date_named_months(self):
        """Test date normalization with named months."""
        assert self.normalizer.normalize_date("January 15, 2024") == "2024-01-15T00:00:00Z"
        assert self.normalizer.normalize_date("15 January 2024") == "2024-01-15T00:00:00Z"

    def test_normalize_date_invalid(self):
        """Test date normalization with invalid dates."""
        assert self.normalizer.normalize_date(None) is None
        assert self.normalizer.normalize_date("") is None
        assert self.normalizer.normalize_date("invalid") is None

    def test_normalize_rotation_string(self):
        """Test rotation normalization from strings."""
        assert self.normalizer.normalize_rotation("none") == 0
        assert self.normalizer.normalize_rotation("90_cw") == 90
        assert self.normalizer.normalize_rotation("90_ccw") == 270
        assert self.normalizer.normalize_rotation("180") == 180

    def test_normalize_rotation_integer(self):
        """Test rotation normalization from integers."""
        assert self.normalizer.normalize_rotation(0) == 0
        assert self.normalizer.normalize_rotation(90) == 90
        assert self.normalizer.normalize_rotation(180) == 180
        assert self.normalizer.normalize_rotation(270) == 270

    def test_normalize_rotation_invalid(self):
        """Test rotation normalization with invalid values."""
        assert self.normalizer.normalize_rotation(None) == 0
        assert self.normalizer.normalize_rotation("invalid") == 0
        assert self.normalizer.normalize_rotation(45) == 0  # Not a valid rotation
        assert self.normalizer.normalize_rotation(360) == 0

    def test_normalize_boolean_true(self):
        """Test boolean normalization for true values."""
        assert self.normalizer.normalize_boolean(True) is True
        assert self.normalizer.normalize_boolean("true") is True
        assert self.normalizer.normalize_boolean("TRUE") is True
        assert self.normalizer.normalize_boolean("yes") is True
        assert self.normalizer.normalize_boolean("1") is True

    def test_normalize_boolean_false(self):
        """Test boolean normalization for false values."""
        assert self.normalizer.normalize_boolean(False) is False
        assert self.normalizer.normalize_boolean("false") is False
        assert self.normalizer.normalize_boolean("no") is False
        assert self.normalizer.normalize_boolean("0") is False
        assert self.normalizer.normalize_boolean(None) is False

    def test_normalize_page_number_valid(self):
        """Test page number normalization with valid values."""
        assert self.normalizer.normalize_page_number(1) == 1
        assert self.normalizer.normalize_page_number("5") == 5
        assert self.normalizer.normalize_page_number(100) == 100

    def test_normalize_page_number_invalid(self):
        """Test page number normalization with invalid values."""
        assert self.normalizer.normalize_page_number(None) is None
        assert self.normalizer.normalize_page_number(0) is None  # Must be positive
        assert self.normalizer.normalize_page_number(-1) is None
        assert self.normalizer.normalize_page_number("invalid") is None

    def test_normalize_confidence_valid(self):
        """Test confidence score normalization with valid values."""
        assert self.normalizer.normalize_confidence(0.5) == 0.5
        assert self.normalizer.normalize_confidence(0.0) == 0.0
        assert self.normalizer.normalize_confidence(1.0) == 1.0
        assert self.normalizer.normalize_confidence("0.75") == 0.75

    def test_normalize_confidence_clamping(self):
        """Test confidence score clamping to 0.0-1.0."""
        assert self.normalizer.normalize_confidence(1.5) == 1.0  # Clamp to max
        assert self.normalizer.normalize_confidence(-0.5) == 0.0  # Clamp to min

    def test_normalize_confidence_invalid(self):
        """Test confidence score with invalid values."""
        assert self.normalizer.normalize_confidence(None) is None
        assert self.normalizer.normalize_confidence("invalid") is None

    def test_normalize_full_metadata(self):
        """Test full metadata normalization."""
        raw_metadata = {
            "company": "acme corp",
            "document_type": "invoice",
            "document_date": "2024-01-15",
            "rotation_needed": "90_cw",
            "page_number": 1,
            "total_pages": 3,
            "belongs_to_same_doc": "true",
            "confidence_score": 0.95,
            "tax_related": "yes",
        }

        normalized = self.normalizer.normalize(raw_metadata)

        assert normalized["company"] == "Acme Corp"
        assert normalized["document_type"] == "Invoice"
        assert normalized["document_date"] == "2024-01-15T00:00:00Z"
        assert normalized["rotation"] == 90
        assert normalized["page_number"] == 1
        assert normalized["total_pages"] == 3
        assert normalized["belongs_to_same_doc"] is True
        assert normalized["confidence_score"] == 0.95
        assert normalized["tax_related"] is True

    def test_normalize_partial_metadata(self):
        """Test normalization with missing fields."""
        raw_metadata = {
            "company": "test inc",
            "document_type": "receipt",
        }

        normalized = self.normalizer.normalize(raw_metadata)

        assert normalized["company"] == "Test Inc"
        assert normalized["document_type"] == "Receipt"
        assert normalized["document_date"] is None
        assert normalized["rotation"] == 0
        assert normalized["page_number"] is None
        assert normalized["total_pages"] is None
        assert normalized["belongs_to_same_doc"] is False
        assert normalized["confidence_score"] is None
        assert normalized["tax_related"] is False

    def test_normalize_raises_type_error_for_non_dict(self):
        """Test that normalize raises TypeError for non-dict input."""
        import pytest

        with pytest.raises(TypeError) as exc_info:
            self.normalizer.normalize("not a dict")  # type: ignore

        assert "must be dict" in str(exc_info.value)

    def test_normalize_document_type_empty_after_strip(self):
        """Test document type with string that becomes empty after strip."""
        assert self.normalizer.normalize_document_type("   ") is None

    def test_normalize_date_empty_after_strip(self):
        """Test date with string that becomes empty after strip."""
        assert self.normalizer.normalize_date("   ") is None

    def test_normalize_rotation_string_integer(self):
        """Test rotation normalization from string representation of integer."""
        # This tests the try/except block that parses string as int (line 207)
        assert self.normalizer.normalize_rotation("90") == 90
        assert self.normalizer.normalize_rotation("180") == 180
        assert self.normalizer.normalize_rotation("270") == 270
        assert self.normalizer.normalize_rotation("135") == 0  # Invalid rotation
