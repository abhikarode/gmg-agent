"""Refresh the local AlmaShines snapshot used by the assistant."""

import os

from dotenv import load_dotenv

from almashines_extractor import AlmaShinesExtractor


def main() -> None:
    load_dotenv(".env.local")
    load_dotenv(".env")
    key = os.getenv("ALMASHINES_API_KEY")
    secret = os.getenv("ALMASHINES_API_SECRET")
    if not key or not secret:
        raise SystemExit("Missing ALMASHINES_API_KEY or ALMASHINES_API_SECRET")

    extractor = AlmaShinesExtractor(key, secret)
    data = extractor.extract_all(form_ids=None)
    extractor.save_to_file("almashines_data.json")
    print("Refreshed snapshot:", {name: len(value) for name, value in data.items()})


if __name__ == "__main__":
    main()
