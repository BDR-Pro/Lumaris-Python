import docker
import uuid
import tempfile
import shutil
import os

# In-memory mapping for cleanup
active_containers = {}

# === SPAWN VM ===
async def handle_spawn_vm(request: dict):
    job_id = request.get("job_id")
    ssh_pubkey = request.get("ssh_pubkey")
    image = request.get("image", "python:3.10-slim")
    cpu_quota = int(request.get("cpu_quota", 50000))
    mem_limit = request.get("mem_limit", "512m")

    container_name = f"vm_{job_id[:8]}"
    ssh_port = str(2200 + (int(job_id[-4:], 16) % 1000))  # simple port logic
    ssh_user = "vmuser"

    # Create temporary working directory for .ssh
    workdir = tempfile.mkdtemp(prefix=f"vm_{job_id}_")
    ssh_dir = os.path.join(workdir, "ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    authorized_keys = os.path.join(ssh_dir, "authorized_keys")

    with open(authorized_keys, "w") as f:
        f.write(ssh_pubkey)

    try:
        client = docker.from_env()

        container = client.containers.run(
            image=image,
            name=container_name,
            command="/usr/sbin/sshd -D",
            ports={"22/tcp": ssh_port},
            volumes={ssh_dir: {"bind": "/home/vmuser/.ssh", "mode": "ro"}},
            detach=True,
            tty=True,
            stdin_open=True,
            network_mode="bridge",
            mem_limit=mem_limit,
            cpu_period=100000,
            cpu_quota=cpu_quota
        )

        active_containers[job_id] = container.id

        return {
            "status": "ok",
            "ip": "localhost",  # change to public IP in real deployment
            "port": int(ssh_port),
            "user": ssh_user,
            "container_id": container.id
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# === DESTROY VM ===
async def destroy_vm(job_id: str):
    try:
        container_id = active_containers.get(job_id)
        if not container_id:
            return

        client = docker.from_env()
        container = client.containers.get(container_id)
        container.kill()
        container.remove()
        active_containers.pop(job_id, None)

    except Exception as e:
        print(f"Failed to destroy VM for job {job_id}: {e}")