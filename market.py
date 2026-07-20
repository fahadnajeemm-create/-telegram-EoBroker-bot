import requests

API_KEY = "B3ZU4ZS44965VIYO"

def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        # الذهب
        if pair == "XAU/USD":
            url = (
                f"https://www.alphavantage.co/query"
                f"?function=CURRENCY_EXCHANGE_RATE"
                f"&from_currency=XAU"
                f"&to_currency=USD"
                f"&apikey={API_KEY}"
            )
        else:
            base, quote = pair.split("/")

            url = (
                f"https://www.alphavantage.co/query"
                f"?function=CURRENCY_EXCHANGE_RATE"
                f"&from_currency={base}"
                f"&to_currency={quote}"
                f"&apikey={API_KEY}"
            )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "Realtime Currency Exchange Rate" not in data:
            print(data)
            return None

        price = data["Realtime Currency Exchange Rate"]["5. Exchange Rate"]

        return round(float(price), 5)

    except Exception as e:
        print("Market Error:", e)
        return None
