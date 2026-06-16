"""Standalone training-worker entrypoint.

Re-exports the in-process TrainingWorker so it can later run as a separate
process (V9: Redis/Celery). The roadmap checker also resolves this path.
"""
from app.services.training_worker import (
    TrainingWorker,
    get_training_worker,
    init_training_worker,
)

__all__ = ["TrainingWorker", "get_training_worker", "init_training_worker"]