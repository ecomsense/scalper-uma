from src.constants import orders_cache


def get_orders():
    try:
        return orders_cache
    except Exception as e:
        print("Failed to fetch cached orders:", e)
        return []
