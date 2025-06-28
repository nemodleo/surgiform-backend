from datetime import datetime
from datetime import timezone

from fastapi import APIRouter
from surgiform.deploy.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="헬스 체크")
async def health() -> dict:
    """
    서비스 상태 점검용 엔드포인트.

    - `status`: 항상 `"ok"` 반환
    - `time`: UTC ISO8601 타임스탬프
    - `env`: 실행 환경(dev/prod 등)
    - `version`: 패키지 버전(pyproject.toml의 version)
    """
    settings = get_settings()
    return {
        "status": "ok",
        "time": datetime.now(timezone.utc).isoformat(),
        "env": settings.app_env,
        "version": "0.1.0",  # 버전 문자열을 하드코딩하거나 importlib.metadata 사용 가능
    }