#!/usr/bin/env python3
"""Export extracted invoice metadata to CSV."""

import argparse
import csv
from datetime import datetime

import boto3


def export_table_to_csv(table_name: str, output_file: str) -> None:
    """Scan DynamoDB table and export to CSV."""
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(table_name)
    
    print(f"Scanning table {table_name}...")
    
    response = table.scan()
    items = response.get("Items", [])
    
    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    
    if not items:
        print("No items found in table.")
        return
    
    # Define CSV columns
    fieldnames = [
        "document_id",
        "source_key",
        "invoice_number",
        "vendor_name",
        "total_amount",
        "currency",
        "confidence_score",
        "status",
        "created_at",
    ]
    
    print(f"Writing {len(items)} items to {output_file}...")
    
    with open(output_file, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in items:
            row = {key: item.get(key, "") for key in fieldnames}
            writer.writerow(row)
    
    print(f"Exported to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DynamoDB table to CSV")
    parser.add_argument("--table", required=True, help="DynamoDB table name")
    parser.add_argument("--output", default="invoices.csv", help="Output CSV file")
    
    args = parser.parse_args()
    export_table_to_csv(args.table, args.output)
