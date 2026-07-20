import requests
from config import TWELVE_API

def get_price(pair):
    try:
        symbols = {
            "XAU/USD": "XAU/USD",
            "XAG/USD": "XAG/USD",
        }

        symbol = symbols.get(pair, pair)

        url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={symbol}"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        print(data)  # لمعرفة سبب الخطأ إذا حدث

        if "price" in data:
            return float(data["price"])

        return None

    except Exception as e:
        print(e)
        return None
