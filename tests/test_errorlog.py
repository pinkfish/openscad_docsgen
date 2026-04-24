import pytest
from openscad_docsgen.errorlog import ErrorLog


def make_log():
    return ErrorLog()


def test_initial_state():
    log = make_log()
    assert log.errlist == []
    assert log.has_errors is False
    assert log.badfiles == {}


def test_add_note_does_not_set_has_errors(capsys):
    log = make_log()
    log.add_entry("foo.scad", 1, "note message", ErrorLog.NOTE)
    assert log.has_errors is False
    assert len(log.errlist) == 1


def test_add_warn_does_not_set_has_errors(capsys):
    log = make_log()
    log.add_entry("foo.scad", 1, "warn message", ErrorLog.WARN)
    assert log.has_errors is False


def test_add_fail_sets_has_errors(capsys):
    log = make_log()
    log.add_entry("foo.scad", 1, "error message", ErrorLog.FAIL)
    assert log.has_errors is True


def test_file_has_errors_false_before_entry(capsys):
    log = make_log()
    assert log.file_has_errors("foo.scad") is False


def test_file_has_errors_true_after_entry(capsys):
    log = make_log()
    log.add_entry("foo.scad", 1, "msg", ErrorLog.FAIL)
    assert log.file_has_errors("foo.scad") is True


def test_file_has_errors_only_for_affected_file(capsys):
    log = make_log()
    log.add_entry("foo.scad", 1, "msg", ErrorLog.FAIL)
    assert log.file_has_errors("bar.scad") is False


def test_errlist_contents(capsys):
    log = make_log()
    log.add_entry("a.scad", 10, "the message", ErrorLog.WARN)
    file, line, msg, level = log.errlist[0]
    assert file == "a.scad"
    assert line == 10
    assert msg == "the message"
    assert level == ErrorLog.WARN


def test_multiple_entries(capsys):
    log = make_log()
    log.add_entry("a.scad", 1, "first", ErrorLog.NOTE)
    log.add_entry("b.scad", 2, "second", ErrorLog.FAIL)
    assert len(log.errlist) == 2
    assert log.has_errors is True


def test_write_report(tmp_path, capsys):
    log = make_log()
    log.add_entry("a.scad", 5, "test error", ErrorLog.FAIL)

    report_path = tmp_path / "report.json"
    log.REPORT_FILE = str(report_path)
    log.write_report()

    import json
    data = json.loads(report_path.read_text())
    assert len(data) == 1
    assert data[0]["file"] == "a.scad"
    assert data[0]["line"] == 5
    assert data[0]["message"] == "test error"
    assert data[0]["annotation_level"] == ErrorLog.FAIL
