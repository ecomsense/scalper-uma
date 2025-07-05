from requests import get
from src.constants import SERVER


def get_orders():
    try:
        response = get(f"http://{SERVER}/sse/orders")
        return response.json()
    except Exception as e:
        print("Failed to fetch cached orders:", e)
        return []
