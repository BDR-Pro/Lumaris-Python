from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging
from sqlalchemy.exc import OperationalError
from models.database import engine
from models.job import Base

# Configure logging
logger = logging.getLogger("lifespan")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    max_tries = 30
    delay = 1.5

    for attempt in range(1, max_tries + 1):
        try:
            logger.info(f"🔁 Connecting to DB via SQLAlchemy (try {attempt})...")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ SQLAlchemy connection established and tables ready.")
            break
        except OperationalError as e:
            logger.warning(f"⏳ DB not ready ({attempt}/{max_tries}) — {type(e).__name__}: {e}")
            await asyncio.sleep(delay)
        except Exception as e:
            logger.exception(f"🔥 Unexpected error: {e}")
            await asyncio.sleep(delay)
    else:
        logger.error("❌ Could not connect to DB after several attempts.")
        raise RuntimeError("❌ Could not connect to DB after several attempts.")

    yield
    
# Initialize FastAPI app with lifespan context
app = FastAPI(title="Lumaris Compute Marketplace", lifespan=lifespan)

# Allow CORS from trusted frontend hosts (adjust in production)
origins = ["http://localhost", "http://localhost:3000", "*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from api import jobs, users
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(users.router, prefix="/users", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "Welcome to Lumaris Compute Marketplace API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
