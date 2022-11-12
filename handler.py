import time
from pathlib import Path

from krakenapi import KrakenApi

from krakendca.config import Config
from krakendca.krakendca import KrakenDCA


def main():
    curr_directory = Path(__file__).resolve().parent

    # Iterate over the multiple configuration files
    for config_file in sorted(curr_directory.glob("config*.yaml")):
        # Read parameters from configuration file
        config = Config(config_file)

        # Initialize the KrakenAPI object
        ka = KrakenApi(config.api_public_key, config.api_private_key)

        # Initialize KrakenDCA and handle the DCA based on configuration
        kdca = KrakenDCA(config, ka)
        kdca.initialize_pairs_dca()
        kdca.handle_pairs_dca()
        time.sleep(2)


def run(event, context):
    main()


if __name__ == "__main__":
    main()
