from fastapi import FastAPI
from surgiform.api.router import api_router

app = FastAPI(title="Surgiform API", version="0.1.0")
app.include_router(api_router)

# 건강 체크
@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}