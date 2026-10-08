import pytest
from src.expense_parser import (
    normalize_currency,
    extract_date,
    normalize_field_name,
    extract_summary_fields,
    extract_line_items,
    parse_expense_document,
)


class TestNormalizeCurrency:
    def test_simple_amount(self):
        assert normalize_currency("1234.56") == "1234.56"
    
    def test_currency_symbol(self):
        assert normalize_currency("$1234.56") == "1234.56"
    
    def test_comma_separator(self):
        assert normalize_currency("1,234.56") == "1234.56"
    
    def test_currency_text(self):
        assert normalize_currency("USD 1234.56") == "1234.56"
    
    def test_empty_string(self):
        assert normalize_currency("") == ""


class TestExtractDate:
    def test_iso_format(self):
        assert extract_date("2026-10-08") == "2026-10-08"
    
    def test_slash_format(self):
        result = extract_date("10/08/2026")
        assert result is not None
    
    def test_empty_string(self):
        assert extract_date("") is None


class TestNormalizeFieldName:
    def test_simple_name(self):
        assert normalize_field_name("Invoice Number") == "invoice_number"
    
    def test_with_special_chars(self):
        assert normalize_field_name("Invoice-Number") == "invoice_number"
    
    def test_with_spaces(self):
        assert normalize_field_name("  Total Amount  ") == "total_amount"


class TestExtractSummaryFields:
    def test_extract_fields(self):
        expense_doc = {
            "SummaryFields": [
                {
                    "LabelDetection": {"Text": "Invoice Number"},
                    "ValueDetection": {"Text": "INV-1042", "Confidence": 95.0},
                },
                {
                    "LabelDetection": {"Text": "Total Amount"},
                    "ValueDetection": {"Text": "$1425.00", "Confidence": 98.0},
                },
            ]
        }
        
        result = extract_summary_fields(expense_doc)
        assert "invoice_number" in result
        assert result["invoice_number"]["value"] == "INV-1042"
        assert result["invoice_number"]["confidence"] == 0.95


class TestExtractLineItems:
    def test_extract_items(self):
        expense_doc = {
            "LineItemGroups": [
                {
                    "LineItems": [
                        {
                            "LineItemExpenseFields": [
                                {
                                    "LabelDetection": {"Text": "Description"},
                                    "ValueDetection": {"Text": "Laptop Stand", "Confidence": 92.0},
                                },
                                {
                                    "LabelDetection": {"Text": "Quantity"},
                                    "ValueDetection": {"Text": "1", "Confidence": 98.0},
                                },
                            ]
                        }
                    ]
                }
            ]
        }
        
        result = extract_line_items(expense_doc)
        assert len(result) == 1
        assert "description" in result[0]
        assert result[0]["description"]["value"] == "Laptop Stand"


class TestParseExpenseDocument:
    def test_full_document_parse(self):
        response = {
            "ExpenseDocuments": [
                {
                    "SummaryFields": [
                        {
                            "LabelDetection": {"Text": "Invoice Number"},
                            "ValueDetection": {"Text": "INV-1042", "Confidence": 95.0},
                        },
                        {
                            "LabelDetection": {"Text": "Vendor Name"},
                            "ValueDetection": {"Text": "Acme Supplies", "Confidence": 98.0},
                        },
                        {
                            "LabelDetection": {"Text": "Total"},
                            "ValueDetection": {"Text": "$1425.00", "Confidence": 99.0},
                        },
                        {
                            "LabelDetection": {"Text": "Invoice Date"},
                            "ValueDetection": {"Text": "2026-10-08", "Confidence": 97.0},
                        },
                    ],
                    "LineItemGroups": [],
                }
            ]
        }
        
        result = parse_expense_document("bucket", "uploads/invoice.pdf", response)
        
        assert result["source_bucket"] == "bucket"
        assert result["invoice_number"] == "INV-1042"
        assert result["vendor_name"] == "Acme Supplies"
        assert result["total_amount"] == "1425.00"
        assert result["invoice_date"] == "2026-10-08"
        assert "confidence_score" in result
        assert result["confidence_score"] > 0.9
    
    def test_missing_expense_document(self):
        response = {"ExpenseDocuments": []}
        
        with pytest.raises(ValueError):
            parse_expense_document("bucket", "uploads/invoice.pdf", response)
