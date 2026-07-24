from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import sqlite3
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

PROJECTS = {
    "caxias": "Caxias",
    "vacaria": "Vacaria",
}

DEFAULT_USERS = (
    {"username": "caxias1", "display_name": "Caxias 1", "role": "project", "project_slug": "caxias"},
    {"username": "caxias2", "display_name": "Caxias 2", "role": "project", "project_slug": "caxias"},
    {"username": "vacaria1", "display_name": "Vacaria 1", "role": "project", "project_slug": "vacaria"},
    {"username": "vacaria2", "display_name": "Vacaria 2", "role": "project", "project_slug": "vacaria"},
    {"username": "admin1", "display_name": "Administrador 1", "role": "admin", "project_slug": None},
    {"username": "admin2", "display_name": "Administrador 2", "role": "admin", "project_slug": None},
    {"username": "admin3", "display_name": "Administrador 3", "role": "admin", "project_slug": None},
    {"username": "admin4", "display_name": "Administrador 4", "role": "admin", "project_slug": None},
)

MIN_PASSWORD_LENGTH = 12
MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 5 * 60


@dataclass(frozen=True)
class AuthPaths:
    database: Path
    initial_credentials: Path
    session_secret: Path

    @classmethod
    def from_environment(cls) -> "AuthPaths":
        data_dir = Path(os.getenv("CROQUIMAKER_DATA_DIR", "generated"))
        auth_dir = data_dir / "auth"
        return cls(
            database=Path(os.getenv("CROQUIMAKER_AUTH_DB", str(auth_dir / "auth.db"))),
            initial_credentials=Path(
                os.getenv(
                    "CROQUIMAKER_INITIAL_CREDENTIALS_FILE",
                    str(auth_dir / "initial-credentials.txt"),
                )
            ),
            session_secret=Path(
                os.getenv("CROQUIMAKER_SECRET_FILE", str(auth_dir / "session-secret"))
            ),
        )


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(descriptor, "w", encoding="utf-8") as private_file:
        private_file.write(content)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_or_create_session_secret(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        value = ""
    if len(value) < 32:
        value = secrets.token_urlsafe(48)
        _write_private(path, value + "\n")
    return value


class AuthStore:
    def __init__(self, database: Path, initial_credentials: Path):
        self.database = Path(database)
        self.initial_credentials = Path(initial_credentials)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self, bootstrap_password: str | None = None) -> bool:
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'project')),
                    project_slug TEXT CHECK (project_slug IN ('caxias', 'vacaria') OR project_slug IS NULL),
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    locked_until REAL,
                    created_at REAL NOT NULL
                )
                """
            )
            existing = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if existing:
                return False

            common_password = bootstrap_password
            if common_password is None:
                common_password = os.getenv("CROQUIMAKER_BOOTSTRAP_PASSWORD", "").strip() or None
            if common_password is not None and len(common_password) < MIN_PASSWORD_LENGTH:
                raise ValueError(
                    f"CROQUIMAKER_BOOTSTRAP_PASSWORD deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres"
                )

            created_at = time.time()
            credentials: list[tuple[str, str]] = []
            for spec in DEFAULT_USERS:
                password = common_password or secrets.token_urlsafe(15)
                connection.execute(
                    """
                    INSERT INTO users (
                        username, display_name, role, project_slug, password_hash, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        spec["username"],
                        spec["display_name"],
                        spec["role"],
                        spec["project_slug"],
                        generate_password_hash(password),
                        created_at,
                    ),
                )
                credentials.append((spec["username"], password))

        lines = [
            "Credenciais iniciais do Croquimaker",
            "Altere as senhas e remova este arquivo após a entrega aos usuários.",
            "",
        ]
        lines.extend(f"{username}: {password}" for username, password in credentials)
        _write_private(self.initial_credentials, "\n".join(lines) + "\n")
        return True

    def authenticate(self, username: str, password: str) -> dict | None:
        normalized = username.strip()
        now = time.time()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (normalized,),
            ).fetchone()
            if row is None:
                return None
            if row["locked_until"] and row["locked_until"] > now:
                return None
            if not check_password_hash(row["password_hash"], password):
                attempts = int(row["failed_attempts"]) + 1
                locked_until = now + LOCK_SECONDS if attempts >= MAX_FAILED_ATTEMPTS else None
                connection.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (0 if locked_until else attempts, locked_until, row["id"]),
                )
                return None
            connection.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                (row["id"],),
            )
            return self._public_user(row)

    def get_user(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ? AND is_active = 1",
                (user_id,),
            ).fetchone()
        return self._public_user(row) if row else None

    def list_users(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, display_name, role, project_slug, is_active
                FROM users
                ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, username
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def set_password(self, username: str, password: str) -> bool:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET password_hash = ?, failed_attempts = 0, locked_until = NULL
                WHERE username = ?
                """,
                (generate_password_hash(password), username.strip()),
            )
        return cursor.rowcount == 1

    @staticmethod
    def _public_user(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "display_name": row["display_name"],
            "role": row["role"],
            "project_slug": row["project_slug"],
        }


def _store_from_environment() -> AuthStore:
    paths = AuthPaths.from_environment()
    store = AuthStore(paths.database, paths.initial_credentials)
    store.initialize()
    return store


def _main() -> int:
    parser = argparse.ArgumentParser(description="Administracao local de usuarios do Croquimaker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list-users", help="Lista os oito usuarios e seus perfis")
    subparsers.add_parser(
        "show-initial-credentials",
        help="Exibe as credenciais criadas na primeira inicializacao",
    )
    password_parser = subparsers.add_parser(
        "set-password",
        help="Redefine a senha de um usuario",
    )
    password_parser.add_argument("username")
    args = parser.parse_args()

    paths = AuthPaths.from_environment()
    store = _store_from_environment()
    if args.command == "list-users":
        print(json.dumps(store.list_users(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "show-initial-credentials":
        if not paths.initial_credentials.exists():
            print("O arquivo de credenciais iniciais nao existe.")
            return 1
        print(paths.initial_credentials.read_text(encoding="utf-8"), end="")
        return 0
    if args.command == "set-password":
        password = getpass.getpass("Nova senha: ")
        confirmation = getpass.getpass("Confirme a nova senha: ")
        if password != confirmation:
            print("As senhas nao conferem.")
            return 1
        try:
            updated = store.set_password(args.username, password)
        except ValueError as error:
            print(str(error))
            return 1
        if not updated:
            print("Usuario nao encontrado.")
            return 1
        print("Senha atualizada.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
