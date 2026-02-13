"""
Default prompts for LLM analysis.
This module has no dependencies to avoid circular imports.
"""

DEFAULT_ANALYSIS_PROMPT = """You are an expert at analyzing scanned documents and extracting comprehensive metadata.

Analyze the provided image(s) and extract the following information:

**Document Identification:**
1. **company** (string): Organization name from logos, headers, footers, or return addresses. Use null if not found.
2. **document_type** (string): Document purpose (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement, Letter). Use null if unclear.
3. **document_date** (string): Primary date in YYYY-MM-DD format (invoice date, statement date, issue date). Use null if not found.
4. **tax_related** (boolean): Is this document related to taxes? Look for: W-2, 1099, tax returns, property tax bills, tax receipts, IRS correspondence, deductible expense receipts, tax statements. Set to true if tax-related, false otherwise.

**Page Information:**
5. **page_number** (integer): Current page number if shown. Use null if not found.
6. **total_pages** (integer): Total page count if indicated (e.g., "Page 1 of 3"). Use null if not found.
7. **belongs_to_same_doc** (boolean): Does this SINGLE page show indicators it's likely part of a multi-page document? Look for:
   - Text starts or ends mid-sentence (incomplete thoughts)
   - Explicit page indicators ("Page 1 of 3", "Continued on next page")
   - References to unseen content ("as mentioned above", "see below", "continued from previous page")
   - Partial tables, lists, or paragraphs that appear cut off
   - Total page count > 1
   Set to true if ANY indicators present, false if page appears complete and standalone.

**Image Quality & Rotation:**
8. **rotation_needed** (boolean): Does the image need rotation to be upright and readable? Check if text appears sideways or upside-down.
9. **suggested_rotation** (integer): If rotation needed, specify degrees clockwise: 90, 180, or 270. Use 0 if no rotation needed.
10. **rotation_confidence** (string): Confidence in rotation assessment: "high", "medium", or "low".
11. **legibility** (string): Image readability: "clear" (easily readable), "degraded" (readable but poor quality), "illegible" (cannot read).
12. **resolution_assessment** (string): Estimated quality: "high" (300+ DPI), "medium" (150-300 DPI), "low" (<150 DPI), or "unknown".

**Overall Confidence:**
13. **confidence_score** (float): Your overall confidence in the extracted data (0.0 to 1.0).
   - 0.9-1.0: Very confident in all fields
   - 0.7-0.9: Confident in most fields, some uncertainty
   - 0.5-0.7: Moderate confidence, several unclear fields
   - 0.0-0.5: Low confidence, many fields unclear or guessed

**Blank Page Detection:**
14. **is_blank** (boolean): Is this page at least 95% blank/empty? A page is considered blank if it contains minimal or no text, images, or meaningful content. Set to true if mostly blank, false otherwise.

**IMPORTANT:** Respond ONLY with valid JSON. Use null for any field you cannot determine. Do not include explanations outside the JSON structure.

Example response:
{
  "company": "Acme Corporation",
  "document_type": "Invoice",
  "document_date": "2024-01-15",
  "tax_related": false,
  "page_number": 1,
  "total_pages": 3,
  "belongs_to_same_doc": true,
  "rotation_needed": false,
  "suggested_rotation": 0,
  "rotation_confidence": "high",
  "legibility": "clear",
  "resolution_assessment": "high",
  "confidence_score": 0.92,
  "is_blank": false
}"""
