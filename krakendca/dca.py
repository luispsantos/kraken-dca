"""Dollar Cost Averaging module."""
from datetime import datetime, timedelta

from krakenapi import KrakenApi

from .order import Order
from .pair import Pair
from .utils import (
    current_utc_datetime,
    current_utc_day_datetime,
    datetime_as_utc_unix,
    utc_unix_time_datetime,
)


class DCA:
    """
    Dollar Cost Averaging encapsulation.
    """

    ka: KrakenApi
    delay: int
    pair: Pair
    amount: float
    user_name: str
    orders_table: str
    limit_factor: float
    max_price: float

    def __init__(
        self,
        ka: KrakenApi,
        delay: int,
        pair: Pair,
        amount: float,
        user_name: str,
        limit_factor: float = 1,
        max_price: float = -1,
        orders_table: str = "kraken-dca",
    ) -> None:
        """
        Initialize the DCA object.

        :param ka: KrakenApi object.
        :param delay: DCA days delay between buy orders.
        :param pair: Pair to dollar cost average as string.
        :param amount: Amount to dollar cost average as float.
        :param user_name: User name of account in Kraken platform.
        :param limit_factor: Price limit factor as float.
        :param max_price: Maximum price as float.
        :param orders_table: Orders save file path as String.
        """
        self.ka = ka
        self.delay = delay
        self.pair = pair
        self.amount = float(amount)
        self.user_name = user_name
        self.limit_factor = float(limit_factor)
        self.max_price = float(max_price)
        self.orders_table = orders_table

    def __str__(self) -> str:
        desc: str = (
            f"Pair {self.pair.name}: delay: {self.delay}, amount: {self.amount}"
        )
        if self.limit_factor != 1:
            desc += f", limit_factor: {self.limit_factor}"
        if self.max_price != -1:
            desc += f", max_price: {self.max_price}"
        return desc

    def handle_dca_logic(self) -> None:
        """
        Handle DCA logic.

        :return: None
        """
        # Check current system time.
        current_date = self.get_system_time()
        # Check Kraken account balance.
        self.check_account_balance()
        # Check if didn't already DCA today
        if self.count_pair_daily_orders() != 0:
            print(f"No DCA for {self.pair.name}: Already placed an order today.")
            return
        print("Didn't DCA already today.")
        # Get current pair ask price.
        pair_ask_price = self.pair.get_pair_ask_price(self.ka, self.pair.name)
        print(f"Current {self.pair.name} ask price: {pair_ask_price}.")
        # Get limit price based on limit_factor
        limit_price = self.get_limit_price(pair_ask_price, self.pair.pair_decimals)
        # Reject DCA if limit_price greater than max_price
        if self.max_price != -1 and limit_price > self.max_price:
            print(
                f"No DCA for {self.pair.name}: Limit price ({limit_price}) "
                f"greater than maximum price ({self.max_price})."
            )
            return
        # Create the Order object.
        order = Order.buy_limit_order(
            self.user_name,
            current_date,
            self.pair.name,
            self.amount,
            limit_price,
            self.pair.lot_decimals,
            self.pair.quote_decimals,
        )
        # Send buy order to Kraken API and print information.
        self.send_buy_limit_order(order)
        # Save order information to Dynamo DB.
        order.save_order_dynamo(self.orders_table)
        print("Order information saved to Dynamo DB.")

    def get_limit_price(self, pair_ask_price: float, pair_decimals: int) -> float:
        """
        Calculates wanted limit price from current ask price and limit_factor.

        :param pair_ask_price: Pair ask price to adjust limit price from.
        :param pair_decimals: Pair maximum number of decimals for price.
        :return: The limit price
        """
        if round(self.limit_factor, 5) == 1.0:
            limit_price = pair_ask_price
        else:
            limit_price = round(pair_ask_price * self.limit_factor, pair_decimals)
            print(
                f"Factor adjusted limit price ({self.limit_factor:.4f})"
                f": {limit_price}."
            )
        return limit_price

    def get_system_time(self) -> datetime:
        """
        Compare system and Kraken time.
        Raise an error if too much difference (> 2sc).

        :return: datetime object of current system time
        """
        kraken_time: int = self.ka.get_time()
        kraken_date: datetime = utc_unix_time_datetime(kraken_time)
        current_date: datetime = current_utc_datetime()
        print(f"It's {kraken_date} on Kraken, {current_date} on system.")
        lag_in_seconds: float = (current_date - kraken_date).seconds
        if lag_in_seconds > 2:
            raise OSError(
                "Too much lag -> Check your internet connection speed "
                "or synchronize your system time."
            )
        return current_date

    def check_account_balance(self) -> None:
        """
        Check account trade balance, pair base and pair quote balances.
        Raise an error if quote pair balance
        is too low to DCA specified amount.

        :return: None
        """
        trade_balance = self.ka.get_trade_balance().get("eb")
        print(f"Current trade balance: {trade_balance} ZUSD.")
        balance = self.ka.get_balance()
        try:
            pair_base_balance = float(balance.get(self.pair.base))
        # No pair base balance on Kraken account.
        except TypeError:
            pair_base_balance = 0
        try:
            pair_quote_balance = float(balance.get(self.pair.quote))
        # No pair quote balance on Kraken account.
        except TypeError:
            pair_quote_balance = 0
        print(
            f"Pair balances: {pair_quote_balance} {self.pair.quote}, "
            f"{pair_base_balance} {self.pair.base}."
        )
        if pair_quote_balance < self.amount:
            raise ValueError(
                f"Insufficient funds to buy {self.amount} "
                f"{self.pair.quote} of {self.pair.base}"
            )

    def count_pair_daily_orders(self) -> int:
        """
        Count current day open and closed orders for the DCA pair.

        :return: Count of daily orders for the dollar cost averaged pair.
        """
        # Get current open orders.
        open_orders = self.ka.get_open_orders()
        daily_open_orders = len(
            self.extract_pair_orders(open_orders, self.pair.name, self.pair.alt_name)
        )

        # Get daily closed orders.
        start_day_datetime = current_utc_day_datetime() - timedelta(days=self.delay - 1)
        start_day_unix = datetime_as_utc_unix(start_day_datetime)
        closed_orders = self.ka.get_closed_orders(
            {"start": start_day_unix, "closetime": "open"}
        )
        daily_closed_orders = len(
            self.extract_pair_orders(closed_orders, self.pair.name, self.pair.alt_name)
        )
        # Sum the count of closed and daily open orders for the DCA pair.
        pair_daily_orders = daily_closed_orders + daily_open_orders
        return pair_daily_orders

    @staticmethod
    def extract_pair_orders(orders: dict, pair: str, pair_alt_name: str) -> dict:
        """
        Filter orders passed as dictionary on specific
        pair and return the nested dictionary.

        :param orders: Orders as dictionary.
        :param pair: Specific pair to filter on.
        :param pair_alt_name: Specific pair alternative name to filter on.
        :return: Filtered orders dictionary on specific pair.
        """
        pair_orders = {
            order_id: order_infos
            for order_id, order_infos in orders.items()
            if order_infos.get("descr").get("pair") == pair
            or order_infos.get("descr").get("pair") == pair_alt_name
        }
        return pair_orders

    def send_buy_limit_order(self, order: Order) -> None:
        """
        Send a limit order for specified dca pair and amount to Kraken.

        :return: None.
        """
        if order.volume < self.pair.order_min:
            raise ValueError(
                f"Too low volume to buy {self.pair.base}: "
                f"current {order.volume}, "
                f"minimum {self.pair.order_min}."
            )
        print(
            f"Create a {order.price}{self.pair.quote} buy limit order of "
            f"{order.volume}{self.pair.base} at "
            f"{order.pair_price}{self.pair.quote}."
        )
        print(f"Fee expected: {order.fee}{self.pair.quote} (0.26% taker fee).")
        print(
            f"Total price expected: {order.volume}{self.pair.base} for "
            f"{order.total_price}{self.pair.quote}."
        )
        order.send_order(self.ka)
        print("Order successfully created.")
        print(f"TXID: {order.txid}")
        print(f"Description: {order.description}")
