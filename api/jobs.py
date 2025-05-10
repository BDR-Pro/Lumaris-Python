from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid

from models.database import get_session
from models.job import Job, JobStatus
from workers.celery_worker import execute_job
from celery.result import AsyncResult

router = APIRouter()

# Schemas
class JobRequest(BaseModel):
    cmd: str
    env: Optional[Dict[str, str]] = Field(default_factory=dict)
    git: Optional[str] = None
    setup: Optional[List[str]] = Field(default_factory=list)
    image: Optional[str] = "python:3.10-slim"
    cpu_quota: Optional[int] = 50000
    mem_limit: Optional[str] = "512m"

class JobResponse(BaseModel):
    job_id: str
    status: str

@router.post("/submit", response_model=JobResponse)
async def submit_job(job: JobRequest, session: AsyncSession = Depends(get_session)):
    job_id = uuid.uuid4()
    celery_task = execute_job.delay(
        job.cmd,
        job.env,
        job.git,
        job.setup,
        job.image,
        job.mem_limit,
        job.cpu_quota
    )

    new_job = Job(
        id=job_id,
        code=job.cmd,
        input_data=job.git or "",
        status=JobStatus.QUEUED,
        celery_id=celery_task.id
    )

    session.add(new_job)
    await session.commit()

    return JobResponse(job_id=str(job_id), status=JobStatus.QUEUED)

@router.get("/{job_id}")
async def get_job_status(job_id: str, session: AsyncSession = Depends(get_session)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    result = await session.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    task: AsyncResult = execute_job.AsyncResult(job.celery_id)
    if task.ready() and job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        job.output = str(task.result)
        job.status = JobStatus.COMPLETED if task.successful() else JobStatus.FAILED
        await session.commit()

    return {
        "job_id": str(job.id),
        "status": job.status,
        "output": job.output or None
    }

@router.get("/")
async def list_jobs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Job))
    jobs = result.scalars().all()
    return [
        {
            "job_id": str(job.id),
            "status": job.status,
            "input_data": job.input_data,
            "output": job.output or None
        }
        for job in jobs
    ]
