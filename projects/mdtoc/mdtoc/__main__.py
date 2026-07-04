"""Entry point for ``python3 -m mdtoc ...`` (T-028).

Running a package with ``python -m`` executes this file as the ``__main__``
module, so ``__name__ == "__main__"`` is always true in that context. The
guard below is kept anyway as a defensive convention (e.g. it also makes
``python3 projects/mdtoc/mdtoc/__main__.py ...`` behave sanely), but it is
not load-bearing for the primary ``python3 -m mdtoc`` invocation.

All argument parsing and command dispatch lives in :mod:`mdtoc.cli`; this
file's only job is to call ``main()`` and translate its integer return value
into a process exit code.
"""
import sys

from mdtoc.cli import main

if __name__ == "__main__":
    sys.exit(main())
