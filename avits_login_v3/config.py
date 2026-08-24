# config.py
import json
import os
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    path = config_path or DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)