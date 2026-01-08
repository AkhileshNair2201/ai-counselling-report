from __future__ import annotations

from celery import Celery

from server.config import get_celery_broker_url, get_celery_result_backend

celery_app = Celery(
    "counseling_notes",
    broker=get_celery_broker_url(),
    backend=get_celery_result_backend(),
    include=["server.tasks.session_processing"],
)

celery_app.conf.task_track_started = True
