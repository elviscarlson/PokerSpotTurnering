from __future__ import annotations

import os


os.environ.setdefault(
    "APP_ENV",
    "production",
)


from run import app as application


__all__ = [
    "application",
]