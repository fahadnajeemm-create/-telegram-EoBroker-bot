import requests

import pandas as pd

import pandas_ta as ta

from config import TWELVE_API

def get_price(pair):

    try:

        pair = pair.replace(" (ذهب)", "")
