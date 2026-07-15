from __future__ import annotations

from functools import wraps

from flask import abort
from flask_login import current_user

from croqui_engine.storage.database import Job


def role_required(*roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def user_can_edit() -> bool:
    return current_user.is_authenticated and current_user.role in {"admin", "engineer", "operator"}


def user_can_generate() -> bool:
    return current_user.is_authenticated and current_user.role in {"admin", "engineer"}


def user_can_edit_job(job: Job) -> bool:
    if not user_can_edit():
        return False
    if current_user.role == "admin":
        return True
    return (job.created_by or "").lower() == (current_user.email or "").lower()


def user_can_generate_job(job: Job) -> bool:
    if not user_can_generate():
        return False
    if current_user.role == "admin":
        return True
    return (job.created_by or "").lower() == (current_user.email or "").lower()
