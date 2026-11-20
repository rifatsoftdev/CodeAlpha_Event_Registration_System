from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .core.database import Base, engine
from .routers import auth, events, registrations

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="EventHub — Event Registration System", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(registrations.router)


@app.get("/", tags=["health"])
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/register", include_in_schema=False)
def signup_page():
    return FileResponse(STATIC_DIR / "signup.html")


@app.get("/forgot-password", include_in_schema=False)
def forgot_password_page():
    return FileResponse(STATIC_DIR / "forgot-password.html")


@app.get("/reset-password", include_in_schema=False)
def reset_password_page():
    return FileResponse(STATIC_DIR / "reset-password.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "docs": "/docs"}
