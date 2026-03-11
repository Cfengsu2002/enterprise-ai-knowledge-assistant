from fastapi import APIRouter

from app.services.enterprise_service import get_enterprise_info

router = APIRouter()

@router.get("/enterprise/{id}")
def get_enter_info(id: int):
    print("enterprise_id =", id)  # 临时调试
    return get_enterprise_info(id)
