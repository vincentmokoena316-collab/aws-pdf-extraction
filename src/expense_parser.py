import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def normalize_currency(value: str) -> str:
    """Normalize currency strings to decimal format."""
    if not value:
        return ""
    # Remove common currency symbols and text
    cleaned = re.sub(r"[^0-9.,-]", "", value)
    # Remove thousands separators (commas)
    cleaned = cleaned.replace(",", "")
    # Remove leading minus if needed
    cleaned = cleaned.lstrip("-")
    # Ensure valid decimal format
    if cleaned and re.match(r"^\d+(\.\d{1,2})?$", cleaned):
        return cleaned
    return value.strip()


def extract_date(value: str) -> Optional[str]:
    """Extract and normalize date strings."""
    if not value:
        return None
    # Simple date extraction - try common formats
    value = value.strip()
    # Already in YYYY-MM-DD format
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return re.search(r"\d{4}-\d{2}-\d{2}", value).group()
    # MM/DD/YYYY or similar
    if re.search(r"\d{1,2}/\d{1,2}/\d{4}", value):
        return value
    return value


def normalize_field_name(text: str) -> str:
    """Convert field label to normalized key."""
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def extract_summary_fields(expense_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Extract summary-level fields from Textract expense document."""
    fields: Dict[str, Any] = {}
    
    for item in expense_doc.get("SummaryFields", []):
        label_detection = item.get("LabelDetection", {})
        value_detection = item.get("ValueDetection", {})
        
        label = label_detection.get("Text", "").strip()
        value = value_detection.get("Text", "").strip()
        confidence = value_detection.get("Confidence", 0) / 100.0
        
        if not label or not value:
            continue
        
        key = normalize_field_name(label)
        fields[key] = {
            "value": value,
            "confidence": confidence,
            "label": label
        }
    
    return fields


def extract_line_items(expense_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract line items from invoice line item groups."""
    line_items: List[Dict[str, Any]] = []
    
    for group in expense_doc.get("LineItemGroups", []):
        for item in group.get("LineItems", []):
            item_fields: Dict[str, Any] = {}
            
            for field in item.get("LineItemExpenseFields", []):
                label_detection = field.get("LabelDetection", {})
                value_detection = field.get("ValueDetection", {})
                
                label = label_detection.get("Text", "").strip()
                value = value_detection.get("Text", "").strip()
                confidence = value_detection.get("Confidence", 0) / 100.0
                
                if not label or not value:
                    continue
                
                key = normalize_field_name(label)
                item_fields[key] = {
                    "value": value,
                    "confidence": confidence,
                    "label": label
                }
            
            if item_fields:
                line_items.append(item_fields)
    
    return line_items


def extract_invoice_fields(summary: Dict[str, Any], line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract and normalize key invoice fields."""
    def get_value(key: str) -> str:
        if key in summary and isinstance(summary[key], dict):
            return summary[key].get("value", "")
        return summary.get(key, "")
    
    def get_confidence(key: str) -> float:
        if key in summary and isinstance(summary[key], dict):
            return summary[key].get("confidence", 0.0)
        return 0.0
    
    # Common field name variations
    invoice_number = (
        get_value("invoice_number") or
        get_value("invoicenumber") or
        get_value("bill_number") or
        get_value("receipt_number") or
        ""
    )
    
    vendor_name = (
        get_value("vendor_name") or
        get_value("vendor") or
        get_value("merchant_name") or
        get_value("company_name") or
        ""
    )
    
    vendor_address = (
        get_value("vendor_address") or
        get_value("vendor_address_line_1") or
        get_value("merchant_address") or
        ""
    )
    
    invoice_date = extract_date(
        get_value("invoice_date") or
        get_value("date") or
        get_value("document_date") or
        ""
    )
    
    due_date = extract_date(
        get_value("due_date") or
        get_value("payment_due_date") or
        get_value("terms_due_date") or
        ""
    )
    
    currency = (
        get_value("currency") or
        get_value("currency_code") or
        "USD"
    )
    
    subtotal = normalize_currency(
        get_value("subtotal") or
        get_value("subtotal_amount") or
        get_value("amount_subtotal") or
        ""
    )
    
    tax_amount = normalize_currency(
        get_value("tax") or
        get_value("tax_amount") or
        get_value("total_tax") or
        ""
    )
    
    total_amount = normalize_currency(
        get_value("total") or
        get_value("total_amount") or
        get_value("amount_total") or
        ""
    )
    
    payment_method = (
        get_value("payment_method") or
        get_value("payment_terms") or
        get_value("terms") or
        ""
    )
    
    # Calculate average confidence score
    confidence_scores = [
        get_confidence("invoice_number"),
        get_confidence("vendor_name"),
        get_confidence("total_amount"),
        get_confidence("invoice_date"),
    ]
    avg_confidence = sum(c for c in confidence_scores if c > 0) / len([c for c in confidence_scores if c > 0]) if any(confidence_scores) else 0.0
    
    return {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "vendor_address": vendor_address,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "currency": currency,
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "payment_method": payment_method,
        "confidence_score": round(avg_confidence, 4),
    }


def parse_expense_document(
    bucket: str,
    key: str,
    response: Dict[str, Any]
) -> Dict[str, Any]:
    """Parse Textract expense document response into normalized JSON."""
    expense_docs = response.get("ExpenseDocuments", [])
    if not expense_docs:
        raise ValueError("No expense documents found in Textract response")
    
    main_doc = expense_docs[0]
    summary_fields = extract_summary_fields(main_doc)
    line_items = extract_line_items(main_doc)
    extracted_fields = extract_invoice_fields(summary_fields, line_items)
    
    # Normalize line items for output
    normalized_line_items = []
    for item in line_items:
        normalized_item = {}
        for key, val in item.items():
            if isinstance(val, dict):
                normalized_item[key] = val.get("value", "")
            else:
                normalized_item[key] = val
        normalized_line_items.append(normalized_item)
    
    normalized = {
        "source_bucket": bucket,
        "source_key": key,
        "document_id": f"{bucket}:{key}",
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "invoice_number": extracted_fields.get("invoice_number"),
        "vendor_name": extracted_fields.get("vendor_name"),
        "vendor_address": extracted_fields.get("vendor_address"),
        "invoice_date": extracted_fields.get("invoice_date"),
        "due_date": extracted_fields.get("due_date"),
        "currency": extracted_fields.get("currency"),
        "subtotal": extracted_fields.get("subtotal"),
        "tax_amount": extracted_fields.get("tax_amount"),
        "total_amount": extracted_fields.get("total_amount"),
        "payment_method": extracted_fields.get("payment_method"),
        "line_items": normalized_line_items,
        "confidence_score": extracted_fields.get("confidence_score"),
        "summary_fields": summary_fields,
    }
    
    # Remove empty fields
    normalized = {k: v for k, v in normalized.items() if v not in ("", None, [])}
    
    return normalized
