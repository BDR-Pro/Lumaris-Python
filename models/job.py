from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
Base = declarative_base()

class JobStatus(PyEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cmd = Column(Text, nullable=False)
    env = Column(JSON, nullable=True)
    git = Column(String, nullable=True)
    setup = Column(JSON, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    output = Column(Text, nullable=True)
    celery_id = Column(String, nullable=True)
    vm_container_id = Column(String, nullable=True)  # Optional: track Docker container
    container_id = Column(String, nullable=True)
    start_time = Column(datetime, nullable=True)
    end_time = Column(datetime, nullable=True)
