"""pair.py tests module."""
import pytest
import vcr
from krakenapi import KrakenApi
from krakendca.pair import Pair


class TestPair:
    pair: Pair
    ka: KrakenApi

    def setup(self) -> None:
        self.pair = Pair("XETHZEUR", "ETHEUR", "XETH", "ZEUR", 2, 8, 4, 0.005)
        self.ka = KrakenApi("api_public_key", "api_private_key")

    @staticmethod
    def assert_xethzeur_pair(pair: Pair) -> None:
        assert type(pair.name) == str
        assert pair.name == "XETHZEUR"
        assert type(pair.alt_name) == str
        assert pair.alt_name == "ETHEUR"
        assert type(pair.base) == str
        assert pair.base == "XETH"
        assert type(pair.quote) == str
        assert pair.quote == "ZEUR"
        assert type(pair.pair_decimals) == int
        assert pair.pair_decimals == 2
        assert type(pair.lot_decimals) == int
        assert pair.lot_decimals == 8
        assert type(pair.quote_decimals) == int
        assert pair.quote_decimals == 4
        assert type(pair.order_min) == float
        assert pair.order_min == 0.005

    def test_init(self) -> None:
        self.assert_xethzeur_pair(self.pair)

    @vcr.use_cassette(
        "tests/fixtures/vcr_cassettes/test_get_pair_from_kraken.yaml"
    )
    def test_get_pair_from_kraken(self) -> None:
        asset_pairs = self.ka.get_asset_pairs()
        pair = Pair.get_pair_from_kraken(self.ka, asset_pairs, "XETHZEUR")
        self.assert_xethzeur_pair(pair)

    def test_get_pair_information(self) -> None:
        # Test with existing pair.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_asset_pairs.yaml"
        ):
            asset_pairs = self.ka.get_asset_pairs()
        pair_information = Pair.get_pair_information(asset_pairs, "XETHZEUR")
        test_pair_information = {
            "altname": "ETHEUR",
            "wsname": "ETH/EUR",
            "aclass_base": "currency",
            "base": "XETH",
            "aclass_quote": "currency",
            "quote": "ZEUR",
            "lot": "unit",
            "pair_decimals": 2,
            "lot_decimals": 8,
            "lot_multiplier": 1,
            "leverage_buy": [2, 3, 4, 5],
            "leverage_sell": [2, 3, 4, 5],
            "fees": [
                [0, 0.26],
                [50000, 0.24],
                [100000, 0.22],
                [250000, 0.2],
                [500000, 0.18],
                [1000000, 0.16],
                [2500000, 0.14],
                [5000000, 0.12],
                [10000000, 0.1],
            ],
            "fees_maker": [
                [0, 0.16],
                [50000, 0.14],
                [100000, 0.12],
                [250000, 0.1],
                [500000, 0.08],
                [1000000, 0.06],
                [2500000, 0.04],
                [5000000, 0.02],
                [10000000, 0],
            ],
            "fee_volume_currency": "ZUSD",
            "margin_call": 80,
            "margin_stop": 40,
            "ordermin": "0.005",
        }
        assert type(pair_information) == dict
        assert pair_information == test_pair_information

        # Test with fake pair.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_asset_pairs.yaml"
        ):
            asset_pairs = self.ka.get_asset_pairs()
        with pytest.raises(ValueError) as e_info:
            Pair.get_pair_information(asset_pairs, "Fake")
        error_message = "Fake pair not available on Kraken. Available pairs:"
        assert error_message in str(e_info.value)

    def test_get_asset_information(self) -> None:
        # Test with existing asset.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_assets.yaml"
        ):
            asset = Pair.get_asset_information(self.ka, "XETH")
        test_asset = {
            "aclass": "currency",
            "altname": "ETH",
            "decimals": 10,
            "display_decimals": 5,
        }
        assert type(asset) == dict
        assert asset == test_asset

        # Test with fake asset.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_assets.yaml"
        ):
            with pytest.raises(ValueError) as e_info:
                Pair.get_asset_information(self.ka, "Fake")
        error_message = "Fake asset not available on Kraken. Available assets:"
        assert error_message in str(e_info.value)

    def test_get_ask_price(self) -> None:
        # Test with existing pair.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_pair_ticker.yaml"
        ):
            pair_ask_price = Pair.get_pair_ask_price(self.ka, "XETHZEUR")
        assert type(pair_ask_price) == float
        assert pair_ask_price == 1749.76

        # Test with fake pair.
        with vcr.use_cassette(
            "tests/fixtures/vcr_cassettes/test_get_pair_ticker_error.yaml"
        ):
            with pytest.raises(ValueError) as e_info:
                Pair.get_pair_ask_price(self.ka, "XETHZEUR")
        error_message = "Kraken API error -> EQuery:Unknown asset pair"
        assert error_message in str(e_info.value)
