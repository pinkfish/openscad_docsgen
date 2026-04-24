import os
import pytest
from PIL import Image
from unittest.mock import MagicMock, patch
from openscad_runner import RenderMode

from openscad_docsgen.imagemanager import ImageRequest, ImageManager
from .conftest import requires_openscad


# --- Helpers ---

def make_png(path, color=(200, 100, 50), size=(32, 32)):
    img = Image.new("RGB", size, color)
    img.save(str(path))


def make_req(meta="", script=None, image_file="/tmp/test_out.png"):
    if script is None:
        script = ["sphere(10);"]
    return ImageRequest("test.scad", 1, image_file, script, meta)


# --- ImageRequest: script_lines stripping ---

def test_script_lines_passthrough():
    req = make_req(script=["sphere(10);"])
    assert req.script_lines[-1] == "sphere(10);"


def test_script_lines_strips_double_dash_prefix():
    req = make_req(script=["--sphere(10);"])
    assert req.script_lines[-1] == "sphere(10);"


def test_script_lines_does_not_strip_single_dash():
    req = make_req(script=["-sphere(10);"])
    assert req.script_lines[-1] == "-sphere(10);"


# --- ImageRequest: defaults (empty meta) ---

def test_defaults_imgsize():
    req = make_req()
    assert req.imgsize == [320.0, 240.0]


def test_defaults_show_edges_false():
    assert make_req().show_edges is False


def test_defaults_show_axes_true():
    assert make_req().show_axes is True


def test_defaults_show_scales_true():
    assert make_req().show_scales is True


def test_defaults_orthographic_true():
    assert make_req().orthographic is True


def test_defaults_script_under_false():
    assert make_req().script_under is False


def test_defaults_animation_frames_none():
    assert make_req().animation_frames is None


def test_defaults_frame_ms():
    assert make_req().frame_ms == 250


def test_defaults_color_scheme():
    assert make_req().color_scheme == "Cornfield"


def test_defaults_render_mode_preview():
    assert make_req().render_mode == RenderMode.preview


def test_defaults_complete_false():
    assert make_req().complete is False


def test_defaults_success_false():
    assert make_req().success is False


def test_defaults_camera_set_when_no_dynamic_vp():
    req = make_req()
    assert req.camera == [0, 0, 0, 55, 0, 25, 444]


# --- ImageRequest: render mode ---

def test_render_mode_thrown_together():
    req = make_req(meta="ThrownTogether")
    assert req.render_mode == RenderMode.thrown_together


def test_render_mode_render():
    req = make_req(meta="Render")
    assert req.render_mode == RenderMode.render


# --- ImageRequest: view options ---

def test_show_edges_true():
    assert make_req(meta="Edges").show_edges is True


def test_show_axes_false():
    assert make_req(meta="NoAxes").show_axes is False


def test_show_scales_false():
    assert make_req(meta="NoScales").show_scales is False


def test_orthographic_false_with_perspective():
    assert make_req(meta="Perspective").orthographic is False


# --- ImageRequest: image sizes ---

def test_size_explicit():
    req = make_req(meta="Size=640x480")
    assert req.imgsize == [640, 480]


def test_size_small():
    req = make_req(meta="Small")
    assert req.imgsize == [240.0, 180.0]


def test_size_med():
    req = make_req(meta="Med")
    assert req.imgsize == [480.0, 360.0]


def test_size_big():
    req = make_req(meta="Big")
    assert req.imgsize == [640.0, 480.0]


def test_size_huge():
    req = make_req(meta="Huge")
    assert req.imgsize == [800.0, 600.0]


# --- ImageRequest: viewport ---

def test_3d_sets_vpr():
    # 3D mode → non-dynamic, camera set with 3D vpr defaults
    req = make_req(meta="3D")
    assert req.camera is not None
    assert req.camera[3] == 55  # vpr[0] = 55


def test_2d_sets_vpr_to_top_down():
    req = make_req(meta="2D")
    assert req.camera is not None
    assert req.camera[3] == 0   # vpr[0] = 0
    assert req.camera[4] == 0   # vpr[1] = 0
    assert req.camera[5] == 0   # vpr[2] = 0


def test_vpd_makes_dynamic():
    req = make_req(meta="VPD=440")
    assert req.camera is None   # dynamic viewport → camera=None


def test_vpd_prepends_script_lines():
    req = make_req(meta="VPD=440", script=["sphere(10);"])
    vp_lines = [l for l in req.script_lines if "$vpd" in l]
    assert len(vp_lines) == 1
    assert "440" in vp_lines[0]


def test_spin_sets_dynamic_and_frames():
    req = make_req(meta="Spin")
    assert req.camera is None
    assert req.animation_frames == 36


def test_flatspin_sets_dynamic():
    req = make_req(meta="FlatSpin")
    assert req.camera is None
    assert req.animation_frames == 36


def test_anim_sets_dynamic():
    req = make_req(meta="Anim")
    assert req.camera is None
    assert req.animation_frames == 36


def test_frames_override():
    req = make_req(meta="Spin;Frames=12")
    assert req.animation_frames == 12


def test_fps_sets_frame_ms():
    req = make_req(meta="FPS=10")
    assert req.frame_ms == 100


def test_framems_sets_frame_ms():
    req = make_req(meta="FrameMS=500")
    assert req.frame_ms == 500


# --- ImageRequest: color scheme ---

def test_color_scheme_from_meta():
    req = make_req(meta="ColorScheme=BeforeDawn")
    assert req.color_scheme == "BeforeDawn"


def test_default_colorscheme_param():
    req = ImageRequest("test.scad", 1, "/tmp/out.png", ["sphere(10);"], "", default_colorscheme="Sunset")
    assert req.color_scheme == "Sunset"


def test_meta_colorscheme_overrides_default():
    req = ImageRequest("test.scad", 1, "/tmp/out.png", ["sphere(10);"], "ColorScheme=Metallic", default_colorscheme="Sunset")
    assert req.color_scheme == "Metallic"


# --- ImageRequest: script_under ---

def test_script_under_long_line():
    long_line = "x" * 100
    req = make_req(script=[long_line])
    assert req.script_under is True


def test_script_under_explicit_flag():
    req = make_req(meta="ScriptUnder")
    assert req.script_under is True


def test_script_under_false_short_line():
    req = make_req(script=["sphere(10);"])
    assert req.script_under is False


# --- ImageRequest: _parse_vp_line ---

def test_parse_vp_line_all_numeric():
    req = make_req()
    trio, dyn = req._parse_vp_line("10, 20, 30", [0, 0, 0], False)
    assert trio == [10.0, 20.0, 30.0]
    assert dyn is False


def test_parse_vp_line_with_expression():
    req = make_req()
    trio, dyn = req._parse_vp_line("10, 360*$t, 30", [0, 0, 0], False)
    assert trio[1] == "360*$t"
    assert dyn is True


def test_parse_vp_line_wrong_count_uses_old():
    req = make_req()
    old = [1, 2, 3]
    trio, dyn = req._parse_vp_line("10, 20", old, False)
    assert trio == old


# --- ImageRequest: starting / completed ---

def test_starting_calls_callback():
    called = []
    req = make_req()
    req.starting_cb = lambda r: called.append(r)
    req.starting()
    assert called == [req]


def test_starting_no_callback():
    req = make_req()
    req.starting_cb = None
    req.starting()  # should not raise


def test_completed_without_osc():
    req = make_req()
    req.completed("SKIP")
    assert req.complete is True
    assert req.status == "SKIP"
    assert req.success is True


def test_completed_calls_callback():
    called = []
    req = make_req()
    req.completion_cb = lambda r: called.append(r.status)
    req.completed("NEW")
    assert called == ["NEW"]


# --- ImageManager: new_request ---

def test_image_manager_new_request_queues():
    mgr = ImageManager()
    req = mgr.new_request("test.scad", 1, "/tmp/out.png", ["sphere(10);"], "")
    assert req in mgr.requests


def test_image_manager_new_request_norender_raises():
    mgr = ImageManager()
    with pytest.raises(Exception, match="NORENDER"):
        mgr.new_request("test.scad", 1, "/tmp/out.png", ["sphere(10);"], "NORENDER")


def test_image_manager_purge_requests():
    mgr = ImageManager()
    mgr.new_request("test.scad", 1, "/tmp/out.png", ["sphere(10);"], "")
    mgr.purge_requests()
    assert mgr.requests == []


# --- ImageManager.image_compare ---

def test_image_compare_identical(tmp_path):
    p = tmp_path / "img.png"
    make_png(p)
    assert ImageManager.image_compare(str(p), str(p))


def test_image_compare_same_content(tmp_path):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    make_png(p1, color=(100, 150, 200))
    make_png(p2, color=(100, 150, 200))
    assert ImageManager.image_compare(str(p1), str(p2))


def test_image_compare_different_colors(tmp_path):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    make_png(p1, color=(0, 0, 0))
    make_png(p2, color=(255, 255, 255))
    assert not ImageManager.image_compare(str(p1), str(p2))


def test_image_compare_different_sizes(tmp_path):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    make_png(p1, size=(32, 32))
    make_png(p2, size=(64, 64))
    assert not ImageManager.image_compare(str(p1), str(p2))


def test_image_compare_similar_within_threshold(tmp_path):
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    make_png(p1, color=(100, 100, 100))
    make_png(p2, color=(140, 100, 100))  # diff of 40 in R channel, within 64
    assert ImageManager.image_compare(str(p1), str(p2))


def test_image_compare_gif_identical(tmp_path):
    """GIF comparison uses filecmp (byte-identical)."""
    from PIL import Image as PILImage
    p = tmp_path / "a.gif"
    img = PILImage.new("P", (10, 10), 0)
    img.save(str(p))
    assert ImageManager.image_compare(str(p), str(p))


# --- Integration tests: requires OpenSCAD ---

@requires_openscad
def test_process_request_test_only(tmp_path, monkeypatch):
    """test_only mode runs OpenSCAD syntax check but skips image output."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "out.png"
    mgr = ImageManager()
    statuses = []
    req = mgr.new_request(
        "test.scad", 1, str(out),
        ["sphere(10);"], "3D",
        completion_cb=lambda r: statuses.append(r.status)
    )
    mgr.process_requests(test_only=True)
    assert req.complete is True
    assert req.success is True
    assert statuses == ["SKIP"]
    assert not out.exists()


@requires_openscad
def test_process_request_generates_image(tmp_path, monkeypatch):
    """Full render produces a PNG file."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "sphere.png"
    mgr = ImageManager()
    req = mgr.new_request(
        "test.scad", 1, str(out),
        ["sphere(10);"], "3D"
    )
    mgr.process_requests(test_only=False)
    assert req.complete is True
    assert req.success is True
    assert out.exists()
    assert req.status in ("NEW", "REPLACE", "SKIP")


@requires_openscad
def test_process_request_skip_on_unchanged(tmp_path, monkeypatch):
    """Re-rendering the same script results in SKIP (image unchanged)."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "sphere.png"
    script = ["sphere(10);"]

    mgr1 = ImageManager()
    mgr1.new_request("test.scad", 1, str(out), script, "3D")
    mgr1.process_requests()
    assert out.exists()

    mgr2 = ImageManager()
    statuses = []
    mgr2.new_request(
        "test.scad", 1, str(out), script, "3D",
        completion_cb=lambda r: statuses.append(r.status)
    )
    mgr2.process_requests()
    assert statuses == ["SKIP"]


@requires_openscad
def test_process_request_replace_on_changed(tmp_path, monkeypatch):
    """Re-rendering a different script results in REPLACE."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "shape.png"

    mgr1 = ImageManager()
    mgr1.new_request("test.scad", 1, str(out), ["sphere(10);"], "3D")
    mgr1.process_requests()

    mgr2 = ImageManager()
    statuses = []
    mgr2.new_request(
        "test.scad", 1, str(out), ["cube(20);"], "3D",
        completion_cb=lambda r: statuses.append(r.status)
    )
    mgr2.process_requests()
    assert statuses == ["REPLACE"]


@requires_openscad
def test_process_request_fails_on_invalid_script(tmp_path, monkeypatch):
    """Invalid OpenSCAD script leads to a failed request."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "bad.png"
    mgr = ImageManager()
    statuses = []
    mgr.new_request(
        "test.scad", 1, str(out),
        ["this is not valid openscad !!!;"],
        "3D",
        completion_cb=lambda r: statuses.append(r.status)
    )
    mgr.process_requests()
    assert statuses == ["FAIL"]
    assert not out.exists()


# --- ImageRequest: VPR / VPT / VPF meta parsing ---

def test_vpr_meta_sets_custom_rotation():
    req = make_req(meta="VPR=[10,20,30]")
    # dynamic_vp=True because VPR sets vpd via VPD default → no, VPR alone doesn't set dynamic
    # Actually VPR alone: _vpr_re matches, _parse_vp_line returns all-numeric → dyn_vp=False
    # dynamic_vp stays False (no other dynamic flag), so camera should be set
    assert req.camera is not None
    assert req.camera[3] == 10.0  # vpr[0]
    assert req.camera[4] == 20.0  # vpr[1]
    assert req.camera[5] == 30.0  # vpr[2]


def test_vpt_meta_sets_translation():
    req = make_req(meta="VPT=[5,10,15]")
    assert req.camera is not None
    assert req.camera[0] == 5.0
    assert req.camera[1] == 10.0
    assert req.camera[2] == 15.0


def test_vpf_meta_sets_dynamic():
    # VPF sets dynamic_vp = True → camera = None
    req = make_req(meta="VPF=45")
    assert req.camera is None


def test_script_with_vp_variable_sets_no_vp_false(tmp_path, monkeypatch):
    """Script lines containing '$vp' set no_vp=False, disabling auto_center/view_all."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "out.png"
    # new_img_file = "tmp_out.png" relative to CWD (base_name="out.png", file_base="out")
    new_img = tmp_path / "tmp_out.png"

    mock_osc = MagicMock()
    mock_osc.good.return_value = True
    mock_osc.warnings = []
    mock_osc.errors = []
    mock_osc.success = True

    def fake_run():
        make_png(str(new_img))

    mock_osc.run.side_effect = fake_run

    with patch("openscad_docsgen.imagemanager.OpenScadRunner", return_value=mock_osc) as MockOSC:
        mgr = ImageManager()
        req = mgr.new_request(
            "test.scad", 1, str(out),
            ["$vpt = [0,0,0];", "sphere(10);"],
            "VPD=440"  # dynamic so script_lines get $vp prepended
        )
        mgr.process_requests()

    # The call should have auto_center=False and view_all=False because $vp is in script
    call_kwargs = MockOSC.call_args[1]
    assert call_kwargs["auto_center"] is False
    assert call_kwargs["view_all"] is False


# --- ImageManager: warning masking ---

def _make_mock_osc(warnings, good=True):
    mock_osc = MagicMock()
    mock_osc.good.return_value = good
    mock_osc.warnings = list(warnings)
    mock_osc.errors = []
    mock_osc.success = True
    return mock_osc


def test_masked_warning_removed_request_succeeds(tmp_path, monkeypatch):
    """Warnings matching masked strings are removed; request completes as NEW."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "out.png"
    new_img = tmp_path / "tmp_out.png"

    mock_osc = _make_mock_osc(["Viewall and autocenter disabled - something"])

    def fake_run():
        make_png(str(new_img))

    mock_osc.run.side_effect = fake_run

    with patch("openscad_docsgen.imagemanager.OpenScadRunner", return_value=mock_osc):
        mgr = ImageManager()
        statuses = []
        mgr.new_request(
            "test.scad", 1, str(out),
            ["sphere(10);"], "3D",
            completion_cb=lambda r: statuses.append(r.status)
        )
        mgr.process_requests()

    assert statuses == ["NEW"]


def test_unmasked_warning_causes_fail(tmp_path, monkeypatch):
    """Warnings not matching masked strings survive and cause FAIL."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "out.png"

    mock_osc = _make_mock_osc(["Some real warning that is not masked"])

    with patch("openscad_docsgen.imagemanager.OpenScadRunner", return_value=mock_osc):
        mgr = ImageManager()
        statuses = []
        mgr.new_request(
            "test.scad", 1, str(out),
            ["sphere(10);"], "3D",
            completion_cb=lambda r: statuses.append(r.status)
        )
        mgr.process_requests()

    assert statuses == ["FAIL"]


def test_nef_fallback_warning_masked(tmp_path, monkeypatch):
    """'failed with error, falling back to Nef operation' is also masked."""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "images" / "out.png"
    new_img = tmp_path / "tmp_out.png"

    mock_osc = _make_mock_osc(["CGAL error: failed with error, falling back to Nef operation"])

    def fake_run():
        make_png(str(new_img))

    mock_osc.run.side_effect = fake_run

    with patch("openscad_docsgen.imagemanager.OpenScadRunner", return_value=mock_osc):
        mgr = ImageManager()
        statuses = []
        mgr.new_request(
            "test.scad", 1, str(out),
            ["sphere(10);"], "3D",
            completion_cb=lambda r: statuses.append(r.status)
        )
        mgr.process_requests()

    assert statuses == ["NEW"]
