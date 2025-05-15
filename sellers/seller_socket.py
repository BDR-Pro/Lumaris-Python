from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from models.database import get_session
from models.job import Job, JobStatus
from sellers.vm_manager import handle_spawn_vm, destroy_vm
import uuid
import logging
from fastapi import Query
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

router = APIRouter()
logger = logging.getLogger("seller_socket")

# In-memory map: seller_id -> WebSocket connection
active_sellers: dict[str, WebSocket] = {}

# === Pydantic Schemas ===
class JobRequest(BaseModel):
    ssh_pubkey: str
    preferred_image: str = "python:3.10-slim"
    cpu_quota: int = 50000
    mem_limit: str = "512m"

class JobResponse(BaseModel):
    job_id: str
    seller_ip: str
    ssh_port: int
    ssh_user: str

class SellerStatus(BaseModel):
    ip: str
    ssh_port: int
    ssh_user: str
    available: bool = True
    image: str = "python:3.10-slim"
    cpu_available: int = 100000
    mem_available: str = "2g"

# === WebSocket endpoint for sellers to register ===
@router.websocket("/ws/seller/{seller_id}")
async def seller_ws(websocket: WebSocket, seller_id: str):
    await websocket.accept()
    active_sellers[seller_id] = websocket
    logger.info(f"Seller connected: {seller_id}")

    try:
        while True:
            message = await websocket.receive_json()

            match message.get("type"):
                case "spawn_vm":
                    result = await handle_spawn_vm(message)
                    await websocket.send_json(result)
                case "destroy_vm":
                    await destroy_vm(message.get("job_id"))
                case _:
                    logger.warning(f"Unknown message type from seller {seller_id}: {message}")
    except WebSocketDisconnect:
        logger.warning(f"Seller {seller_id} disconnected")
        active_sellers.pop(seller_id, None)

# === REST endpoint for buyer to request VM for SSH job ===
@router.post("/jobs/submit", response_model=JobResponse)
async def submit_job(job: JobRequest, session: AsyncSession = Depends(get_session)):
    if not active_sellers:
        raise HTTPException(status_code=503, detail="No sellers available")

    # Pick first available seller
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
            raise HTTPException(status_code=500, detail="Seller failed to spawn VM")

        new_job = Job(
            id=job_id,
            cmd="ssh connection",
            env={},
            git=None,
            setup=[],
            status=JobStatus.QUEUED,
            output=None,
            celery_id=str(uuid.uuid4()),
            vm_container_id=response.get("container_id"),  # Save container ref if needed
            container_id=response.get("container_id"),
            start_time = datetime.now(),
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
        logger.error(f"Error submitting job to seller: {e}")
        raise HTTPException(status_code=500, detail=f"Error communicating with seller: {e}")



@router.websocket("/ws/seller/{seller_id}")
async def seller_ws(websocket: WebSocket, seller_id: str, token: str = Query(...)):
    if token != os.getenv("SELLER_AUTH_TOKEN"):
        await websocket.close()
        return
    await websocket.accept()