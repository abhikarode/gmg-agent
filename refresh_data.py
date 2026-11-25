"""Refresh the local AlmaShines snapshot used by the assistant."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import load_dotenv

from almashines_extractor import AlmaShinesExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--members-out", type=Path, help="Export only members to a private JSON file")
    args = parser.parse_args()
    load_dotenv(".env.local")
    load_dotenv(".env")
    key = os.getenv("ALMASHINES_API_KEY")
    secret = os.getenv("ALMASHINES_API_SECRET")
    if not key or not secret:
        raise SystemExit("Missing ALMASHINES_API_KEY or ALMASHINES_API_SECRET")

    extractor = AlmaShinesExtractor(key, secret)
    if args.members_out:
        users = extractor.extract_all_users()
        snapshot = {"source": "AlmaShines listUsers", "exported_at": datetime.now(timezone.utc).isoformat(), "users": users}
        output = args.members_out.expanduser()
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as file:
            temporary = Path(file.name)
            try:
                json.dump(snapshot, file, ensure_ascii=False)
                file.close()
                temporary.replace(output)
            finally:
                temporary.unlink(missing_ok=True)
        print(f"Exported {len(users)} members to {output}.")
        return
    data = extractor.extract_all(form_ids=None)
    extractor.save_to_file("almashines_data.json")
    print("Refreshed snapshot:", {name: len(value) for name, value in data.items()})


if __name__ == "__main__":
    main()
