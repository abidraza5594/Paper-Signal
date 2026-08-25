"""Delete finished jobs and the PDFs they uploaded.

Nothing removes uploaded files on its own, so disk use only grows. Run this on a
schedule, or by hand when you want the documents gone.

    python cleanup.py --older-than 7          # what would go, nothing deleted
    python cleanup.py --older-than 7 --yes    # actually delete
    python cleanup.py --all --yes             # every finished job
    python cleanup.py --job <job_id> --yes    # one job

Jobs that are still queued or processing are never touched.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import get_settings
from app.database import JobDatabase
from app.models import JobStatus
from app.storage import LocalStorage


def _age_days(created_at: str) -> float:
    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return 0.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete finished jobs and their PDFs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--older-than", type=float, metavar="DAYS", help="finished jobs older than DAYS")
    group.add_argument("--all", action="store_true", help="every finished job")
    group.add_argument("--job", metavar="JOB_ID", help="one job by id")
    parser.add_argument("--yes", action="store_true", help="actually delete (otherwise dry run)")
    args = parser.parse_args(argv)

    settings = get_settings()
    settings.prepare_directories()
    database = JobDatabase(settings.database_path)
    database.initialize()
    storage = LocalStorage(settings.upload_dir, settings.max_upload_bytes)

    if args.job:
        job = database.get(args.job)
        if job is None:
            print(f"error: no job with id {args.job}", file=sys.stderr)
            return 1
        candidates = [job]
    else:
        candidates = database.list_recent(limit=100)
        cutoff = args.older_than
        if cutoff is not None:
            candidates = [job for job in candidates if _age_days(job.created_at) >= cutoff]

    finished = [job for job in candidates if job.status in (JobStatus.completed, JobStatus.failed)]
    skipped = len(candidates) - len(finished)

    if not finished:
        print("Nothing to delete." + (f" ({skipped} still running)" if skipped else ""))
        return 0

    freed = 0
    for job in finished:
        path = Path(job.file_path)
        size = path.stat().st_size if path.exists() else 0
        freed += size
        mark = "would delete" if not args.yes else "deleted"
        print(f"  {mark}: {job.file_name}  ({size // 1024} KB, {_age_days(job.created_at):.1f} days old)")
        if args.yes:
            storage.delete(job.file_path)
            database.delete(job.id)

    print()
    print(f"{len(finished)} job(s), {freed / (1024 * 1024):.1f} MB" + (" freed." if args.yes else " would be freed."))
    if skipped:
        print(f"{skipped} job(s) still queued or processing were left alone.")
    if not args.yes:
        print("Dry run. Add --yes to actually delete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
