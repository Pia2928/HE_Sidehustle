# randomisation.py
"""
Balanced random assignment to the four conditions of the 2 x 2 design.

Method: permuted-block randomisation with randomly varying block sizes
(4 or 8). Every block contains each condition equally often, so the groups
stay balanced throughout recruitment, and the varying block size means the
next assignment cannot be predicted.

The full allocation sequence is generated once from a fixed seed and stored
in the database. Participants take the next free slot in order. A participant
who returns (reload, new tab) always gets their original slot back.

Report in the preregistration: "Participants were assigned to conditions by
permuted-block randomisation (block sizes 4 and 8, random order) using a
pre-generated, seeded allocation sequence."
"""

import random
import time

CONDITIONS = ["generic_noai", "personalized_noai", "generic_ai", "personalized_ai"]
BLOCK_SIZES = (4, 8)


def generate_sequence(seed, n_slots):
    """Return a list of (block_number, condition) of at least n_slots entries."""
    rng = random.Random(seed)
    sequence = []
    block = 0
    while len(sequence) < n_slots:
        block += 1
        size = rng.choice(BLOCK_SIZES)
        items = CONDITIONS * (size // len(CONDITIONS))
        rng.shuffle(items)
        sequence.extend((block, cond) for cond in items)
    return sequence


def ensure_sequence(db, seed, n_slots):
    """Create the allocation table contents once. Never regenerates existing slots."""
    existing = db.execute("SELECT COUNT(*) FROM allocation").fetchone()[0]
    if existing >= n_slots:
        return
    sequence = generate_sequence(seed, n_slots)
    db.executemany(
        "INSERT OR IGNORE INTO allocation (slot, block, condition) VALUES (?, ?, ?)",
        [(i + 1, blk, cond) for i, (blk, cond) in enumerate(sequence)],
    )


def assign(db, pid):
    """
    Atomically assign the next free slot to pid, or return the existing one.
    Returns (condition, slot). Caller must commit.
    """
    if db.in_transaction:
        db.commit()
    # Take the write lock before reading, so two simultaneous participants
    # can never receive the same slot.
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT slot, condition FROM allocation WHERE pid = ?", (pid,)).fetchone()
    if row:
        return row["condition"], row["slot"]
    row = db.execute("SELECT slot, condition FROM allocation WHERE pid IS NULL ORDER BY slot LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("Allocation sequence exhausted; increase ALLOCATION_SLOTS.")
    db.execute("UPDATE allocation SET pid = ?, assigned_at = ? WHERE slot = ?", (pid, time.time(), row["slot"]))
    return row["condition"], row["slot"]
