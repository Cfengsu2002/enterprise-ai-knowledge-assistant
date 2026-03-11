from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.controllers.enterprise_controller import router as enterprise_router

app = FastAPI(title="Enterprise AI Knowledge Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(enterprise_router)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
#python3 -m uvicorn app.main:app --reload
# docker 下好
# 数据库一个真正的数据
#SQL 下载好，本地建立一个domain，在建立一个sql
#Alex Su建立reporitory，