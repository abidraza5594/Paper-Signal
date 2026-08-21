from app.database import JobDatabase
from app.models import JobRecord, JobStatus


def test_job_lifecycle(tmp_path):
    database = JobDatabase(tmp_path / "jobs.sqlite3")
    database.initialize()
    job = JobRecord(
        id="job-1",
        file_name="document.pdf",
        file_path=str(tmp_path / "document.pdf"),
        file_size=123,
        instruction="Extract the invoice total",
    )

    database.create(job)
    updated = database.update(
        job.id,
        status=JobStatus.completed,
        progress=100,
        stage="Completed",
        result={"data": {"total": 42}},
    )

    assert updated.status == JobStatus.completed
    assert updated.result == {"data": {"total": 42}}
    assert database.delete(job.id) is True
    assert database.get(job.id) is None


def test_database_get_many_preserves_requested_order(tmp_path):
    database = JobDatabase(tmp_path / "jobs.sqlite3")
    database.initialize()
    first = JobRecord(
        id="first",
        file_name="first.pdf",
        file_path=str(tmp_path / "first.pdf"),
        file_size=10,
        instruction="Extract fields",
    )
    second = JobRecord(
        id="second",
        file_name="second.pdf",
        file_path=str(tmp_path / "second.pdf"),
        file_size=20,
        instruction="Extract fields",
    )
    database.create(first)
    database.create(second)

    assert [job.id for job in database.get_many(["second", "missing", "first"])] == [
        "second",
        "first",
    ]
