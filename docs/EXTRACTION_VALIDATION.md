# Extraction validation — 9 September 2026

This report separates source grounding, schema validity, semantic correctness and recall. A valid JSON object containing mostly nulls is not counted as a high-recall extraction.

## Completed automated checks

- Backend: **147 tests passed**. Coverage includes real generated PDF geometry, adjacent tables, wrong columns/parents, strict schema validation, normalization, visual verification requirements, provider routing/failover, image upload, audit persistence, schema-derived identities, and repeated-source disagreements even when a model rejects a correct row.
- Frontend: 36 tests passed; production build passed.
- Python compilation and Git whitespace checks passed. The backend run reports five upstream SWIG deprecation warnings.
- No live provider calls run inside pytest.

## Independently scored live fixture

The generated supply record has adjacent ordered-item and returned-item tables, repeated item descriptions, unrelated quotation prices and an absent delivery date. Its schema uses arbitrary property names (`a`, `b`, `c`, `d`, `x`, `y`, `z`) with descriptive instructions. Expected answers are created independently of model output.

| Input / model for extraction and verification | Correct facts | Wrong facts | Missing facts | Absent date | Exact JSON match |
|---|---:|---:|---:|---|---|
| Native PDF / `mistral-small-2603` | 8 | 0 | 0 | null | Yes |
| Native PDF / `mistral-large-2512` | 8 | 0 | 0 | null | Yes |
| Rasterized scan, real visual transcription / `mistral-small-2603` | 8 | 0 | 0 | null | Yes |

These three small tests demonstrate specific behaviors, not universal accuracy. Raw results and source files are under `backend/live-results/comparison/` and `backend/live-results/scan-comparison/` locally.

## Real supplied document and model diagnosis

Source: the supplied **The Prestige City – Aston Park.pdf**, 41 file pages. The three supplied schemas are used unchanged.

The small model initially proposed `The Prestige City` as a micro-market and independently accepted its own interpretation because the phrase appeared in the source. An exact-quote check could not detect this semantic error. With the same candidate, schema and page evidence, `mistral-large-2512` rejected it: the text identifies a larger development, not the requested sub-market/corridor.

The production pipeline now has a separately configurable verifier, defaulting to `mistral-large-2512`, while candidate extraction retains `mistral-small-2603`. This is an evidence-based mitigation for an observed model error; stronger verification can still make mistakes.

Basics re-verification completed with schema-valid output and zero mechanical grounding failures. Two distinct fields were populated: the legal entity and SQFT area unit. The wrong micro-market was withheld. Project-name variants remained in conflict and were withheld. This output has limited recall and is not presented as a complete extraction of the brochure.

Repeating Basics with the large model for candidate generation also finished with only the legal entity and SQFT populated after all gates. Before the parent-association check, that model had proposed the corporate office's state, country and postal code as the project address. The final parent check rejected that transfer and the nearby-map landmark interpretation. This sample does not justify upgrading the default candidate model merely to fill more fields; larger models can also make semantic errors.

| Supplied schema | Schema valid | Distinct populated scalar fields | Source citations | Mechanical grounding failures |
|---|---|---:|---:|---:|
| Basics | Yes | 2 | 2 | 0 |
| Amenities and Facilities | Yes | 10 | 11 | 0 |
| Inventory | Yes | 55 | 243 | 0 |

Inventory contains **13 distinct printed type codes**, with no anonymous or duplicate type objects. All **33 returned area measurements** were compared to an independently transcribed reference from the rendered master table on file page 17: **zero mismatches**. This is a selected-field check, not an overall accuracy or recall score.

The source itself contains contradictions:

- C1 is printed as 2 BED Regular in the master table but 3 BED Premier in the file-page-22 table.
- E2 is 3 BED / 1599 in one table and 2 BED / 1352 in another. The final type object retains its identifier and withholds the disputed fields.
- E2d has 2 BED in the master table and 3 BED in the file-page-19 table. Its configuration/count remain unresolved.
- D1's master-table balcony measurement is printed `113,13`. No decimal convention is declared in the supplied schema, so the system does not silently turn it into `113.13`.

The repeated-source gate addresses a second model failure: some correct identity candidates were rejected with explanations alleging nonexistent row mismatches. A pipeline that compares only accepted candidates can therefore miss printed contradictions. The new deterministic check compares matching source columns in tables with a verified identity-column mapping and records possible disagreements, without accepting rejected facts.

Full results, individual rejection explanations, source coordinates and model names are saved in `backend/live-results/verified/`. Data-only artifacts are `data-1.json`, `data-2.json`, and `data-3.json`; `manual-source-audit.json` records the selected-field comparison. The native-source audit checks every returned non-null scalar against the fresh PDF parse, its exact cell when applicable, schema constraints and the bound verifier result. It explicitly does not certify semantic correctness.

The final replay used **140 cached provider responses and zero new provider calls**, applying the final deterministic checks to actual model responses from the live runs. Its short recorded durations are replay timings, not fresh end-to-end service latency. Earlier live runs included substantial quota backoff. The synthetic native and scanned comparisons were separate live provider runs.

## What is fixed, and what remains incomplete

The observed problems came from **code, model interpretation, and inconsistent source content**. Code fixes preserve schema rules, table/cell identity, exact evidence, entity keys, normalization, parent associations and conflicting observations. The stronger independent verifier helps with semantic field mapping. Source contradictions require abstention unless the schema supplies a defensible precedence rule.

Recall is still limited on the supplied brochure. Basics leaves the project name unresolved. Amenities omits visibly present facilities, and Inventory leaves tower/floor hierarchies and many configuration/count fields empty. Missing candidate proposals, inconsistent interpretation of labels, conservative transformations and incomplete cross-page parent resolution all contribute. Requiring every requested field to be filled would hide these failures by guessing; these outputs must not be described as complete extractions.

## Remaining accuracy boundaries

- Mixed subject names and unresolved conflicting statements may yield null rather than selecting a plausible answer.
- Complex cross-page parent identities, unlabeled diagram associations and arbitrary natural-language calculations remain difficult. Missing values do not prove absence.
- Strict raw-evidence and normalization checks reduce recall when candidates quote or transform the source incorrectly.
- Model calls are subject to provider quotas; live timing includes substantial rate-limit backoff.
- No finite set of tests establishes correct extraction for every possible document and JSON Schema.

See [architecture and implementation](EXTRACTION_PIPELINE.md) for the replaced failure mechanisms, exact schema behavior and configuration.
