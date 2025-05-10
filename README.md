# 🔌 Lumaris Compute Marketplace

**Turn any computer into an EC2-like resource.**  
Lumaris is a distributed compute marketplace that lets buyers submit jobs and sellers run them in isolated environments, powered by Docker (and soon via SSH).

---

## 🚀 Overview

This project enables buyers to:

- Submit custom code or shell commands as jobs
- Define environment variables and setup steps
- Automatically execute the job in a secure Docker container
- Retrieve outputs and track job status

All jobs are handled via a robust asynchronous FastAPI + Celery backend with Redis as the broker and PostgreSQL as the job store.

---

## 🛠 Tech Stack

- **FastAPI** – RESTful API
- **SQLAlchemy + PostgreSQL** – Job persistence
- **Celery + Redis** – Task queue and background workers
- **Docker SDK (Python)** – Secure job execution in containers

---

## 📦 API Sample

### Submit a Job

```http
POST /jobs/submit
````

```json
{
  "cmd": "python script.py",
  "env": { "X": "10" },
  "git": "https://github.com/user/myrepo.git",
  "setup": ["pip install -r requirements.txt"]
}
```

### Get Job Status

```http
GET /jobs/{job_id}
```

---

## ⚙️ Running the Project

1. Clone the repo
2. Start with Docker Compose:

   ```bash
   docker-compose up --build
   ```

    This will set up the FastAPI server, Redis, and PostgreSQL.
3. Access the API at `http://localhost:8000`

---

## 📌 Roadmap

### ✅ Current Features

- [x] Docker-based secure execution of arbitrary jobs
- [x] API to submit and track job execution
- [x] Result storage and job logging

---

### 🧠 Planned Features

| Feature                            | Description                                               |
| ---------------------------------- | --------------------------------------------------------- |
| 🔐 SSH-based remote execution      | Run jobs on actual seller VMs using SSH instead of Docker |
| 💻 Seller registration & heartbeat | Let sellers register and send availability updates        |
| ⚖️ Matchmaking engine              | Match buyer jobs with optimal seller based on capacity    |
| 💳 Resource billing system         | Charge buyers based on CPU, memory, and time              |
| 🛡 Authentication                  | Secure endpoints with JWT tokens for buyers/sellers       |
| 📊 Admin dashboard                 | View live job queue, seller stats, and history            |
| 🧾 Log & file storage              | Persist logs, error traces, or result files per job       |

---

## 📃 License

MIT License — Use freely with attribution.

---

## 🤝 Contributing

Want to contribute a seller daemon, SSH job runner, or GPU support? PRs welcome!
