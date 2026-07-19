import requests

def get_price(pair):
    try:
        # تحويل اسم الزوج إلى تنسيق مزود البيانات
        symbol = pair.replace("/", "")

        # مثال باستخدام مصدر مجاني
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}=X"

        response = requests.get(url, timeout=10)
        data = response.json()

        result = data["chart"]["result"][0]
        price = result["meta"]["regularMarketPrice"]

        return round(price, 5)

    except Exception:
        return None
