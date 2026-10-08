# aws-pdf-extraction

Serverless PDF invoice and receipt extraction on AWS using Amazon Textract, S3, Lambda, and DynamoDB.

## Overview

This project implements an optimized pipeline for extracting structured data from invoices and receipts:

- **Vendor information** (name, address)
- **Invoice metadata** (invoice number, date, due date)
- **Financial data** (subtotal, tax, total amount)
- **Line items** (description, quantity, unit price, total)
- **Payment information** (method, terms)

Uses Amazon Textract's **ExpenseDocuments API** for intelligent invoice/receipt parsing.

## Architecture

```
PDF Upload (S3)
    ↓
S3 Event Trigger
    ↓
Lambda Function
    ↓
Amazon Textract (ExpenseDocuments)
    ↓
Extracted JSON (S3)
    ↓
DynamoDB Metadata + SNS Notifications
```

## Features

- ✅ Automatic invoice/receipt field extraction
- ✅ Normalized JSON output
- ✅ DynamoDB metadata tracking
- ✅ SNS completion notifications
- ✅ CloudWatch monitoring and alarms
- ✅ Multi-page PDF support
- ✅ Currency normalization
- ✅ Line item extraction and aggregation
- ✅ Confidence score tracking
- ✅ CSV export capability

## Prerequisites

- AWS CLI v2+
- AWS SAM CLI
- Python 3.11+
- Docker (for SAM builds)
- Valid AWS credentials

## Deployment

### 1. Build the SAM application

```bash
sam build
```

### 2. Deploy to AWS

```bash
sam deploy --guided
```

Answer the deployment prompts:
- Stack name: `pdf-invoice-extraction`
- Region: `us-east-1` (or your region)
- Environment: `dev` or `prod`

### 3. Note the outputs

After successful deployment, note the output values:
- `UploadBucketName` - where to upload PDFs
- `ExtractedDataBucketName` - where extracted JSON is stored
- `ExtractionMetadataTableName` - DynamoDB table for tracking

## Usage

### Upload an invoice PDF

```bash
aws s3 cp invoice.pdf s3://<UploadBucketName>/uploads/
```

### Check the extracted data

```bash
aws s3 ls s3://<ExtractedDataBucketName>/
aws s3 cp s3://<ExtractedDataBucketName>/invoice_invoice_extracted.json .
```

### Query DynamoDB metadata

```bash
aws dynamodb scan --table-name <ExtractionMetadataTableName>
```

## Output Format

Extracted invoice data is returned in JSON format:

```json
{
  "source_bucket": "pdf-upload-123456789-dev",
  "source_key": "uploads/invoice.pdf",
  "document_id": "pdf-upload-123456789-dev:uploads/invoice.pdf",
  "extracted_at": "2026-10-08T18:15:00+00:00",
  "invoice_number": "INV-1042",
  "vendor_name": "Acme Supplies Ltd",
  "vendor_address": "123 Business St, Suite 100",
  "invoice_date": "2026-10-08",
  "due_date": "2026-11-08",
  "currency": "USD",
  "subtotal": "1340.00",
  "tax_amount": "85.00",
  "total_amount": "1425.00",
  "payment_method": "Wire Transfer",
  "payment_terms": "Net 30",
  "line_items": [
    {
      "description": "Laptop Stand",
      "quantity": "1",
      "unit_price": "120.00",
      "total_price": "120.00",
      "confidence": 0.95
    },
    {
      "description": "USB-C Cable",
      "quantity": "2",
      "unit_price": "25.00",
      "total_price": "50.00",
      "confidence": 0.92
    }
  ],
  "summary_fields": {
    "all_extracted_fields": "..."
  },
  "confidence_score": 0.94
}
```

## Local Testing

```bash
pip install -r requirements.txt
pytest -v
```

## Troubleshooting

### Lambda timeout

Increase `Timeout` in `template.yaml` to 600 seconds for large PDFs.

### Low confidence scores

If confidence scores are low, ensure PDFs are:
- High resolution (300+ DPI)
- Properly scanned (not tilted)
- Clear text (not faded)

### Missing fields

Some invoices may not have all fields. Check `summary_fields` for the complete Textract output.

## Performance

- Small invoices (< 1 page): ~2-5 seconds
- Medium invoices (1-5 pages): ~5-15 seconds
- Large invoices (5+ pages): ~15-30 seconds

## Costs

Amazon Textract pricing:
- $0.50 per invoice page (ExpenseDocuments API)
- Free tier: 1,000 pages/month
- S3 storage: standard pricing
- Lambda: free tier covers most workloads
- DynamoDB: on-demand pricing

## CSV Export

To export extracted invoices to CSV:

```bash
python scripts/export_to_csv.py --table <ExtractionMetadataTableName> --output invoices.csv
```

## Advanced

### Async batch processing

For large volumes, use Step Functions with SQS:

```bash
sam deploy --template-file template-async.yaml
```

### Custom field mapping

Edit `src/expense_parser.py` to add custom field extraction rules.

## Support

For issues, file a GitHub issue with:
- PDF sample (redacted)
- Error logs from CloudWatch
- Expected vs actual extraction
