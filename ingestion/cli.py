"""Entry point: python -m ingestion.cli sync|build|all

Must run on a machine with unrestricted egress (sync) and a manually
downloaded VG250 dataset on disk (build) -- see ingestion/README.md.
"""
from __future__ import annotations

import argparse

from ingestion.build_db import build
from ingestion.mastr_sync import sync


def main() -> None:
    parser = argparse.ArgumentParser(description="MaStR/VG250 ingestion pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="Bulk-download MaStR data via open-mastr")

    build_parser = sub.add_parser("build", help="Transform raw data into the processed DB")
    build_parser.add_argument("--vg250-path", required=True, help="Path to VG250 .gpkg or unzipped folder")

    all_parser = sub.add_parser("all", help="Run sync then build")
    all_parser.add_argument("--vg250-path", required=True, help="Path to VG250 .gpkg or unzipped folder")

    args = parser.parse_args()

    if args.command in ("sync", "all"):
        sync()
    if args.command in ("build", "all"):
        build(args.vg250_path)


if __name__ == "__main__":
    main()
