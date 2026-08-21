"""Issue, list, and revoke API keys without going through HTTP.

    python manage_keys.py create "Acme Corp" --rate-limit 120 --quota 5000
    python manage_keys.py list
    python manage_keys.py revoke <key_id>

The raw key is printed once at creation. Only its SHA-256 hash is stored, so it
cannot be recovered afterwards; issue a new key instead.
"""

from __future__ import annotations

import argparse
import sys

from app.api_keys import ApiKeyError, ApiKeyStore
from app.config import get_settings


def _store() -> ApiKeyStore:
    settings = get_settings()
    settings.prepare_directories()
    store = ApiKeyStore(settings.api_keys_database_path)
    store.initialize()
    return store


def cmd_create(args: argparse.Namespace) -> int:
    settings = get_settings()
    store = _store()
    try:
        record, raw_key = store.create(
            name=args.name,
            rate_limit_per_minute=args.rate_limit or settings.default_rate_limit_per_minute,
            monthly_document_quota=args.quota or settings.default_monthly_document_quota,
        )
    except ApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("API key created. Copy it now, it is not shown again.\n")
    print(f"  key        {raw_key}")
    print(f"  id         {record.id}")
    print(f"  name       {record.name}")
    print(f"  rate limit {record.rate_limit_per_minute} requests/minute")
    print(f"  quota      {record.monthly_document_quota} documents/month")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    store = _store()
    records = store.list_all()
    if not records:
        print("No API keys yet. Create one with: python manage_keys.py create \"Client name\"")
        return 0

    print(f"{'id':34}{'name':24}{'prefix':22}{'used':>8}{'quota':>10}  status")
    for record in records:
        used = store.documents_used(record.id)
        status = "revoked" if record.revoked_at else "active"
        print(
            f"{record.id:34}{record.name[:22]:24}{record.key_prefix:22}"
            f"{used:>8}{record.monthly_document_quota:>10}  {status}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    store = _store()
    if store.get(args.key_id) is None:
        print(f"error: no API key with id {args.key_id}", file=sys.stderr)
        return 1
    if not store.revoke(args.key_id):
        print("error: that key is already revoked", file=sys.stderr)
        return 1
    print(f"Revoked {args.key_id}. Calls using it now return 401.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage PaperSignal API keys.")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="issue a new API key")
    create.add_argument("name", help="client name, for your own records")
    create.add_argument("--rate-limit", type=int, help="requests per minute")
    create.add_argument("--quota", type=int, help="documents per calendar month")
    create.set_defaults(func=cmd_create)

    listing = sub.add_parser("list", help="list keys and their usage")
    listing.set_defaults(func=cmd_list)

    revoke = sub.add_parser("revoke", help="revoke a key by id")
    revoke.add_argument("key_id")
    revoke.set_defaults(func=cmd_revoke)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
