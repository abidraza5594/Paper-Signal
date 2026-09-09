from app.database import JobDatabase
from app.dynamo import DynamoJobDatabase
from app.models import JobRecord, JobPublic


def make_job(audit=None):
    return JobRecord(id="audit", file_name="test.pdf", file_path="test.pdf", file_size=42,
                     instruction="Extract", extraction_audit=audit)


def test_sqlite_audit_survives_reload_without_public_exposure(tmp_path):
    db = JobDatabase(tmp_path / "jobs.sqlite3")
    db.initialize()
    db.create(make_job())
    audit = {"provenance": [{"fieldPath": "/value", "rawValue": "private evidence"}]}
    db.update("audit", extraction_audit=audit)
    record = db.get("audit")
    assert record.extraction_audit == audit
    assert "extraction_audit" not in JobPublic.from_record(record).model_dump()


def test_dynamo_audit_compression_round_trip():
    class FakeTable:
        def put_item(self, Item):
            self.item = Item
    db = DynamoJobDatabase.__new__(DynamoJobDatabase)
    db.table = FakeTable()
    audit = {"decisions": [{"sourcePage": i, "rawValue": "evidence " * 100} for i in range(1000)]}
    db.create(make_job(audit))
    assert "extraction_audit" not in db.table.item
    assert len(db.table.item["extraction_audit_gzip"]) < 30_000
    assert db._record(db.table.item).extraction_audit == audit


def test_sqlite_preserves_audit_supplied_at_creation(tmp_path):
    db = JobDatabase(tmp_path / "jobs.sqlite3")
    db.initialize()
    audit = {"decisions": [{"accepted": False, "rejectionReason": "schema_constraint"}]}
    db.create(make_job(audit))
    assert db.get("audit").extraction_audit == audit
