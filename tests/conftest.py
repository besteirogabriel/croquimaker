from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

test_data_dir = Path(tempfile.gettempdir()) / f"croquimaker-tests-{os.getpid()}"
test_data_dir.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(32))
os.environ.setdefault("CROQUI_ADMIN_EMAIL", "test-admin@example.invalid")
os.environ.setdefault("CROQUI_ADMIN_PASSWORD", secrets.token_urlsafe(32))
os.environ.setdefault("CROQUI_OPENAI_FALLBACK", "false")
os.environ.setdefault("CROQUI_DATA_DIR", str(test_data_dir))
os.environ.setdefault("UPLOAD_DIR", str(test_data_dir / "uploads"))
os.environ.setdefault("OUTPUT_DIR", str(test_data_dir / "outputs"))
os.environ.setdefault("CROQUI_TMP_DIR", str(test_data_dir / "tmp"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{test_data_dir / 'test.db'}")
