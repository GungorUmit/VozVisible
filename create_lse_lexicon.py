#!/usr/bin/env python3
"""Compatibility wrapper for lexicon setup.

Uses setup_lse_from_ase.py to create a working custom lexicon.
"""

from setup_lse_from_ase import main

if __name__ == "__main__":
    raise SystemExit(main())
