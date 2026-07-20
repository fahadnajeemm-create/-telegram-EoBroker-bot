import requests
from config import TWELVE_API

def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={pair}"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            return round(float(data["price"]), 5)

        print(data)
        return None

    except Exception as e:
        print(e)
        return None
