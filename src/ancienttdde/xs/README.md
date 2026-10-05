# Embedded XS source

The `probe-heartbeat.xs` rule increments a trigger variable and reports every ten
ticks, providing an observable embedding and save/load experiment. Its scenario
reserves variable zero for the heartbeat. The generator embeds it through
`XsManager.add_script`, validates it with the parser's bundled `xs-check`, and leaves
the external script name empty. No companion XS installation is required.

`probe-raider-purchases.xs` handles scout and galley purchases. Each transaction
checks the current living count and selects exactly three living, ungarrisoned
Kings owned by the buyer inside the payment pad. It creates the raider with
collision checks enabled and removes those Kings only if creation returns a
valid unit ID. A blocked spawn or full cap keeps the payment intact. The generator
embeds the shared function before the purchase effects, whose functions have no
arguments as required by DE trigger script calls.

`uv run python tools/check_xs.py` checks every `.xs` file added to this directory.
The checker rejects errors and disabled validation. If the packaged binary lacks
execute permission on POSIX, a temporary executable copy is used without modifying
the installed dependency.
