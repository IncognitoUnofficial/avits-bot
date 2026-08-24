# result_saver.py
import json
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def save_result(email: str, tokens: Dict[str, str], session_data: Dict[str, Any],
                result_file: str = "avits_login_result.json"):
    """Save login results to a JSON file."""
    output = {
        "timestamp": datetime.now().isoformat(),
        "email": email,
        "tokens": tokens,
        "session": session_data,
    }
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info(f"Results saved to {result_file}")
    return output