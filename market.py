import requests
from config import ALPHA_API

def get_forex(base, quote):

    url = (
        "https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY"
        f"&from_symbol={base}"
        f"&to_symbol={quote}"
        f"&interval=1min"
        f"&outputsize=compact"
        f"&apikey={ALPHA_API}"
    )

    data = requests.get(url, timeout=20).json()

    key = "Time Series FX (1min)"

    if key not in data:
        return None

    candles = []

    for t in data[key]:

        c = data[key][t]

        candles.append({

            "time": t,

            "open": float(c["1. open"]),

            "high": float(c["2. high"]),

            "low": float(c["3. low"]),

            "close": float(c["4. close"])

        })

    candles.reverse()

    return candles
