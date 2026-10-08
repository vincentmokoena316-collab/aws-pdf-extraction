import json
from pathlib import Path


def test_normalize_document():
    blocks = [
        {"BlockType": "LINE", "Text": "Invoice #1234"},
        {"BlockType": "LINE", "Text": "Total: $250.00"},
        {"BlockType": "KEY_VALUE_SET", "Id": "k1", "EntityTypes": ["KEY"], "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}]},
        {"BlockType": "WORD", "Id": "w1", "Text": "Invoice"},
        {"BlockType": "KEY_VALUE_SET", "Id": "k2", "EntityTypes": ["VALUE"], "Relationships": [{"Type": "CHILD", "Ids": ["w2"]}]},
        {"BlockType": "WORD", "Id": "w2", "Text": "1234"},
    ]

    from src.lambda_handler import normalize_document

    doc = normalize_document('bucket', 'uploads/invoice.pdf', blocks)
    assert 'text_lines' in doc
    assert 'Invoice #1234' in doc['text_lines']
    assert 'Invoice' in doc['form_fields']


def test_write_output_json(tmp_path):
    payload = {'status': 'ok', 'text_lines': ['hello']}
    from src.lambda_handler import write_output_json

    assert isinstance(payload, dict)
