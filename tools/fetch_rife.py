"""Fetch the RIFE frame interpolator, which this checkout does not carry.

    python tools/fetch_rife.py            # fetch if absent, report what is there
    python tools/fetch_rife.py --require  # ...and exit non-zero unless it runs

``tools/rife-ncnn-vulkan-20221029-windows/`` was committed until item 28: 62
files and 448 MB, of which the code opens one model directory.  Ten of the
eleven models went in stage 1; the remaining 17 MB is fetched here rather than
tracked, the way ``player_core/vendor/libmpv-2.dll`` is, so a clone stops paying
for a Windows binary most machines cannot execute.

It lands where ``clip_postprocess_transforms._find_rife_exe`` already looks, so
nothing in the app changes: with the files absent ``_rife_setup`` returns None
and the postprocess falls back to its geometric seam, exactly as it does on a
machine that never fetched.

Upstream, and the whole of this file's provenance::

    https://github.com/nihui/rife-ncnn-vulkan/releases/tag/20221029
    asset   rife-ncnn-vulkan-20221029-windows.zip
    sha256  d8e4d772d26cd8006ef0ad0bc82eb191b53c68677d1ae2f42506d74cbbbea606

MIT, (c) 2020 nihui.  Upstream's LICENSE is one of the six files extracted, so
the notice travels with the binaries it covers.

Six members come out and the other ten model directories stay in the zip, which
is deleted once they are extracted.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

RELEASE = "20221029"
ASSET = f"rife-ncnn-vulkan-{RELEASE}-windows.zip"
URL = f"https://github.com/nihui/rife-ncnn-vulkan/releases/download/{RELEASE}/{ASSET}"
SHA256 = "d8e4d772d26cd8006ef0ad0bc82eb191b53c68677d1ae2f42506d74cbbbea606"

TOOLS_DIR = Path(__file__).resolve().parent
DEST = TOOLS_DIR / f"rife-ncnn-vulkan-{RELEASE}-windows"
RIFE_EXE = DEST / "rife-ncnn-vulkan.exe"
ZIP_PATH = TOOLS_DIR / ASSET

# The executable, the C runtime it loads, the one model _rife_setup names, and
# upstream's own notice and usage.
MEMBERS = (
    "LICENSE",
    "README.md",
    "rife-ncnn-vulkan.exe",
    "vcomp140.dll",
    "rife-v4.6/flownet.bin",
    "rife-v4.6/flownet.param",
)

_DOWNLOAD_TIMEOUT = 120


def is_present() -> bool:
    """Whether every file the app and its licence need is extracted and non-empty.

    Non-empty because a restored cache or an interrupted extract can leave a
    file that exists and holds nothing, and ``is_file()`` alone calls that
    fetched.
    """
    return all(
        (DEST / member).is_file() and (DEST / member).stat().st_size > 0
        for member in MEMBERS
    )


def runs() -> bool:
    """Whether the interpolator actually produces a frame on this machine.

    Not whether the file is on disk, and not whether the process starts.  The
    release is a Windows PE that every other platform finds and then refuses;
    and a Windows box with no Vulkan device *starts* it happily and gets
    nothing back, because upstream prints its usage and exits before touching
    Vulkan when it is called with no arguments.  A spawn probe would answer
    yes to both, and the merge gate spends a step on this precisely so the four
    seam-bridge tests do not have to find out for it.

    So the question asked is the one those tests need answered: one real
    interpolation, through the same production call they make.  The app is
    imported lazily, so fetching does not need it installed.
    """
    if not is_present():
        return False

    import numpy as np

    from clipper.clip_postprocess_transforms import build_rife_bridge

    y, x = (a.astype(np.uint8) for a in np.mgrid[0:64, 0:64])
    try:
        return build_rife_bridge(np.dstack([x, y, x]), np.dstack([y, x, y]), 1) is not None
    except Exception:
        return False


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(target: Path = ZIP_PATH) -> Path:
    """Fetch the release asset to *target*, reusing an intact copy already there.

    The asset is 432 MB because upstream ships all eleven models in one zip, so
    a re-run that would download it again for six files it already has is worth
    avoiding.  A copy whose digest does not match is replaced rather than
    trusted.
    """
    if target.exists() and sha256_of(target) == SHA256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"fetching {URL}")
    # Streamed with a timeout rather than urlretrieve, which has none: a stalled
    # connection would otherwise hold a CI job open until the runner's own limit.
    with urllib.request.urlopen(URL, timeout=_DOWNLOAD_TIMEOUT) as response:  # noqa: S310
        with target.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    actual = sha256_of(target)
    if actual != SHA256:
        target.unlink(missing_ok=True)
        raise SystemExit(f"sha256 mismatch for {ASSET}: expected {SHA256}, got {actual}")
    return target


def extract(archive: Path, dest: Path = DEST) -> None:
    """Unpack the six members into *dest*, flat under it as upstream nests them."""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in MEMBERS:
            out = dest / member
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(f"rife-ncnn-vulkan-{RELEASE}-windows/{member}") as src:
                out.write_bytes(src.read())


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    require = "--require" in argv

    if not is_present():
        archive = download()
        extract(archive)
        archive.unlink(missing_ok=True)

    if not is_present():
        print(f"RIFE is still not at {DEST}", file=sys.stderr)
        return 1

    if runs():
        print(f"RIFE is at {DEST} and interpolates here")
        return 0

    print(
        f"RIFE is at {DEST} but produced no frame here — expected off Windows, "
        "where it is a PE that cannot be executed; on Windows it means the "
        "binary ran and the interpolation did not (no usable Vulkan device)."
    )
    if require:
        print(
            "--require was given, so this is a failure: the merge gate depends on "
            "the interpolator actually running.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
