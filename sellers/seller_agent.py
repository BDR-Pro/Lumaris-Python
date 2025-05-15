import asyncio
import websockets
import docker
import json
import uuid
import os
from dotenv import load_dotenv
load_dotenv()
server_ip = os.getenv("SELLER_IP", "localhost")  # Change to your server IP
# or hostname
API_URL = f"ws://{server_ip}:8000/ws/seller/seller-001"  # Change host/IP

client = docker.from_env()
container_registry = {}

async def handle_spawn_vm(data):
    job_id = data.get("job_id")
    ssh_pubkey = data.get("ssh_pubkey")
    image = data.get("image", "python:3.10-slim")
    cpu_quota = data.get("cpu_quota", 50000)
    mem_limit = data.get("mem_limit", "512m")

    container_name = f"vm_{job_id}"

    try:
        container = client.containers.run(
            image,
            command="/usr/sbin/sshd -D",
            detach=True,
            name=container_name,
            ports={"22/tcp": None},  # auto-assign port
            environment={},
            volumes={
                os.path.expanduser("~/.ssh"): {"bind": "/root/.ssh", "mode": "rw"}
            },
            cpu_period=100000,
            cpu_quota=cpu_quota,
            mem_limit=mem_limit,
        )

        container.reload()
        host_port = container.attrs["NetworkSettings"]["Ports"]["22/tcp"][0]["HostPort"]
        ip = os.getenv("SELLER_IP", "localhost")

        container_registry[job_id] = container.id

        return {
            "status": "ok",
            "job_id": job_id,
            "ip": ip,
            "port": int(host_port),
            "user": "root",
            "container_id": container.id,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}

async def handle_destroy_vm(data):
    job_id = data.get("job_id")
    container_id = container_registry.get(job_id)

    try:
        if container_id:
            container = client.containers.get(container_id)
            container.stop()
            container.remove()
            return {"status": "ok", "job_id": job_id}
        return {"status": "error", "error": "VM not found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

async def seller_loop():
    async with websockets.connect(API_URL) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)

            if data.get("type") == "spawn_vm":
                response = await handle_spawn_vm(data)
                await ws.send(json.dumps(response))

            elif data.get("type") == "destroy_vm":
                response = await handle_destroy_vm(data)
                await ws.send(json.dumps(response))

if __name__ == "__main__":
    asyncio.run(seller_loop())
