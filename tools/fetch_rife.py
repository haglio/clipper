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
import subprocess
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

_PROBE_TIMEOUT = 60


def is_present() -> bool:
    """Whether every file the app and its licence need is already extracted."""
    return all((DEST / member).is_file() for member in MEMBERS)


def runs() -> bool:
    """Whether the extracted executable can actually be run on this machine.

    The release is a Windows PE.  Elsewhere it is found and then refuses --
    ``subprocess`` raises PermissionError -- so presence is not runnability, and
    a test gated on presence alone fails where it meant to skip.  Any completed
    run counts, whatever the exit code: with no arguments the binary prints its
    usage and exits non-zero, and executing at all is the whole question.
    """
    if not is_present():
        return False
    try:
        subprocess.run([str(RIFE_EXE)], capture_output=True, timeout=_PROBE_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    return True


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
    urllib.request.urlretrieve(URL, target)  # noqa: S310 - literal https URL above
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
        print(f"RIFE is at {DEST} and runs here")
        return 0

    print(f"RIFE is at {DEST} but does not run here (it is a Windows binary)")
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
