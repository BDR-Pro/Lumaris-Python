from celery import Celery
import docker
import os
import uuid
import tempfile
import shutil
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("celery_worker")

# Celery app
celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_BACKEND_URL", "redis://localhost:6379/1"),
)

# Allowed images for security
ALLOWED_IMAGES = {"python:3.10-slim", "ubuntu:22.04"}
MAX_CPU_QUOTA = 200000  # in microseconds
MAX_MEM_LIMIT = "2g"    # memory cap

@celery_app.task(name="execute_job")
def execute_job(cmd: str, env: dict = {}, git: str = None, setup: list = [],
                image: str = "python:3.10-slim", mem_limit="512m", cpu_quota=50000):

    job_id = str(uuid.uuid4())
    client = docker.from_env()
    workdir = tempfile.mkdtemp(prefix=f"job_{job_id}_")

    try:
        logger.info(f"[{job_id}] Preparing job environment...")

        # Clone git repo if provided
        if git:
            subprocess.run(["git", "clone", git, workdir], check=True)
            logger.info(f"[{job_id}] Cloned repo: {git}")

        # Write setup script if needed
        if setup:
            setup_script = os.path.join(workdir, "setup.sh")
            with open(setup_script, "w") as f:
                f.write("\n".join(setup))
            os.chmod(setup_script, 0o755)

        full_cmd = "./setup.sh && " + cmd if setup else cmd
        container_env = {str(k): str(v) for k, v in env.items()}

        # Enforce limits and image policy
        if image not in ALLOWED_IMAGES:
            image = "python:3.10-slim"

        cpu_quota = min(cpu_quota, MAX_CPU_QUOTA)
        if mem_limit.endswith("g") and int(mem_limit[:-1]) > int(MAX_MEM_LIMIT[:-1]):
            mem_limit = MAX_MEM_LIMIT

        logger.info(f"[{job_id}] Running Docker container...")
        result = client.containers.run(
            image,
            command=["/bin/bash", "-c", full_cmd],
            volumes={workdir: {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
            environment=container_env,
            network_disabled=True,
            remove=True,
            stderr=True,
            stdout=True,
            mem_limit=mem_limit,
            cpu_period=100000,
            cpu_quota=cpu_quota,
        )

        logger.info(f"[{job_id}] Job completed.")
        return {"job_id": job_id, "output": result.decode("utf-8")}

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}")
        return {"job_id": job_id, "error": str(e)}

    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        logger.info(f"[{job_id}] Cleaned up workspace.")
