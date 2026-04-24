import os
import pytest
from openscad_docsgen.filehashes import FileHashes


def test_is_changed_new_file(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    fh = FileHashes(hashfile)
    test_file = tmp_path / "test.scad"
    test_file.write_text("sphere(10);")
    assert fh.is_changed(str(test_file)) is True


def test_is_changed_unchanged_file(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    fh = FileHashes(hashfile)
    test_file = tmp_path / "test.scad"
    test_file.write_text("sphere(10);")
    fh.is_changed(str(test_file))  # first call: new file
    assert fh.is_changed(str(test_file)) is False  # second call: unchanged


def test_is_changed_after_modification(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    fh = FileHashes(hashfile)
    test_file = tmp_path / "test.scad"
    test_file.write_text("sphere(10);")
    fh.is_changed(str(test_file))
    test_file.write_text("cube(10);")
    assert fh.is_changed(str(test_file)) is True


def test_save_and_load_round_trip(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    test_file = tmp_path / "test.scad"
    test_file.write_text("sphere(10);")

    fh = FileHashes(hashfile)
    fh.is_changed(str(test_file))
    fh.save()

    fh2 = FileHashes(hashfile)
    assert fh2.is_changed(str(test_file)) is False


def test_load_nonexistent_hashfile(tmp_path):
    hashfile = str(tmp_path / "nonexistent.txt")
    fh = FileHashes(hashfile)
    assert fh.file_hashes == {}


def test_save_creates_file(tmp_path):
    hashfile = str(tmp_path / "subdir" / "hashes.txt")
    test_file = tmp_path / "test.scad"
    test_file.write_text("data")
    fh = FileHashes(hashfile)
    fh.is_changed(str(test_file))
    fh.save()
    assert os.path.isfile(hashfile)


def test_invalidate_forces_redetection(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    fh = FileHashes(hashfile)
    test_file = tmp_path / "test.scad"
    test_file.write_text("sphere(10);")
    fh.is_changed(str(test_file))  # registers hash
    fh.invalidate(str(test_file))  # removes hash
    assert fh.is_changed(str(test_file)) is True  # treated as new again


def test_multiple_files(tmp_path):
    hashfile = str(tmp_path / "hashes.txt")
    fh = FileHashes(hashfile)
    f1 = tmp_path / "a.scad"
    f2 = tmp_path / "b.scad"
    f1.write_text("content a")
    f2.write_text("content b")
    assert fh.is_changed(str(f1)) is True
    assert fh.is_changed(str(f2)) is True
    assert fh.is_changed(str(f1)) is False
    assert fh.is_changed(str(f2)) is False
