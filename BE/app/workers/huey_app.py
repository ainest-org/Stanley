from huey import RedisHuey

from app.core.config import get_settings

settings = get_settings()

huey = RedisHuey("pmtool", url=settings.redis_url)

from app.workers import tasks  # noqa: E402,F401 — registers tasks on `huey`; import after its creation
