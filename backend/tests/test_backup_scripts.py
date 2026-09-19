"""B-25 — the backup scripts, and specifically the one that deletes.

`backup.sh` and `restore-drill.sh` need a live Postgres, so what runs here is a
syntax check on all three (a backup script with a typo in it fails at 03:00 on
the night nobody is watching) plus real coverage of `backup-prune.sh`, which is
the only one that removes files and therefore the only one where a bug destroys
something instead of merely failing.

The prune tests use actual directories. Retention logic tested against a mock
filesystem is retention logic that has never deleted anything.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
PRUNE = SCRIPTS / "backup-prune.sh"


def stamp(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).strftime("%Y%m%dT%H%M%SZ")


def make_backups(root: Path, *days_ago: int) -> list[str]:
    names = []
    for days in days_ago:
        name = stamp(days)
        (root / name).mkdir(parents=True)
        (root / name / "db.dump").write_bytes(b"x")
        names.append(name)
    return names


def prune(root: Path, days: int) -> subprocess.CompletedProcess:
    return subprocess.run(["sh", str(PRUNE), str(root), str(days)], capture_output=True, text=True)


def remaining(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()}


@pytest.mark.parametrize("script", ["backup.sh", "backup-prune.sh", "restore-drill.sh"])
def test_the_script_parses(script: str):
    result = subprocess.run(["sh", "-n", str(SCRIPTS / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_it_keeps_what_is_inside_the_window(tmp_path: Path):
    kept = make_backups(tmp_path, 1, 3, 10)
    prune(tmp_path, 30)
    assert remaining(tmp_path) == set(kept)


def test_it_removes_what_is_past_the_window(tmp_path: Path):
    # The expected name comes from `make_backups`, never from a second `stamp()`
    # call: `stamp()` reads the clock, so recomputing it after the subprocess has
    # run gives a different second whenever the test straddles a tick. That is a
    # flake that only shows up on a loaded machine — which is to say, in CI.
    juengste, _alt, _aelter = make_backups(tmp_path, 1, 40, 90)
    prune(tmp_path, 30)
    assert remaining(tmp_path) == {juengste}


def test_the_newest_backup_is_never_removed(tmp_path: Path):
    # Retention 0 means "keep one", not "keep none" — an empty backup directory
    # is the state this whole feature exists to prevent.
    (einzige,) = make_backups(tmp_path, 400)
    prune(tmp_path, 0)
    assert remaining(tmp_path) == {einzige}


def test_it_leaves_everything_that_is_not_a_backup(tmp_path: Path):
    make_backups(tmp_path, 90)
    (tmp_path / "README.md").write_text("do not delete me")
    (tmp_path / "wichtig").mkdir()
    (tmp_path / "20260101-notastamp").mkdir()
    prune(tmp_path, 1)
    assert {"README.md", "wichtig", "20260101-notastamp"} <= remaining(tmp_path)


def test_an_empty_directory_is_not_an_error(tmp_path: Path):
    assert prune(tmp_path, 30).returncode == 0


def test_a_missing_directory_is_not_an_error(tmp_path: Path):
    assert prune(tmp_path / "nope", 30).returncode == 0


def test_it_removes_the_whole_backup_not_just_its_dump(tmp_path: Path):
    old = make_backups(tmp_path, 90)[0]
    (tmp_path / old / "files.tar.gz").write_bytes(b"y")
    make_backups(tmp_path, 1)
    prune(tmp_path, 30)
    assert not (tmp_path / old).exists()


def test_backup_names_sort_the_way_time_runs(tmp_path: Path):
    # The whole script compares timestamps as strings; that only works because
    # the format is fixed-width UTC. A local-time or a %-d format would not sort.
    fuenf, zwei, _fuenfzig = make_backups(tmp_path, 5, 2, 50)
    prune(tmp_path, 30)
    assert remaining(tmp_path) == {fuenf, zwei}
