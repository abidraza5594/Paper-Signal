"""Opt-in model comparison on a generated, independently scored document.

Uses arbitrary field names, repeated labels, adjacent tables, an unrelated
reference price, and an absent field. No provider calls are made by pytest.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import fitz

from app.config import Settings
from app.mistral_service import MistralDocumentService
from app.pdf_service import PdfTextService
from app.schema_service import OutputContract


def fixture(path: Path, *, scan=False):
    document = fitz.open()
    page = document.new_page(width=840, height=600)
    page.insert_text((40, 40), "Supply record SR-27", fontsize=18)
    page.insert_text((40, 70), "Buyer: North Laboratory. Seller: Delta Instruments.")
    page.insert_text((40, 95), "Reference quotation only: Zeta Instruments, price 999. Not an ordered item.")
    for left, title, rows in (
        (40, "ORDERED ITEMS", [("A-1", "Sensor", "2", "120"), ("A-2", "Sensor", "3", "80")]),
        (440, "RETURNED ITEMS", [("R-1", "Sensor", "9", "900"), ("R-2", "Cable", "8", "700")]),
    ):
        page.insert_text((left, 145), title, fontsize=13)
        columns = [left, left + 75, left + 180, left + 245, left + 350]
        for x in columns:
            page.draw_line((x, 160), (x, 256))
        for y in (160, 192, 224, 256):
            page.draw_line((left, y), (left + 350, y))
        for r, values in enumerate([("Code", "Description", "Quantity", "Unit price"), *rows]):
            for c, value in enumerate(values):
                page.insert_text((columns[c] + 5, 181 + 32 * r), value, fontsize=10)
    page.insert_text((40, 310), "Ordered total: 480. Returned total: 13700.")
    page.insert_text((40, 340), "Prices are in USD. These are separate transactions; do not combine them.")
    if scan:
        scanned = fitz.open()
        scanned.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect,
            stream=page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png"))
        scanned.save(path)
        scanned.close()
    else:
        document.save(path)
    document.close()
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "a": {"type": ["string", "null"], "description": "Buyer name, excluding the seller and quotation supplier."},
        "b": {"type": ["number", "null"], "description": "Total value of ordered items only, excluding returns and quotations."},
        "c": {"type": ["string", "null"], "description": "Explicitly printed delivery date. Null if absent."},
        "d": {"type": "array", "description": "Ordered items only. Exclude returned items and reference quotations.",
              "items": {"type": "object", "additionalProperties": False, "required": ["x", "y", "z"], "properties": {
                  "x": {"type": ["string", "null"], "description": "Printed item code."},
                  "y": {"type": ["integer", "null"], "description": "Ordered quantity from the Quantity column."},
                  "z": {"type": ["number", "null"], "description": "Price per item from the Unit price column."}}}}},
        "required": ["a", "b", "c", "d"]}
    expected = {"a": "North Laboratory", "b": 480, "c": None,
                "d": [{"x": "A-1", "y": 2, "z": 120}, {"x": "A-2", "y": 3, "z": 80}]}
    return schema, expected


def score(data, expected):
    # Missing facts hurt recall; wrong facts hurt precision, including extra rows.
    def facts(value):
        result = {(key, value.get(key)) for key in ("a", "b", "c") if value.get(key) is not None}
        for row in value.get("d", []):
            for key in ("x", "y", "z"):
                if row.get(key) is not None:
                    result.add(("d", row.get("x"), key, row[key]))
        return result
    actual, truth = facts(data), facts(expected)
    return {"correct": len(actual & truth), "wrong": len(actual - truth), "missing": len(truth - actual),
            "precision": len(actual & truth) / len(actual) if actual else None,
            "recall": len(actual & truth) / len(truth), "exact_match": data == expected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scan", action="store_true", help="Rasterize the fixture to exercise real visual transcription.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / "comparison.pdf"
    schema, expected = fixture(path, scan=args.scan)
    (args.output / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (args.output / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    pdf = PdfTextService()
    document = pdf.extract(path)
    for model in args.model:
        settings = Settings(mistral_text_model=model, mistral_verification_model=model, ai_retry_base_seconds=20)
        ai = MistralDocumentService(settings)
        original = ai.extraction_json
        def paced(prompt, images=None):
            time.sleep(10)
            return original(prompt, images)
        ai.extraction_json = paced
        readable = document
        for page in document.ocr_candidates:
            text = ai.vision_page_text(pdf.render_page_data_url(path, page), page)
            readable = pdf.apply_page_text(readable, {page: text})
        outcome = ai.extract_document(readable, OutputContract(schema, "json_schema"), debug=True,
            image_reader=lambda p: pdf.render_page_data_url(path, p),
            crop_reader=lambda p, box: pdf.render_page_data_url(path, p, bbox=box))
        result = {"model": model, "schema": schema, "data": outcome.data, "expected": expected,
                  "score": score(outcome.data, expected), "schema_valid": outcome.schema_valid,
                  "provenance": outcome.provenance, "debug": outcome.debug, "warnings": outcome.warnings}
        (args.output / f"{model}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps({"model": model, **result["score"], "schema_valid": outcome.schema_valid}), flush=True)


if __name__ == "__main__":
    main()
