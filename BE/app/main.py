from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.my_work import router as my_work_router
from app.api.radar import router as radar_router
from app.api.team_board import router as team_board_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="GitLab-Integrated PM Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(my_work_router)
app.include_router(team_board_router)
app.include_router(radar_router)
app.include_router(webhooks_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
