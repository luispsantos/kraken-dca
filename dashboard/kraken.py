from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import boto3
import pandas as pd
import yaml
from krakenapi import KrakenApi

from file_io import persist_to_file

kraken_api = KrakenApi()

with open("pairs.yml", "r") as yml_file:
    pairs = yaml.safe_load(yml_file)


@persist_to_file("orders.csv")
def get_order_history():
    session = boto3.Session(profile_name="personal")
    client = session.resource("dynamodb")
    table = client.Table("kraken-dca")
    response = table.scan()
    for order in response["Items"]:
        for key, val in order.items():
            if isinstance(val, Decimal):
                order[key] = float(val)
    orders = pd.DataFrame(response["Items"])

    return orders


@persist_to_file("asset_prices.json")
def get_asset_prices():
    with ThreadPoolExecutor() as executor:
        asset_prices = list(executor.map(get_asset_price, pairs))
        asset_prices = dict(zip(pairs, asset_prices))

    return asset_prices


def get_asset_price(pair):
    ticker_information = kraken_api.get_pair_ticker(pair)
    pair_ask_price = float(ticker_information.get(pair).get("a")[0])
    return pair_ask_price
