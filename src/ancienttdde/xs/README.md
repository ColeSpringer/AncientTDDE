# Embedded XS source

Shared state and calculations will live here when gameplay generation begins.
The generator must embed scripts through `XsManager.add_script`, validate them
with the parser's bundled `xs-check`, and leave the external script name empty.
No companion XS installation is permitted by the modernization plan.

`uv run python tools/check_xs.py` checks every `.xs` file added to this directory.
Milestone 1 contains no gameplay scripts.
