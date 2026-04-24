import os
import sys
import types
import glob
import yaml
import pytest
from unittest.mock import patch, MagicMock, call

from openscad_docsgen.mdimggen import MarkdownImageGen, mdimggen_main


# --- Helpers ---

def make_opts(tmp_path, **kwargs):
    defaults = dict(
        docs_dir=str(tmp_path / "docs"),
        image_root="images",
        file_prefix="",
        test_only=False,
        force=True,  # default to force so process_requests always runs
        png_animation=False,
        verbose=False,
        colorscheme="Cornfield",
    )
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def write_md(path, content):
    path.write_text(content)
    return path


def make_gen(tmp_path, **kwargs):
    opts = make_opts(tmp_path, **kwargs)
    os.makedirs(opts.docs_dir, exist_ok=True)
    return MarkdownImageGen(opts), opts


def make_mock_req(success=True, status="SKIP", echos=None, warnings=None, errors=None,
                  script_lines=None, src_file="test.md", src_line=1, image_file="/tmp/out.png"):
    req = MagicMock()
    req.success = success
    req.status = status
    req.echos = echos or []
    req.warnings = warnings or []
    req.errors = errors or []
    req.script_lines = script_lines or ["sphere(10);"]
    req.src_file = src_file
    req.src_line = src_line
    req.image_file = image_file
    return req


# --- MarkdownImageGen: img_started ---

def test_img_started_prints_basename(tmp_path, capsys):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(image_file="/some/dir/myimage.png")
    gen.img_started(req)
    captured = capsys.readouterr()
    assert "myimage.png" in captured.out


def test_img_started_no_newline(tmp_path, capsys):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(image_file="/some/dir/myimage.png")
    gen.img_started(req)
    captured = capsys.readouterr()
    assert not captured.out.endswith("\n")


# --- MarkdownImageGen: img_completed ---

def test_img_completed_skip_prints_newline(tmp_path, capsys):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(success=True, status="SKIP")
    gen.img_completed(req)
    captured = capsys.readouterr()
    assert captured.out == "\n"


def test_img_completed_new_prints_status(tmp_path, capsys):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(success=True, status="NEW")
    gen.img_completed(req)
    captured = capsys.readouterr()
    assert "NEW" in captured.out


def test_img_completed_replace_prints_status(tmp_path, capsys):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(success=True, status="REPLACE")
    gen.img_completed(req)
    captured = capsys.readouterr()
    assert "REPLACE" in captured.out


def test_img_completed_failure_adds_to_errorlog(tmp_path):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(
        success=False, status="FAIL",
        errors=["ERROR: undefined var"], warnings=[], echos=[],
        src_file="test.md", src_line=5, image_file="/tmp/bad.png"
    )
    with patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        gen.img_completed(req)
        mock_errorlog.add_entry.assert_called_once()
        args = mock_errorlog.add_entry.call_args[0]
        assert args[0] == "test.md"
        assert args[1] == 5


def test_img_completed_failure_includes_script_in_error(tmp_path):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(
        success=False, status="FAIL",
        script_lines=["cube(5);"],
        image_file="/tmp/bad.png"
    )
    with patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        gen.img_completed(req)
        msg = mock_errorlog.add_entry.call_args[0][2]
        assert "cube(5);" in msg


def test_img_completed_failure_includes_image_name_in_error(tmp_path):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(success=False, image_file="/tmp/myimage.png")
    with patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        gen.img_completed(req)
        msg = mock_errorlog.add_entry.call_args[0][2]
        assert "myimage.png" in msg


# --- MarkdownImageGen: log_completed ---

def test_log_completed_success_no_errorlog(tmp_path):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(success=True)
    with patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        gen.log_completed(req)
        mock_errorlog.add_entry.assert_not_called()


def test_log_completed_failure_adds_to_errorlog(tmp_path):
    gen, _ = make_gen(tmp_path)
    req = make_mock_req(
        success=False, errors=["ERROR: bad"], warnings=[],
        src_file="input.md", src_line=10
    )
    with patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        gen.log_completed(req)
        mock_errorlog.add_entry.assert_called_once()
        args = mock_errorlog.add_entry.call_args[0]
        assert args[0] == "input.md"
        assert args[1] == 10


# --- MarkdownImageGen: processFiles ---

def test_processfiles_plain_text_passthrough(tmp_path):
    """Lines without openscad fences are written unchanged to output."""
    infile = write_md(tmp_path / "plain.md", "# Hello\n\nJust text.\n")
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        gen.processFiles([str(infile)])

    outfile = os.path.join(opts.docs_dir, "plain.md")
    content = open(outfile).read()
    assert "# Hello" in content
    assert "Just text." in content


def test_processfiles_image_block_queues_request(tmp_path):
    """An openscad-3D block causes an image_manager.new_request call."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        gen.processFiles([str(infile)])
        mock_img.new_request.assert_called_once()
        call_kwargs = mock_img.new_request.call_args[1]
        assert call_kwargs["default_colorscheme"] == "Cornfield"


def test_processfiles_image_block_passes_extyp(tmp_path):
    """The meta string (extyp) is extracted from the fence header."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        gen.processFiles([str(infile)])
        pos_args = mock_img.new_request.call_args[0]
        assert "3D" in pos_args  # extyp is a positional arg


def test_processfiles_image_block_output_contains_figure(tmp_path):
    """Output markdown has an image reference."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    outfile = os.path.join(opts.docs_dir, "img.md")
    content = open(outfile).read()
    assert "![Figure 1]" in content


def test_processfiles_image_block_output_contains_code_fence(tmp_path):
    """Non-ImgOnly block shows the script as a code block."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "img.md")).read()
    assert "```openscad" in content
    assert "sphere(10);" in content


def test_processfiles_imgonly_hides_code_fence(tmp_path):
    """ImgOnly suppresses the code block in output."""
    # extyp = line.split("-")[1], so ImgOnly must be the sole tag
    infile = write_md(tmp_path / "img.md", "```openscad-ImgOnly\nsphere(10);\n```\n")
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "img.md")).read()
    assert "```openscad" not in content
    assert "![Figure 1]" in content


def test_processfiles_script_strips_double_dash_from_output(tmp_path):
    """Lines starting with '--' are excluded from the shown code fence."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\n--hidden();\nvisible();\n```\n")
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "img.md")).read()
    assert "hidden();" not in content
    assert "visible();" in content


def test_processfiles_spin_uses_gif_extension(tmp_path):
    """Spin animation blocks produce a .gif image filename."""
    infile = write_md(tmp_path / "anim.md", "```openscad-Spin\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        imgfile_arg = mock_img.new_request.call_args[0][2]
        assert imgfile_arg.endswith(".gif")


def test_processfiles_anim_uses_gif_extension(tmp_path):
    """Anim blocks produce a .gif image filename."""
    infile = write_md(tmp_path / "anim.md", "```openscad-Anim\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        imgfile_arg = mock_img.new_request.call_args[0][2]
        assert imgfile_arg.endswith(".gif")


def test_processfiles_png_animation_overrides_gif(tmp_path):
    """When png_animation=True, Spin still produces .png."""
    infile = write_md(tmp_path / "anim.md", "```openscad-Spin\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path, png_animation=True)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        imgfile_arg = mock_img.new_request.call_args[0][2]
        assert imgfile_arg.endswith(".png")


def test_processfiles_multiple_image_blocks_numbered(tmp_path):
    """Multiple image blocks get sequential figure numbers."""
    md = "```openscad-3D\nsphere(10);\n```\n```openscad-3D\ncube(5);\n```\n"
    infile = write_md(tmp_path / "multi.md", md)
    gen, opts = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "multi.md")).read()
    assert "Figure 1" in content
    assert "Figure 2" in content


def test_processfiles_no_fence_no_image_request(tmp_path):
    """Plain markdown without openscad blocks makes no image requests."""
    infile = write_md(tmp_path / "plain.md", "# Title\n\nSome text.\n")
    gen, _ = make_gen(tmp_path)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        mock_img.new_request.assert_not_called()


def test_processfiles_log_block_queues_log_request(tmp_path):
    """openscad-log block causes a log_manager.new_request call."""
    infile = write_md(tmp_path / "log.md", '```openscad-log\necho("hi");\n```\n')
    gen, _ = make_gen(tmp_path)

    mock_req = MagicMock()
    mock_req.success = True
    mock_req.echos = ["hi"]

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        mock_log.new_request.return_value = mock_req
        gen.processFiles([str(infile)])
        mock_log.new_request.assert_called_once()


def test_processfiles_log_block_output_has_log_fence(tmp_path):
    """Processed log block has a ```log code fence in output."""
    infile = write_md(tmp_path / "log.md", '```openscad-log\necho("hi");\n```\n')
    gen, opts = make_gen(tmp_path)

    mock_req = MagicMock()
    mock_req.success = True
    mock_req.echos = ["hello from openscad"]

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        mock_log.new_request.return_value = mock_req
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "log.md")).read()
    assert "```log" in content
    assert "hello from openscad" in content


def test_processfiles_log_block_no_echos_shows_fallback(tmp_path):
    """Log block with no echos shows 'No log output generated.'"""
    infile = write_md(tmp_path / "log.md", '```openscad-log\necho("hi");\n```\n')
    gen, opts = make_gen(tmp_path)

    mock_req = MagicMock()
    mock_req.success = True
    mock_req.echos = []

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        mock_log.new_request.return_value = mock_req
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "log.md")).read()
    assert "No log output generated." in content


def test_processfiles_log_block_failure_shows_fallback(tmp_path):
    """Failed log request shows 'No log output generated.'"""
    infile = write_md(tmp_path / "log.md", '```openscad-log\nbad syntax;\n```\n')
    gen, opts = make_gen(tmp_path)

    mock_req = MagicMock()
    mock_req.success = False
    mock_req.echos = []

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        mock_log.new_request.return_value = mock_req
        gen.processFiles([str(infile)])

    content = open(os.path.join(opts.docs_dir, "log.md")).read()
    assert "No log output generated." in content


def test_processfiles_writes_output_file(tmp_path):
    """Output file is written when test_only=False."""
    infile = write_md(tmp_path / "out.md", "# Hello\n")
    gen, opts = make_gen(tmp_path, test_only=False)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    outfile = os.path.join(opts.docs_dir, "out.md")
    assert os.path.exists(outfile)


def test_processfiles_test_only_skips_output_file(tmp_path):
    """Output file is NOT written when test_only=True."""
    infile = write_md(tmp_path / "out.md", "# Hello\n")
    gen, opts = make_gen(tmp_path, test_only=True)

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    outfile = os.path.join(opts.docs_dir, "out.md")
    assert not os.path.exists(outfile)


def test_processfiles_force_calls_process_requests(tmp_path):
    """force=True always calls image_manager.process_requests."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path, force=True)

    with patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        mock_img.process_requests.assert_called_once()


def test_processfiles_unchanged_no_force_skips_process_requests(tmp_path):
    """Unchanged file without force=True skips image_manager.process_requests."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path, force=False, test_only=False)

    # Patch filehashes.is_changed to return False (unchanged)
    with patch.object(gen.filehashes, "is_changed", return_value=False), \
         patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        mock_img.process_requests.assert_not_called()
        mock_img.purge_requests.assert_called_once()


def test_processfiles_always_purges_requests(tmp_path):
    """purge_requests is called even when process_requests is skipped."""
    infile = write_md(tmp_path / "img.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path, force=False, test_only=False)

    with patch.object(gen.filehashes, "is_changed", return_value=False), \
         patch("openscad_docsgen.mdimggen.image_manager") as mock_img, \
         patch("openscad_docsgen.mdimggen.log_manager") as mock_log:
        gen.processFiles([str(infile)])
        mock_img.purge_requests.assert_called_once()
        mock_log.purge_requests.assert_called_once()


def test_processfiles_errorlog_invalidates_filehash(tmp_path):
    """When a file has errors, its filehash is invalidated."""
    infile = write_md(tmp_path / "bad.md", "```openscad-3D\nsphere(10);\n```\n")
    gen, _ = make_gen(tmp_path)

    with patch.object(gen.filehashes, "invalidate") as mock_invalidate, \
         patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"), \
         patch("openscad_docsgen.mdimggen.errorlog") as mock_errorlog:
        mock_errorlog.file_has_errors.return_value = True
        gen.processFiles([str(infile)])
        mock_invalidate.assert_called_once_with(str(infile))


def test_processfiles_saves_filehashes(tmp_path):
    """filehashes.save() is called after processing."""
    infile = write_md(tmp_path / "img.md", "# text\n")
    gen, _ = make_gen(tmp_path)

    with patch.object(gen.filehashes, "save") as mock_save, \
         patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])
        mock_save.assert_called_once()


def test_processfiles_file_prefix_applied(tmp_path):
    """file_prefix is prepended to the output filename."""
    infile = write_md(tmp_path / "shape.md", "# Hello\n")
    gen, opts = make_gen(tmp_path, file_prefix="gen_")

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"):
        gen.processFiles([str(infile)])

    outfile = os.path.join(opts.docs_dir, "gen_shape.md")
    assert os.path.exists(outfile)


# --- mdimggen_main ---

def test_mdimggen_main_no_srcfiles_exits(tmp_path, monkeypatch):
    """With no source files, main exits with error."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["openscad-mdimggen"])
    with pytest.raises(SystemExit) as exc:
        mdimggen_main()
    assert exc.value.code != 0


def test_mdimggen_main_with_srcfile_runs(tmp_path, monkeypatch):
    """main runs processFiles when a valid source file is given."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "test.md", "# Hello\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "openscad-mdimggen", "-D", str(docs), str(infile)
    ])

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"), \
         patch("openscad_docsgen.mdimggen.errorlog") as mock_el:
        mock_el.has_errors = False
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code == 0


def test_mdimggen_main_rcfile_string_source(tmp_path, monkeypatch):
    """RC file with source_files as a string glob is expanded."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "mylib.md", "# Hi\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    rcfile = tmp_path / ".openscad_mdimggen_rc"
    rcfile.write_text(yaml.dump({
        "docs_dir": str(docs),
        "source_files": str(tmp_path / "*.md"),
    }))
    monkeypatch.setattr(sys, "argv", ["openscad-mdimggen"])

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"), \
         patch("openscad_docsgen.mdimggen.errorlog") as mock_el:
        mock_el.has_errors = False
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code == 0


def test_mdimggen_main_rcfile_list_source(tmp_path, monkeypatch):
    """RC file with source_files as a list of globs is expanded."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "mylib.md", "# Hi\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    rcfile = tmp_path / ".openscad_mdimggen_rc"
    rcfile.write_text(yaml.dump({
        "docs_dir": str(docs),
        "source_files": [str(tmp_path / "*.md")],
    }))
    monkeypatch.setattr(sys, "argv", ["openscad-mdimggen"])

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"), \
         patch("openscad_docsgen.mdimggen.errorlog") as mock_el:
        mock_el.has_errors = False
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code == 0


def test_mdimggen_main_oserror_exits(tmp_path, monkeypatch):
    """OSError during processFiles causes exit with error."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "test.md", "# Hello\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "openscad-mdimggen", "-D", str(docs), str(infile)
    ])

    with patch("openscad_docsgen.mdimggen.MarkdownImageGen") as MockGen:
        MockGen.return_value.processFiles.side_effect = OSError("disk full")
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code == -1


def test_mdimggen_main_keyboard_interrupt_exits(tmp_path, monkeypatch):
    """KeyboardInterrupt during processFiles causes exit with error."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "test.md", "# Hello\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "openscad-mdimggen", "-D", str(docs), str(infile)
    ])

    with patch("openscad_docsgen.mdimggen.MarkdownImageGen") as MockGen:
        MockGen.return_value.processFiles.side_effect = KeyboardInterrupt()
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code == -1


def test_mdimggen_main_errorlog_has_errors_exits_nonzero(tmp_path, monkeypatch):
    """When errorlog reports errors after processing, exit code is non-zero."""
    monkeypatch.chdir(tmp_path)
    infile = write_md(tmp_path / "test.md", "# Hello\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "openscad-mdimggen", "-D", str(docs), str(infile)
    ])

    with patch("openscad_docsgen.mdimggen.image_manager"), \
         patch("openscad_docsgen.mdimggen.log_manager"), \
         patch("openscad_docsgen.mdimggen.errorlog") as mock_el:
        mock_el.has_errors = True
        with pytest.raises(SystemExit) as exc:
            mdimggen_main()
    assert exc.value.code != 0
