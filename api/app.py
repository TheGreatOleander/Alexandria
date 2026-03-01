
from fastapi import FastAPI
from .routes import router

app = FastAPI(title="Alexandria Temporal Kernel API", version="0.6.0")
app.include_router(router)
