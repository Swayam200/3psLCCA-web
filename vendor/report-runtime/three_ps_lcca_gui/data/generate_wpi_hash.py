"""
generate_wpi_hashes.py

Loops through every entry in wpi_db.json, recomputes the SHA-256 hash
from its data block, and writes the updated file back.

Usage:
    python generate_wpi_hashes.py                        # uses wpi_db.json in same dir
    python generate_wpi_hashes.py path/to/wpi_db.json   # explicit path
"""

import hashlib
import json
import sys
from pathlib import Path


def compute_hash(data: dict) -> str:
    data_str = json.dumps(data, sort_keys=True)
    return "sha256:" + hashlib.sha256(data_str.encode()).hexdigest()


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "wpi_db.json"

    if not path.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        db = json.load(f)

    entries = db.get("entries", [])
    if not entries:
        print("No entries found in wpi_db.json")
        sys.exit(1)

    print(f"Processing {len(entries)} entries from: {path}\n")

    for entry in entries:
        name = entry["metadata"]["name"]
        old_hash = entry["metadata"].get("hash", "-")
        new_hash = compute_hash(entry["data"])
        entry["metadata"]["hash"] = new_hash

        status = "✅ unchanged" if old_hash == new_hash else "🔄 updated"
        print(f"  {name}: {new_hash}  {status}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4)

    print(f"\nDone. Hashes written to: {path}")


if __name__ == "__main__":
    main()


