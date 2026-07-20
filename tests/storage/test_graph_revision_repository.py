from __future__ import annotations

import json
import uuid

from croqui_engine.storage.database import init_db
from croqui_engine.storage.repositories import GraphRevisionRepository


def test_graph_revisions_are_versioned_and_latest_is_recoverable():
    init_db()
    repository = GraphRevisionRepository()
    job_id = f"synthetic-{uuid.uuid4().hex}"

    first = repository.create(
        job_id,
        json.dumps({"id": "synthetic", "version": 1}),
        "test-admin@example.invalid",
        "automatic_generation",
    )
    second = repository.create(
        job_id,
        json.dumps({"id": "synthetic", "version": 2}),
        "test-admin@example.invalid",
        "engineer_regeneration",
    )

    assert first.revision == 1
    assert second.revision == 2
    assert [item.revision for item in repository.list(job_id)] == [2, 1]
    assert json.loads(repository.latest(job_id).graph_json)["version"] == 2
