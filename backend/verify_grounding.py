"""Opt-in live regression harness. Never runs paid provider calls from pytest."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.config import Settings
from app.extraction.llm import response_schema
from app.mistral_service import MistralDocumentService
from app.gemini_service import GeminiDocumentService
from app.pdf_service import PdfTextService
from app.schema_service import parse_json_schema_contract, validator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["mistral", "gemini"])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--schema", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-cache", type=Path, help="Reuse exact candidate responses from an earlier evaluation.")
    parser.add_argument("--verification-model", help="Override only the independent verifier for a controlled evaluation.")
    parser.add_argument("--text-model", help="Override local candidate generation for a controlled evaluation.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    if args.provider:
        settings.ai_provider = args.provider
    if args.text_model:
        if settings.ai_provider == "gemini":
            settings.gemini_text_model = args.text_model
        else:
            settings.mistral_text_model = args.text_model
    if args.verification_model:
        if settings.ai_provider == "gemini":
            settings.gemini_verification_model = args.verification_model
        else:
            settings.mistral_verification_model = args.verification_model
    # The live harness deliberately paces calls to fit small provider quotas.
    settings.ai_retry_base_seconds = 20
    pdf = PdfTextService(settings.ocr_min_text_chars)
    document = pdf.extract(args.pdf)
    ai = GeminiDocumentService(settings) if settings.ai_provider == "gemini" else MistralDocumentService(settings)
    cache = args.output / "provider-cache"
    cache.mkdir(exist_ok=True)
    original_call = ai.extraction_json
    calls = {"cached": 0, "live": 0}
    last_call = [0.0]
    def cached_call(prompt, images=None):
        request = json.loads(prompt)
        verification = "questions" in request or "complete_document_text" in request or request.get("task") == "schema_identity_plan"
        model = settings.verification_model if verification else settings.text_model
        key = hashlib.sha256(json.dumps([model, prompt, images], ensure_ascii=False).encode()).hexdigest()
        path = cache / (key + ".json")
        read_path = path
        if not path.exists() and args.candidate_cache and not verification:
            previous = args.candidate_cache / path.name
            if previous.exists():
                read_path = previous
        if read_path.exists():
            cached = json.loads(read_path.read_text(encoding="utf-8"))
            if validator(response_schema(prompt)).is_valid(cached):
                calls["cached"] += 1
                return cached
        time.sleep(max(0, 8 - (time.monotonic() - last_call[0])))
        last_call[0] = time.monotonic()
        print(f"MODEL {model} chars={len(prompt)} images={len(images or [])}", flush=True)
        try:
            value = original_call(prompt, images)
        except Exception as exc:
            print(f"MODEL FAILED {type(exc).__name__} {getattr(exc, 'failure_code', '')}", flush=True)
            raise
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        calls["live"] += 1
        return value
    ai.extraction_json = cached_call
    for page in document.ocr_candidates:
        image = pdf.render_page_data_url(args.pdf, page, dpi=settings.vision_render_dpi)
        text = ai.vision_page_text(image, page)
        if len(text) < settings.vision_min_text_chars:
            document = pdf.apply_ocr(document, ai.ocr_pages(args.pdf, [page]))
        else:
            document = pdf.apply_page_text(document, {page: text})
    for index, path in enumerate(args.schema):
        started = time.monotonic()
        schema = parse_json_schema_contract(path.read_text(encoding="utf-8-sig"))
        label = str(schema.schema.get("title", f"schema-{index + 1}")) if isinstance(schema.schema, dict) else f"schema-{index + 1}"
        print(f"START {label} pages={document.page_count}", flush=True)
        outcome = ai.extract_document(document, schema, debug=True,
            image_reader=lambda p: pdf.render_page_data_url(args.pdf, p, dpi=settings.vision_render_dpi),
            crop_reader=lambda p, box: pdf.render_page_data_url(args.pdf, p, dpi=settings.vision_render_dpi, bbox=box),
            progress=lambda percent, stage: print(f"{label} {percent}% {stage}", flush=True))
        output = {"schema": schema.schema, "data": outcome.data, "schema_valid": outcome.schema_valid,
                  "validation_paths": outcome.validation_paths, "provenance": outcome.provenance,
                  "debug": outcome.debug, "warnings": outcome.warnings,
                  "duration_seconds": round(time.monotonic() - started, 2), "provider_calls": dict(calls),
                  "provider": settings.ai_provider, "model": settings.text_model, "verification_model": settings.verification_model}
        (args.output / f"result-{index + 1}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.output / f"data-{index + 1}.json").write_text(json.dumps(outcome.data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"DONE {label}: schema_valid={outcome.schema_valid} accepted={len(outcome.provenance)} elapsed={output['duration_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
