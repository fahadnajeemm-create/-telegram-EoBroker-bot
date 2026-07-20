import requests
from config import TWELVE_API


def get_candles(pair):
    try:
        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={pair}"
            f"&interval=1min"
            f"&outputsize=100"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "values" not in data:
            print(data)
            return None

        return data["values"]

    except Exception as e:
        print(e)
        return None
