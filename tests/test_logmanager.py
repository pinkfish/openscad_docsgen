import os
import shutil
import subprocess
import tempfile
import platform
import pytest
from unittest.mock import patch, MagicMock

from openscad_docsgen.logmanager import LogRequest, LogManager
from .conftest import requires_openscad, OPENSCAD_APP


# --- LogRequest: __init__ ---

def test_log_request_passthrough_script():
    req = LogRequest("test.scad", 1, ['echo("hi");'])
    assert req.script_lines == ['echo("hi");']


def test_log_request_strips_double_dash():
    req = LogRequest("test.scad", 1, ['--echo("hi");'])
    assert req.script_lines == ['echo("hi");']


def test_log_request_initial_state():
    req = LogRequest("test.scad", 1, ["sphere(10);"])
    assert req.complete is False
    assert req.success is False
    assert req.status == "INCOMPLETE"
    assert req.echos == []
    assert req.warnings == []
    assert req.errors == []


# --- LogRequest: starting ---

def test_starting_calls_callback():
    called = []
    req = LogRequest("test.scad", 1, [], starting_cb=lambda r: called.append(True))
    req.starting()
    assert called == [True]


def test_starting_no_callback():
    req = LogRequest("test.scad", 1, [])
    req.starting()  # should not raise


# --- LogRequest: completed ---

def test_completed_success():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=[], stderr=[])
    assert req.complete is True
    assert req.success is True
    assert req.status == "SUCCESS"


def test_completed_fail():
    req = LogRequest("test.scad", 1, [])
    req.completed("FAIL", stdout=[], stderr=[])
    assert req.success is False


def test_completed_parses_echo_string():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=['ECHO: "hello world"'], stderr=[])
    assert "hello world" in req.echos


def test_completed_parses_echo_number():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=["ECHO: 42"], stderr=[])
    assert "42" in req.echos


def test_completed_parses_multiple_echos():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=['ECHO: "first"', 'ECHO: "second"'], stderr=[])
    assert "first" in req.echos
    assert "second" in req.echos


def test_completed_parses_warning():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=[], stderr=["WARNING: something deprecated"])
    assert len(req.warnings) == 1
    assert "WARNING:" in req.warnings[0]


def test_completed_parses_error():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=[], stderr=["ERROR: undefined variable"])
    assert len(req.errors) == 1
    assert "ERROR:" in req.errors[0]


def test_completed_stores_return_code():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=[], stderr=[], return_code=0)
    assert req.return_code == 0


def test_completed_calls_callback():
    called = []
    req = LogRequest("test.scad", 1, [], completion_cb=lambda r: called.append(r.status))
    req.completed("SUCCESS", stdout=[], stderr=[])
    assert called == ["SUCCESS"]


def test_completed_no_callback():
    req = LogRequest("test.scad", 1, [])
    req.completed("SUCCESS", stdout=[], stderr=[])  # should not raise


# --- LogManager: basic operations ---

def test_new_request_queues():
    mgr = LogManager()
    req = mgr.new_request("test.scad", 1, ["sphere(10);"])
    assert req in mgr.requests


def test_purge_requests():
    mgr = LogManager()
    mgr.new_request("test.scad", 1, ["sphere(10);"])
    mgr.purge_requests()
    assert mgr.requests == []


def test_process_requests_empty():
    mgr = LogManager()
    mgr.process_requests()  # should not raise with empty list


# --- LogManager: find_openscad_binary ---

@requires_openscad
def test_find_openscad_binary_returns_path():
    mgr = LogManager()
    path = mgr.find_openscad_binary()
    assert path is not None
    assert os.path.isfile(path)


def test_find_openscad_binary_raises_when_missing(monkeypatch):
    """When OpenSCAD cannot be found, an exception is raised."""
    monkeypatch.setenv("PATH", "/nonexistent/path")
    monkeypatch.setattr(shutil, "which", lambda p, **kw: None)
    mgr = LogManager()
    with pytest.raises(Exception, match="Can't find OpenSCAD"):
        mgr.find_openscad_binary()


# --- LogManager: integration with real OpenSCAD ---

@requires_openscad
def test_process_request_echo(tmp_path):
    """OpenSCAD echo() output is captured in req.echos."""
    mgr = LogManager()
    req = mgr.new_request(
        str(tmp_path / "test.scad"), 1,
        ['echo("hello from openscad");']
    )
    mgr.process_request(req)
    assert req.complete is True
    assert req.success is True
    assert any("hello from openscad" in e for e in req.echos)


@requires_openscad
def test_process_request_echo_number(tmp_path):
    mgr = LogManager()
    req = mgr.new_request(
        str(tmp_path / "test.scad"), 1,
        ["echo(1 + 2);"]
    )
    mgr.process_request(req)
    assert req.success is True
    assert any("3" in e for e in req.echos)


@requires_openscad
def test_process_request_multiple_echoes(tmp_path):
    mgr = LogManager()
    req = mgr.new_request(
        str(tmp_path / "test.scad"), 1,
        ['echo("first");', 'echo("second");']
    )
    mgr.process_request(req)
    assert req.success is True
    assert any("first" in e for e in req.echos)
    assert any("second" in e for e in req.echos)


@requires_openscad
def test_process_request_fails_on_invalid_script(tmp_path):
    mgr = LogManager()
    req = mgr.new_request(
        str(tmp_path / "test.scad"), 1,
        ["this is not valid openscad syntax!!!"]
    )
    mgr.process_request(req)
    assert req.complete is True
    assert req.success is False
    assert req.status == "FAIL"


@requires_openscad
def test_process_requests_batch(tmp_path):
    """process_requests() handles multiple queued requests."""
    mgr = LogManager()
    r1 = mgr.new_request(str(tmp_path / "a.scad"), 1, ['echo("one");'])
    r2 = mgr.new_request(str(tmp_path / "b.scad"), 1, ['echo("two");'])
    mgr.process_requests()
    assert r1.complete is True
    assert r2.complete is True
    assert mgr.requests == []


@requires_openscad
def test_process_requests_clears_queue(tmp_path):
    mgr = LogManager()
    mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])
    mgr.process_requests()
    assert mgr.requests == []


# --- LogRequest: verbose mode prints stderr ---

def test_completed_verbose_prints_stderr(capsys):
    req = LogRequest("test.scad", 1, [], verbose=True)
    req.completed("SUCCESS", stdout=[], stderr=["WARNING: something"])
    captured = capsys.readouterr()
    assert "WARNING: something" in captured.out


# --- LogManager: find_openscad_binary edge cases ---

def test_find_openscad_binary_test_only_prints_when_found_in_path(monkeypatch, capsys):
    """When test_only=True and openscad found in PATH, prints a message."""
    monkeypatch.setattr(shutil, "which", lambda p, **kw: "/usr/bin/openscad" if p == "openscad" else None)
    mgr = LogManager()
    mgr.test_only = True
    path = mgr.find_openscad_binary()
    assert path == "/usr/bin/openscad"
    captured = capsys.readouterr()
    assert "Found OpenSCAD in PATH" in captured.out


def test_find_openscad_binary_raises_on_linux_no_binary(monkeypatch):
    """On Linux with no openscad in any expected location, raises Exception."""
    monkeypatch.setattr(shutil, "which", lambda p, **kw: None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    mgr = LogManager()
    with pytest.raises(Exception, match="Can't find OpenSCAD"):
        mgr.find_openscad_binary()


def test_find_openscad_binary_raises_on_windows_no_binary(monkeypatch):
    """On Windows with no openscad found, raises Exception."""
    monkeypatch.setattr(shutil, "which", lambda p, **kw: None)
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    mgr = LogManager()
    with pytest.raises(Exception, match="Can't find OpenSCAD"):
        mgr.find_openscad_binary()


# --- LogManager: process_request error paths ---

def test_process_request_fails_when_binary_not_found(tmp_path):
    """When find_openscad_binary raises, request is marked FAIL."""
    mgr = LogManager()
    req = mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])

    with patch.object(mgr, "find_openscad_binary", side_effect=Exception("Can't find OpenSCAD")):
        mgr.process_request(req)

    assert req.complete is True
    assert req.success is False
    assert req.status == "FAIL"


def test_process_request_fails_on_tempfile_oserror(tmp_path):
    """When NamedTemporaryFile raises OSError, request is marked FAIL."""
    mgr = LogManager()
    req = mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])

    with patch.object(mgr, "find_openscad_binary", return_value="/usr/bin/openscad"):
        with patch("openscad_docsgen.logmanager.tempfile.NamedTemporaryFile",
                   side_effect=OSError("disk full")):
            mgr.process_request(req)

    assert req.complete is True
    assert req.success is False
    assert req.status == "FAIL"


def test_process_request_fails_on_timeout(tmp_path):
    """When subprocess.run raises TimeoutExpired, request is marked FAIL."""
    mgr = LogManager()
    req = mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])

    mock_proc_result = MagicMock()
    mock_proc_result.stdout = ""
    mock_proc_result.stderr = ""
    mock_proc_result.returncode = 0

    with patch.object(mgr, "find_openscad_binary", return_value="/usr/bin/openscad"):
        with patch("openscad_docsgen.logmanager.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="openscad", timeout=10)):
            mgr.process_request(req)

    assert req.complete is True
    assert req.success is False
    assert req.status == "FAIL"


def test_process_request_fails_on_generic_exception(tmp_path):
    """When subprocess.run raises a generic Exception, request is marked FAIL."""
    mgr = LogManager()
    req = mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])

    with patch.object(mgr, "find_openscad_binary", return_value="/usr/bin/openscad"):
        with patch("openscad_docsgen.logmanager.subprocess.run",
                   side_effect=Exception("something went wrong")):
            mgr.process_request(req)

    assert req.complete is True
    assert req.success is False
    assert req.status == "FAIL"


def test_process_requests_test_only_with_request(tmp_path, capsys):
    """process_requests(test_only=True) adds --hardwarnings to the command."""
    mgr = LogManager()
    req = mgr.new_request(str(tmp_path / "test.scad"), 1, ['echo("x");'])

    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock_result.returncode = 0

    with patch.object(mgr, "find_openscad_binary", return_value="/usr/bin/openscad"):
        with patch("openscad_docsgen.logmanager.subprocess.run", return_value=mock_result) as mock_run:
            mgr.process_requests(test_only=True)

    called_cmd = mock_run.call_args[0][0]
    assert "--hardwarnings" in called_cmd


def test_process_requests_test_only_empty_queue(capsys):
    """process_requests(test_only=True) with empty queue prints a message."""
    mgr = LogManager()
    mgr.process_requests(test_only=True)
    captured = capsys.readouterr()
    assert "No log requests" in captured.out
