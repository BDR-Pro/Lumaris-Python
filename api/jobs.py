from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from sellers.vm_manager import destroy_vm
from models.database import get_session
from models.job import Job, JobStatus
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
    if not active_sellers:
        raise HTTPException(status_code=503, detail="No sellers available")

    matched_seller_id, seller_ws = next(iter(active_sellers.items()))
    job_id = uuid.uuid4()

    try:
        await seller_ws.send_json({
            "type": "spawn_vm",
            "job_id": str(job_id),
            "ssh_pubkey": job.ssh_pubkey,
            "image": job.preferred_image,
            "cpu_quota": job.cpu_quota,
            "mem_limit": job.mem_limit
        })

        response = await seller_ws.receive_json()

        if response.get("status") != "ok":
            raise HTTPException(status_code=500, detail="Seller failed to provision VM")

        new_job = Job(
            id=job_id,
            cmd="ssh execution",
            env={},
            git=None,
            setup=[],
            status=JobStatus.QUEUED,
            output=None,
            celery_id=None,
            vm_container_id=response.get("container_id")  # optional tracking
        )
        session.add(new_job)
        await session.commit()

        return JobResponse(
            job_id=str(job_id),
            seller_ip=response["ip"],
            ssh_port=response["port"],
            ssh_user=response["user"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error contacting seller: {str(e)}")

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
            "cmd": job.cmd,
            "env": job.env,
            "git": job.git,
            "setup": job.setup,
            "output": job.output,
        }
        for job in jobs
    ]

@router.post("/jobs/{job_id}/destroy")
async def destroy_job(job_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
    job = result.scalar_one_or_none()

    if not job or not job.vm_container_id:
        raise HTTPException(status_code=404, detail="Job or VM not found")
    # call the WS to check if the seller is available
    active_sellers = active_sellers_dict()  # This should be your active sellers dict
    seller_ws = next(iter(active_sellers.values()), None)
    if not seller_ws:
        raise HTTPException(status_code=503, detail="Seller unavailable")

    await seller_ws.send_json({"type": "destroy_vm", "job_id": job_id})
    data = await seller_ws.receive_json()

    if data.get("status") != "ok":
        raise HTTPException(status_code=500, detail=f"Failed to destroy: {data.get('error')}")

    job.status = JobStatus.COMPLETED
    await session.commit()

    return {"detail": "VM destroyed successfully"}


@router.post("/jobs/{job_id}/terminate")
async def terminate_vm(job_id: str):
    try:
        await destroy_vm(job_id)  # from vm_manager
        return {"status": "terminated"}
    except Exception as e:
        raise HTTPException(500, detail=str(e))
