from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Float, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker
from werkzeug.security import generate_password_hash

from croqui_engine.core.cities import normalize_city_group
from croqui_engine.core.config import ensure_data_dirs, settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.sqlalchemy_url, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


class User(Base, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Administrador JOBEL")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="admin")
    city_group: Mapped[str] = mapped_column(String(40), default="admin")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        return self.active

    def can_edit(self) -> bool:
        return self.role in {"admin", "engineer", "operator"}

    def can_generate(self) -> bool:
        return self.role in {"admin", "engineer"}

    def can_admin(self) -> bool:
        return self.role == "admin"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_pdf_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="UPLOADED")
    message: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    tes_number: Mapped[str] = mapped_column(String(80), default="")
    municipality: Mapped[str] = mapped_column(String(160), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    payload_path: Mapped[str] = mapped_column(Text, default="")
    reviewed_payload_path: Mapped[str] = mapped_column(Text, default="")
    croqui_pdf_path: Mapped[str] = mapped_column(Text, default="")
    croqui_png_path: Mapped[str] = mapped_column(Text, default="")
    excel_path: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(255), default="")
    city_group: Mapped[str] = mapped_column(String(40), default="caxias_do_sul")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


def init_db() -> None:
    ensure_data_dirs()
    Base.metadata.create_all(engine)
    ensure_demo_columns()
    upsert_demo_users()


def ensure_demo_columns() -> None:
    if not settings.sqlalchemy_url.startswith("sqlite:///"):
        return
    with engine.begin() as conn:
        _ensure_column(conn, "users", "city_group", "VARCHAR(40) DEFAULT 'admin'")
        _ensure_column(conn, "jobs", "city_group", "VARCHAR(40) DEFAULT 'caxias_do_sul'")


def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def upsert_demo_users() -> None:
    db = SessionLocal()
    try:
        for item in _demo_users():
            existing = db.query(User).filter(User.email == item["email"]).first()
            if existing:
                existing.name = item["name"]
                existing.password_hash = generate_password_hash(item["password"])
                existing.role = item["role"]
                existing.city_group = normalize_city_group(item["city_group"], fallback="admin")
                existing.active = True
            else:
                db.add(
                    User(
                        name=item["name"],
                        email=item["email"],
                        password_hash=generate_password_hash(item["password"]),
                        role=item["role"],
                        city_group=normalize_city_group(item["city_group"], fallback="admin"),
                        active=True,
                    )
                )
        db.commit()
    finally:
        db.close()


def _demo_users() -> list[dict[str, str]]:
    return [
        {
            "name": "Administrador JOBEL",
            "email": settings.admin_email,
            "password": settings.admin_password,
            "role": "admin",
            "city_group": "admin",
        },
        {
            "name": "Caxias Operador 1",
            "email": "caxias1@jobel.local",
            "password": "Caxias@2026",
            "role": "engineer",
            "city_group": "caxias_do_sul",
        },
        {
            "name": "Caxias Operador 2",
            "email": "caxias2@jobel.local",
            "password": "Caxias@2026",
            "role": "engineer",
            "city_group": "caxias_do_sul",
        },
        {
            "name": "Vacaria Operador 1",
            "email": "vacaria1@jobel.local",
            "password": "Vacaria@2026",
            "role": "engineer",
            "city_group": "vacaria",
        },
        {
            "name": "Vacaria Operador 2",
            "email": "vacaria2@jobel.local",
            "password": "Vacaria@2026",
            "role": "engineer",
            "city_group": "vacaria",
        },
    ]
