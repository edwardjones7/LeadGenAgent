from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import leads, search
from app.routers import scheduler as scheduler_router
from app.scheduler import scheduler_instance, load_schedules_from_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_instance.start()
    await load_schedules_from_db()
    yield
    scheduler_instance.shutdown(wait=False)


app = FastAPI(title="Elenos Lead Gen API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(search.router)
app.include_router(scheduler_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
