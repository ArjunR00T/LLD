from fastapi import FastAPI
from contextlib import asynccontextmanager

from routes.store_routes import storerouter
from routes.rate_limit_routes import router as rate_limit_router

from datastore.in_memory_store import InMemoryStore
from middleware.rate_limitter import RateLimiter, rate_limitter, SlidingWindowStrategy

@asynccontextmanager
async def lifespan(app: FastAPI):
    store = InMemoryStore()
    store.load()
    app.state.store = store
    app.state.rate_limiter = RateLimiter(strategy=SlidingWindowStrategy())
    yield
    store.save()

app = FastAPI(lifespan=lifespan)
app.middleware("http")(rate_limitter)
app.include_router(storerouter)
app.include_router(rate_limit_router)

@app.get("/")
def health_check():
    return {"status": "ok"}
