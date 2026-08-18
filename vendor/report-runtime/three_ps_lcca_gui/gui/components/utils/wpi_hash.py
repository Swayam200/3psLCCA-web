"""
utils/wpi_hash.py

Hash utility for WPI data integrity checking.
Used both at build time (stamp_hashes.py) and at runtime (WPIManager).
"""

import hashlib
import json


def compute_hash(data: dict) -> str:
    """
    Compute a deterministic SHA-256 hash of a WPI data block.
    sort_keys=True ensures key ordering never affects the hash.
    """
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=True)
    return "sha256:" + hashlib.sha256(serialized.encode()).hexdigest()


def verify_hash(data: dict, stored_hash: str) -> bool:
    """
    Verify a data block against a stored hash string.
    Returns True if match, False if mismatch or missing.
    """
    if not stored_hash:
        return False
    return compute_hash(data) == stored_hash


