"""Order object module."""
import json
import math
from datetime import datetime
from decimal import Decimal
from typing import TypeVar

import boto3
from krakenapi import KrakenApi

T = TypeVar("T", bound="Order")


class Order:
    """
    Kraken order encapsulation.
    """

    user_name: str
    date: datetime
    pair: str
    type: str
    order_type: str
    o_flags: str
    pair_price: float
    volume: float
    price: float
    fee: float
    total_price: float
    txid: str
    description: str

    def __init__(
        self,
        user_name: str,
        date: datetime,
        pair: str,
        type: str,
        order_type: str,
        o_flags: str,
        pair_price: float,
        volume: float,
        price: float,
        fee: float,
        total_price: float,
    ) -> None:
        """
        Initialize the Order object.
        More information on Kraken documentation
        (Add standard order):
        https://www.kraken.com/en-us/features/api

        :param user_name: User executing the order.
        :param date: Order date as datetime.
        :param pair: Order pair.
        :param type: Buy or sell order.
        :param order_type: Order type.
        :param o_flags: Order additional flags.
        :param volume: Order volume.
        :param price: Order price.
        :param fee: Order fee.
        :param pair_price: Order pair price.
        :param total_price: Total price of the order (order price + fee).
        """
        self.user_name = user_name
        self.date = date
        self.pair = pair
        self.type = type
        self.order_type = order_type
        self.o_flags = o_flags
        self.pair_price = pair_price
        self.volume = volume
        self.price = price
        self.fee = fee
        self.total_price = total_price

    @classmethod
    def buy_limit_order(
        cls,
        user_name: str,
        date: datetime,
        pair: str,
        amount: float,
        pair_price: float,
        lot_decimals: int,
        quote_decimals: int,
    ) -> T:
        """
        Create a limit order for specified dca pair and amount.

        :param user_name: User executing the order.
        :param date: Order date as datetime.
        :param pair: Asset pair.
        :param amount: Amount to buy,
        :param pair_price: Limit order pair price.
        :param lot_decimals: Pair lot decimals.
        :param quote_decimals: Pair quote asset decimals.
        :return: Instance of Order object.
        """
        volume = cls.set_order_volume(amount, pair_price, lot_decimals)
        price = cls.estimate_order_price(volume, pair_price, quote_decimals)
        fee = cls.estimate_order_fee(volume, pair_price, quote_decimals)
        type = "buy"
        order_type = "limit"
        # Pay fee in quote asset.
        o_flags = "fciq"
        total_price = round(price + fee, quote_decimals)
        return cls(
            user_name,
            date,
            pair,
            type,
            order_type,
            o_flags,
            pair_price,
            volume,
            price,
            fee,
            total_price,
        )

    def send_order(self, ka: KrakenApi) -> None:
        """
        Execute the order by sending it to Kraken API.
        Add the returned TXID and order description to Order object.

        :param ka: krakenAPI object.
        :return: None
        """
        response = ka.create_order(
            self.pair,
            self.type,
            self.order_type,
            self.pair_price,
            self.volume,
            self.o_flags,
        )
        self.txid = response.get("txid")[0]
        self.description = response.get("descr").get("order")

    def save_order_dynamo(self, orders_table: str) -> None:
        """
        Save Order object attributes to Dynamo DB.

        :return: None
        """
        client = boto3.resource("dynamodb")
        table = client.Table(orders_table)
        order_json = json.dumps(self.__dict__, default=str)
        order_item = json.loads(order_json, parse_float=Decimal)
        table.put_item(Item=order_item)

    @staticmethod
    def set_order_volume(
        amount: float, pair_price: float, lot_decimals: float
    ) -> float:
        """
        Define order volume for specified DCA amount,
        pair price and pair decimals based on Kraken lot decimals.
        Volume is adjusted for 0.026% Kraken taker fees
        to be at the maximum cost of the amount specified
        in the configuration

        :param amount: DCA amount.
        :param pair_price: Pair price.
        :param lot_decimals: Lot decimals as float.
        :return: Fee adjusted order volume as flat.
        """
        decimals = 10**lot_decimals
        try:
            order_volume = (
                math.floor(amount / pair_price * decimals) / decimals
            )
            # Adjust amount to the 0.26% taker fee on Kraken
            order_volume_fee_adjusted = (
                math.floor(order_volume / 1.0026 * decimals) / decimals
            )
        except ZeroDivisionError:
            raise ZeroDivisionError(
                "Order set_order_volume -> pair_price must not be 0."
            )
        return order_volume_fee_adjusted

    @staticmethod
    def estimate_order_price(
        volume: float, pair_price: float, quote_decimals: int
    ) -> float:
        """
        Get order price for specified order volume
        and pair price and 0.26% taker fees.
        Rounded to quote asset decimals.

        :param volume: Order volume.
        :param pair_price: Pair price.
        :param quote_decimals: Quote asset decimals as float.
        :return: Adjusted order price as float.
        """
        order_price = volume * pair_price
        return round(order_price, quote_decimals)

    @staticmethod
    def estimate_order_fee(
        volume: float, pair_price: float, quote_decimals: int
    ) -> float:
        """
        Return order fee based on the 0.026%
        fee from kraken on limit maker orders.
        Rounded to quote asset decimals.

        :param volume: Order volume.
        :param pair_price: Pair price.
        :param quote_decimals: Quote asset decimals as float.
        :return: Order fees as float.
        """
        order_price = volume * pair_price
        fees = order_price * 0.0026
        return round(fees, quote_decimals)
