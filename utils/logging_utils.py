import json
import logging
from datetime import UTC, datetime

from config.runtime import RuntimeConfig


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status_code", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def get_logger(name: str) -> logging.Logger:
    runtime = RuntimeConfig.from_env()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        if runtime.log_json:
            handler.setFormatter(JsonFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logging.getLogger(name)
