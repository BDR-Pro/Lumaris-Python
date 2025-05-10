from enum import Enum as PyEnum
from sqlalchemy import Column, String, Text, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class JobStatus(PyEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cmd = Column(Text, nullable=False)  # replaces "code"
    env = Column(JSON, nullable=True)   # JSON field for environment variables
    git = Column(String, nullable=True) # optional git repo
    setup = Column(JSON, nullable=True) # list of setup shell commands
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    output = Column(Text, nullable=True)
    celery_id = Column(String, nullable=True)
