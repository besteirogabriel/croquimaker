from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func

from croqui_engine.core.cities import normalize_city_group
from croqui_engine.storage.database import GraphRevision, Job, SessionLocal, User


class UserRepository:
    def get(self, user_id: str | int) -> User | None:
        db = SessionLocal()
        try:
            return db.get(User, int(user_id))
        finally:
            db.close()

    def get_by_email(self, email: str) -> User | None:
        db = SessionLocal()
        try:
            return db.query(User).filter(User.email == email.lower().strip()).first()
        finally:
            db.close()


class JobRepository:
    def create(self, job: Job) -> Job:
        db = SessionLocal()
        try:
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        finally:
            db.close()

    def get(self, job_id: str) -> Job | None:
        db = SessionLocal()
        try:
            return db.get(Job, job_id)
        finally:
            db.close()

    def update(self, job_id: str, **fields) -> Job | None:
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return None
            for key, value in fields.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(job)
            return job
        finally:
            db.close()

    def list_recent(self, limit: int = 50, city_group: str | None = None) -> list[Job]:
        db = SessionLocal()
        try:
            query = db.query(Job)
            if city_group:
                query = query.filter(Job.city_group == normalize_city_group(city_group))
            return query.order_by(Job.created_at.desc()).limit(limit).all()
        finally:
            db.close()

    def count_by_status(self, statuses: Iterable[str], city_group: str | None = None) -> int:
        db = SessionLocal()
        try:
            query = db.query(Job).filter(Job.status.in_(list(statuses)))
            if city_group:
                query = query.filter(Job.city_group == normalize_city_group(city_group))
            return query.count()
        finally:
            db.close()

    def count_all(self, city_group: str | None = None) -> int:
        db = SessionLocal()
        try:
            query = db.query(Job)
            if city_group:
                query = query.filter(Job.city_group == normalize_city_group(city_group))
            return query.count()
        finally:
            db.close()

    def dashboard_stats(self, city_group: str | None = None) -> dict[str, float | int]:
        db = SessionLocal()
        try:
            query = db.query(Job)
            if city_group:
                query = query.filter(Job.city_group == normalize_city_group(city_group))
            jobs = query.all()
            total = len(jobs)
            done = sum(1 for job in jobs if job.status == "DONE")
            review = sum(1 for job in jobs if job.status == "NEEDS_REVIEW")
            failed = sum(1 for job in jobs if job.status == "FAILED")
            alerts = sum(
                1 for job in jobs if (job.confidence or 0) < 0.85 and job.status != "FAILED"
            )
            pdf_ready = sum(1 for job in jobs if bool(job.croqui_pdf_path))
            excel_ready = sum(1 for job in jobs if bool(job.excel_path))
            avg_confidence = sum(job.confidence or 0 for job in jobs) / total if total else 0.0
            return {
                "processed": total,
                "review": review,
                "approved": done,
                "alerts": alerts,
                "failed": failed,
                "done": done,
                "pdf_ready": pdf_ready,
                "excel_ready": excel_ready,
                "avg_confidence": avg_confidence,
            }
        finally:
            db.close()

    def city_distribution(self) -> dict[str, int]:
        db = SessionLocal()
        try:
            rows = db.query(Job.city_group, func.count(Job.id)).group_by(Job.city_group).all()
            return {normalize_city_group(city): count for city, count in rows}
        finally:
            db.close()


class GraphRevisionRepository:
    def create(self, job_id: str, graph_json: str, created_by: str, reason: str) -> GraphRevision:
        db = SessionLocal()
        try:
            latest = (
                db.query(func.max(GraphRevision.revision))
                .filter(GraphRevision.job_id == job_id)
                .scalar()
                or 0
            )
            item = GraphRevision(
                job_id=job_id,
                revision=int(latest) + 1,
                graph_json=graph_json,
                created_by=created_by,
                reason=reason,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return item
        finally:
            db.close()

    def list(self, job_id: str) -> list[GraphRevision]:
        db = SessionLocal()
        try:
            return (
                db.query(GraphRevision)
                .filter(GraphRevision.job_id == job_id)
                .order_by(GraphRevision.revision.desc())
                .all()
            )
        finally:
            db.close()

    def latest(self, job_id: str) -> GraphRevision | None:
        db = SessionLocal()
        try:
            return (
                db.query(GraphRevision)
                .filter(GraphRevision.job_id == job_id)
                .order_by(GraphRevision.revision.desc())
                .first()
            )
        finally:
            db.close()
