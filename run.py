"""Single entry point:  python run.py"""
import sys

import uvicorn

from app.config import ConfigError, get_settings


def main() -> None:
    try:
        settings = get_settings()
    except ConfigError as exc:
        sys.exit(f"Configuration error: {exc}")
    print(f"\n  AI Data Quality Intelligence Platform\n  → http://{settings.host}:{settings.port}"
          f"   (API docs: /api/docs)\n")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug,
                log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
