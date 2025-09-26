from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from surgiform.api.router import api_router

app = FastAPI(title="Surgiform API", version="0.1.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.surgi-form.com",
        "https://surgi-form.com",
        "http://localhost:3000",
        "http://localhost:3003"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 건강 체크
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}