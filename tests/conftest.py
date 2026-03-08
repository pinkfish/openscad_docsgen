import os
import shutil
import pytest

OPENSCAD_APP = "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
OPENSCAD_DIR = "/Applications/OpenSCAD.app/Contents/MacOS"


def openscad_available():
    return (
        shutil.which("openscad") is not None
        or os.path.isfile(OPENSCAD_APP)
    )


requires_openscad = pytest.mark.skipif(
    not openscad_available(),
    reason="OpenSCAD not installed"
)


@pytest.fixture(autouse=True)
def add_openscad_to_path(monkeypatch):
    """Add the macOS OpenSCAD app bundle to PATH so openscad_runner can find it."""
    if os.path.isfile(OPENSCAD_APP) and shutil.which("openscad") is None:
        monkeypatch.setenv("PATH", OPENSCAD_DIR + ":" + os.environ.get("PATH", ""))
