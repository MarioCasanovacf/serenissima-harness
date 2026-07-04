# Empty package marker for projects/mdtoc/tests/.
#
# This file is required, unavoidably, by Python 3.9's stdlib
# `unittest discover` implementation: when `-s <start_dir>` differs from
# `-t <top_level_dir>`, `unittest.loader.TestLoader.discover` refuses to run
# unless `<start_dir>/__init__.py` exists (raises "Start directory is not
# importable" otherwise -- see cpython bpo-23882, fixed only in 3.11+). Every
# mdtoc task's acceptance criteria mandate the EXACT command
# `python3 -m unittest discover -s projects/mdtoc/tests -t projects/mdtoc`,
# which is a discover call with distinct start/top dirs, so this marker is
# load-bearing infrastructure, not a stray file.
#
# It is intentionally NOT the same thing as `projects/mdtoc/mdtoc/__init__.py`
# (the PACKAGE marker for the `mdtoc` namespace package, owned solely by
# T-028 per the mdtoc plan) -- this file only marks the *tests* directory as
# an importable package for discovery purposes and carries no package logic.
#
# It was not enumerated in any single mdtoc task's context_files (a gap in
# the original T-020 decomposition), so it is shared bootstrap infra created
# by whichever mdtoc worker task first needed a green discover run. Content
# is deliberately empty/inert so any other mdtoc task that also touches this
# file collides on nothing but the trivial marker itself.
