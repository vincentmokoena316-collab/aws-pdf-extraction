import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

from expense_parser import parse_expense_document

textract = boto3.client("textract")
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")
EXTRACTION_TABLE = os.environ.get("EXTRACTION_TABLE")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


def log(message: str, level: str = "INFO") -> None:
    """Simple logging function."""
    if level in ["DEBUG", "INFO", "WARN", "ERROR"]:
        print(f"[{level}] {message}")


def write_output_json(document: Dict[str, Any], bucket: str, key: str) -> str:
    """Write extracted document to S3 as JSON."""
    if not OUTPUT_BUCKET:
        raise ValueError("OUTPUT_BUCKET environment variable is not set")
    
    output_key = key.replace(".pdf", "_invoice_extracted.json")
    s3.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=json.dumps(document, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    log(f"Wrote extracted data to s3://{OUTPUT_BUCKET}/{output_key}")
    return output_key


def store_metadata(document: Dict[str, Any]) -> None:
    """Store extraction metadata in DynamoDB."""
    if not EXTRACTION_TABLE:
        log("EXTRACTION_TABLE not set, skipping metadata storage", "WARN")
        return
    
    table = dynamodb.Table(EXTRACTION_TABLE)
    table.put_item(
        Item={
            "document_id": document.get("document_id", f"{document['source_bucket']}:{document['source_key']}"),
            "extraction_timestamp": int(datetime.now(timezone.utc).timestamp()),
            "source_bucket": document.get("source_bucket"),
            "source_key": document.get("source_key"),
            "invoice_number": document.get("invoice_number", "N/A"),
            "vendor_name": document.get("vendor_name", "N/A"),
            "total_amount": document.get("total_amount", "0"),
            "currency": document.get("currency", "USD"),
            "confidence_score": float(document.get("confidence_score", 0.0)),
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    log(f"Stored metadata for {document.get('document_id')}")


def publish_notification(document: Dict[str, Any], output_key: str, status: str) -> None:
    """Publish extraction completion notification to SNS."""
    if not SNS_TOPIC_ARN:
        log("SNS_TOPIC_ARN not set, skipping notification", "WARN")
        return
    
    message = {
        "status": status,
        "document_id": document.get("document_id"),
        "source_key": document.get("source_key"),
        "output_key": output_key,
        "invoice_number": document.get("invoice_number"),
        "vendor_name": document.get("vendor_name"),
        "total_amount": document.get("total_amount"),
        "extracted_at": document.get("extracted_at"),
        "confidence_score": document.get("confidence_score"),
    }
    
    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject=f"Invoice Extraction Complete: {document.get('invoice_number', 'Unknown')}",
        Message=json.dumps(message, indent=2),
    )
    log(f"Published SNS notification for {document.get('document_id')}")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for invoice/receipt extraction."""
    try:
        log(f"Received event: {json.dumps(event)}", "DEBUG")
        
        # Extract S3 event details
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        
        log(f"Processing PDF from s3://{bucket}/{key}")
        
        # Call Textract ExpenseDocuments API
        response = textract.analyze_expense(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
        )
        
        log("Textract analysis completed")
        
        # Parse and normalize the response
        document = parse_expense_document(bucket, key, response)
        
        log(f"Extracted invoice: {document.get('invoice_number')} from {document.get('vendor_name')}")
        
        # Write normalized output to S3
        output_key = write_output_json(document, bucket, key)
        
        # Store metadata in DynamoDB
        store_metadata(document)
        
        # Publish SNS notification
        publish_notification(document, output_key, "completed")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "document_id": document.get("document_id"),
                "invoice_number": document.get("invoice_number"),
                "output_key": output_key,
                "status": "completed",
                "confidence_score": document.get("confidence_score"),
            }),
        }
    
    except ClientError as exc:
        error_message = str(exc)
        log(f"AWS service error: {error_message}", "ERROR")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message, "type": "ClientError"}),
        }
    
    except ValueError as exc:
        error_message = str(exc)
        log(f"Validation error: {error_message}", "ERROR")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": error_message, "type": "ValueError"}),
        }
    
    except Exception as exc:
        error_message = str(exc)
        log(f"Unexpected error: {error_message}", "ERROR")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message, "type": "UnexpectedError"}),
        }
