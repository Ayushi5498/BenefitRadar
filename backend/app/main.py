"""
BenefitRadar — Card Benefit Activation Engine
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_db, create_indexes
from app.routers import cards, claims, matches, metrics, notifications, transactions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create DB indexes
    await create_indexes()
    yield
    # Shutdown: close DB connection
    await close_db()


app = FastAPI(
    title="BenefitRadar API",
    description=(
        "Card Benefit Activation Engine — automatically detects when a card "
        "purchase qualifies for purchase protection, return protection, or "
        "travel-delay insurance, and pre-fills the claim for you."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(transactions.router)
app.include_router(matches.router)
app.include_router(claims.router)
app.include_router(cards.router)
app.include_router(notifications.router)
app.include_router(metrics.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "BenefitRadar API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
