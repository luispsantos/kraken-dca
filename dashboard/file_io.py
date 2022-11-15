import json
import os
import time

import pandas as pd


def persist_to_file(file_name: str, ttl: int = 10 * 60):
    """Decorator to persist return type of function to a file.

    Only performs operation if the file does not exist or the TTL has expired.
    """

    def decorator(function):
        def wrapper(*args, **kwargs):
            cache_valid = True
            try:
                modification_time = os.path.getmtime(file_name)
                if time.time() - modification_time > ttl:
                    cache_valid = False

                if cache_valid:
                    with open(file_name, "r") as cache_file:
                        if file_name.endswith(".json"):
                            return json.load(cache_file)
                        elif file_name.endswith(".csv"):
                            return pd.read_csv(file_name)
                        else:
                            raise ValueError(f"Unprocessable file {file_name}")
            except (FileNotFoundError, IOError, ValueError):
                pass

            result = function(*args, **kwargs)
            with open(file_name, "w") as cache_file:
                if file_name.endswith(".json"):
                    json.dump(result, cache_file)
                elif file_name.endswith(".csv"):
                    result.to_csv(file_name, index=False)
            return result

        return wrapper

    return decorator
