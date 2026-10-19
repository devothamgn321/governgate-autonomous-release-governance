"""GovernGate: cross-service change impact checks for shared libraries on GitLab.

Pipeline of one run:

    change analysis -> consumer discovery -> differential verification
        -> root cause (Nemotron) -> policy verdict -> evidence ledger -> MR report

Principle: AI explains and proposes; only real test results decide.
"""

__version__ = "0.1.0"
