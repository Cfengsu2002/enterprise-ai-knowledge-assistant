from app.repositories.enterprise_repo import get_enterprise_by_id

def get_enterprise_info(enterprise_id: int):

    print("Fetching enterprise info for ID:", enterprise_id) 
    return get_enterprise_by_id(enterprise_id)
