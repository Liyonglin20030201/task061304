import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database import engine, Base, AsyncSessionLocal
from app.api import auth, stores, sales, inventory, members, promotions, traffic, weather, analytics, imports, reports, tasks
from app.api import replenishment, site_selection, marketing, supply_chain
from app.api import port_energy, port_cargo, port_scheduling, port_analytics, port_ws
from app.api import space_layout
from app.api import omnichannel
from app.api import association
from app.api import store_energy
from app.services.port_energy_service import start_energy_simulator
import app.models.port_equipment
import app.models.port_cargo
import app.models.port_scheduling
import app.models.port_analytics
import app.models.space_layout
import app.models.omnichannel
import app.models.association
import app.models.store_energy


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    simulator_task = asyncio.create_task(start_energy_simulator(AsyncSessionLocal))
    yield
    simulator_task.cancel()
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
app.include_router(replenishment.router, prefix="/api")
app.include_router(site_selection.router, prefix="/api")
app.include_router(marketing.router, prefix="/api")
app.include_router(supply_chain.router, prefix="/api")
app.include_router(port_energy.router, prefix="/api")
app.include_router(port_cargo.router, prefix="/api")
app.include_router(port_scheduling.router, prefix="/api")
app.include_router(port_analytics.router, prefix="/api")
app.include_router(port_ws.router, prefix="/api")
app.include_router(space_layout.router, prefix="/api")
app.include_router(omnichannel.router, prefix="/api")
app.include_router(association.router, prefix="/api")
app.include_router(store_energy.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "连锁门店经营数据分析平台"}
