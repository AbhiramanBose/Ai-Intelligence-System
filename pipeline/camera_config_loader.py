import json
from pathlib import Path


def load_camera_config(path: str) -> dict:
    return json.loads(Path(path).read_text())
