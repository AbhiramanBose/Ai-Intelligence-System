from pathlib import Path


def assert_video_exists(path: str) -> None:
    if not Path(path).exists():
        raise FileNotFoundError(f"Video not found: {path}")
