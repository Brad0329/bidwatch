from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import get_engine
from app.routers import admin, auth, keywords, notices, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine = get_engine()
    if engine:
        await engine.dispose()


app = FastAPI(title="BidWatch", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(keywords.router)
app.include_router(notices.router)
app.include_router(sources.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
