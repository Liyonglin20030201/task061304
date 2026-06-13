from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import engine, Base
from app.api import auth, stores, sales, inventory, members, promotions, traffic, weather, analytics, imports, reports, tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="连锁门店经营数据分析平台",
    description="多源数据接入、指标建模、智能分析、报表导出",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(stores.router, prefix="/api")
app.include_router(sales.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(promotions.router, prefix="/api")
app.include_router(traffic.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "连锁门店经营数据分析平台"}
