from app.extraction.source_consistency import withhold_source_disagreements
from app.extraction.types import Candidate, Cell, Decision, EvidenceWindow


SCHEMA = {"type": "object", "properties": {"rows": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "string"}, "n": {
        "type": ["number", "null"], "description": "Number of components."}}}}}}
ID = ["rows", None, "id"]


def row(name, key, raw, table="t", headers=None):
    return EvidenceWindow(name, 1, f"{key} | {raw}", name, table, table_id=table,
        cells=[Cell(0, key), Cell(1, raw)], columns=headers or ["Code", "Components"])


def fact(window, path, value, column, accepted=True):
    return Decision(Candidate(path=path, source_id=window.id, entity_ids=[window.id],
        raw_value=window.cells[column].raw, value=value, quote=window.text, column=column),
        accepted, "accepted" if accepted else "semantic_verification_failed", .8)


def check(windows, decisions):
    withhold_source_disagreements(decisions, {w.id: w for w in windows}, SCHEMA, [ID])


def test_omitted_or_rejected_row_still_exposes_printed_count_conflict():
    a, b = row("a", "X", "3 components"), row("b", "X", "2 components")
    value = fact(a, ["rows", None, "n"], 3, 1)
    rejected = fact(b, ID, "X", 0, False)
    check([a, b], [fact(a, ID, "X", 0), value, rejected])
    assert not value.accepted
    assert value.reason == "unresolved_repeated_source_value"
    assert value.verification["source_consistency_conflicts"] == [{"source_id": "b", "column": 1, "raw_value": "2 components"}]
    assert not rejected.accepted


def test_equivalent_numeric_format_and_other_identifiers_do_not_conflict():
    a, b, c = row("a", "X", "3"), row("b", "X", "3.00"), row("c", "Y", "9")
    value = fact(a, ["rows", None, "n"], 3, 1)
    check([a, b, c], [fact(a, ID, "X", 0), value])
    assert value.accepted


def test_unmapped_table_and_unrelated_column_are_not_compared():
    a = row("a", "X", "3")
    b = row("b", "X", "9", table="unmapped")
    c = row("c", "X", "8", headers=["Code", "Price"])
    value = fact(a, ["rows", None, "n"], 3, 1)
    check([a, b, c], [fact(a, ID, "X", 0), value])
    assert value.accepted


def test_verified_identity_column_in_second_table_enables_cross_page_check():
    a, b, anchor = row("a", "X", "3"), row("b", "X", "2", "t2"), row("z", "Z", "4", "t2")
    value = fact(a, ["rows", None, "n"], 3, 1)
    check([a, b, anchor], [fact(a, ID, "X", 0), fact(anchor, ID, "Z", 0), value])
    assert not value.accepted


def test_merged_title_uses_immediate_textual_subheader_for_disagreement():
    from dataclasses import replace
    a = row("a", "X", "3")
    b = replace(row("b", "X", "2", "t2", ["Record", ""]),
        table_context=[["Record", None], ["Code", "Components"]])
    value = fact(a, ["rows", None, "n"], 3, 1)
    check([a, b], [fact(a, ID, "X", 0), fact(b, ID, "X", 0), value])
    assert not value.accepted
