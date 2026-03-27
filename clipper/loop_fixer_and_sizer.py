from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from clipper.clip_postprocess import *  # noqa: F401,F403
    from clipper.clip_postprocess import main
else:
    from .clip_postprocess import *  # noqa: F401,F403
    from .clip_postprocess import main


if __name__ == "__main__":
    main()
