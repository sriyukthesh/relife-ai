from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import catalog, models  # noqa: F401  (models import registers tables)
from .config import get_settings
from .database import Base, engine
from .routers import auth, builds, checkout, copilot, inspect, inventory, marketplace, projects, salvage, stats, workbench


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="ReLife AI", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(projects.router)
app.include_router(inspect.router)
app.include_router(builds.router)
app.include_router(copilot.router)
app.include_router(marketplace.router)
app.include_router(checkout.router)
app.include_router(stats.router)
app.include_router(salvage.router)
app.include_router(workbench.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/catalog")
def get_catalog():
    """Categories, required specs and field metadata; the frontend builds its confirm form from this."""
    return {
        "categories": catalog.CATEGORIES,
        "spec_fields": catalog.SPEC_FIELDS,
        "conditions": list(catalog.CONDITIONS),
    }
