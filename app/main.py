from fastapi import FastAPI
from app.database import init_db
from app.errors.exception_handlers import register_exception_handlers
from app.middleware import RequestLoggingMiddleware
from app.routers import events, health, stores

app = FastAPI(title="Store Intelligence API", version="0.1.0")
app.add_middleware(RequestLoggingMiddleware)
register_exception_handlers(app)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(events.router)
app.include_router(stores.router)
app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "store-intelligence-api", "status": "running"}
