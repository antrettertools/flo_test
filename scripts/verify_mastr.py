"""Smoke-test: confirm open-mastr can install and pull data from MaStR.

Run locally (not from the Claude sandbox -- marktstammdatenregister.de is
blocked by this session's network egress policy):

    python3 -m venv .venv && source .venv/bin/activate
    pip install open-mastr
    python scripts/verify_mastr.py

We deliberately avoid triggering the full Gesamtdatenexport (multi-GB) on
the first run and instead try a technology-scoped pull (storage units only).
open-mastr's own docs site wasn't reachable while writing this script, so
the `data=["storage"]` argument below is a best-effort guess based on prior
versions of the package -- if it raises a TypeError, run `help(db.download)`
in a REPL and adjust the call accordingly, then report back what worked.
"""
import sys


def main() -> None:
    try:
        import open_mastr
        from open_mastr import Mastr
    except ImportError as e:
        print(f"FAIL: could not import open_mastr ({e}).")
        print("-> Run: pip install open-mastr")
        sys.exit(1)

    print(f"OK: open-mastr imported, version={getattr(open_mastr, '__version__', 'unknown')}")

    db = Mastr()
    print("OK: Mastr() initialized (local database created)")

    print("Attempting a small, technology-scoped bulk download (storage units only)...")
    try:
        db.download(method="bulk", data=["storage"])
        print("OK: bulk download for 'storage' completed")
    except TypeError as e:
        print(f"PARAM MISMATCH: {e}")
        print("-> Run `help(db.download)` and retry with the correct argument name/values.")
        sys.exit(2)
    except Exception as e:
        print(f"FAIL during download: {e}")
        sys.exit(3)

    print("\nAll checks passed. Report the output above back so we can lock in the ingestion design.")


if __name__ == "__main__":
    main()
