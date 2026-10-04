# Embedded XS source

Shared state and calculations will live here when gameplay generation begins.
The generator must embed scripts through `XsManager.add_script`, validate them
with the parser's bundled `xs-check`, and leave the external script name empty.
Gameplay scripts must be embedded in the scenario without a companion installation.

`uv run python tools/check_xs.py` checks every `.xs` file added to this directory.
This directory currently contains no gameplay scripts.
