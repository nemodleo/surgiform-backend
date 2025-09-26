from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from surgiform.api.router import api_router
import json

app = FastAPI(title="Surgiform API", version="0.1.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.surgi-form.com",
        "https://surgi-form.com",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3003"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# Pydantic 검증 오류 핸들러
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Pydantic 검증 오류 발생:")
    print(f"  URL: {request.url}")
    print(f"  Method: {request.method}")
    print(f"  Headers: {dict(request.headers)}")
    
    # 요청 본문 읽기
    try:
        body = await request.body()
        print(f"  Request Body: {body.decode() if body else 'None'}")
    except Exception as e:
        print(f"  Request Body 읽기 실패: {e}")
    
    print(f"  Validation Errors: {exc.errors()}")
    
    # 원래 FastAPI 오류 응답 반환
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# 건강 체크
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}