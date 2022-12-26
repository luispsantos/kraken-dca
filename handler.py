from pathlib import Path

import sentry_sdk
from krakenapi import KrakenApi

from krakendca.config import Config
from krakendca.krakendca import KrakenDCA


def setup_sentry(dsn_file="sentry_dsn.txt"):
    sentry_dsn = Path(dsn_file).read_text()
    sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=1.0)


def main():
    curr_directory = Path(__file__).resolve().parent

    # Iterate over the multiple configuration files
    for config_file in sorted(curr_directory.glob("config*.yaml")):
        # Read parameters from configuration file
        config = Config(config_file)

        # Skip non-initialized config files
        if config.api_user_name == "KRAKEN_USER_NAME":
            continue

        # Initialize the KrakenAPI object
        ka = KrakenApi(config.api_public_key, config.api_private_key)

        # Initialize KrakenDCA and handle the DCA based on configuration
        kdca = KrakenDCA(config, ka)
        kdca.initialize_pairs_dca()
        kdca.handle_pairs_dca()


def run(event, context):
    setup_sentry()
    main()


if __name__ == "__main__":
    main()
