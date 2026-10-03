from typer.testing import CliRunner

from ancienttdde.cli import app

runner = CliRunner()


def test_cli_exposes_development_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("audit", "build", "validate", "probe"):
        assert name in result.output


def test_audit_fails_cleanly_when_inputs_are_missing(tmp_path):
    result = runner.invoke(app, ["audit", "--root", str(tmp_path)])
    assert result.exit_code != 0
    assert "content/audit.toml" in result.output
    assert not (tmp_path / ".build").exists()


def test_unimplemented_generation_commands_report_milestone():
    for command in ("build", "probe"):
        result = runner.invoke(app, [command])
        assert result.exit_code != 0
        assert "milestone" in result.output.lower()
