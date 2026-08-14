from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import agent, blockchain, chat, customers, dashboard, health, invoices

app = FastAPI(title="SettleFlow API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(customers.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(blockchain.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()
