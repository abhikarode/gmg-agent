"""Build the source ZIP for an Azure Functions Flex remote build."""

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


FLEX = Path(__file__).resolve().parent
ROOT = FLEX.parents[2]
FLEX_FILES = (
    "function_app.py",
    "host.json",
    "requirements.txt",
    "desk.css",
    "desk-tools.js",
    "desk_tools.py",
    "member_desk.py",
    "templates/desk.html",
    "templates/tools.html",
)
SHARED_FILES = (
    "ai_agent.py",
    "azure_storage.py",
    "directory_snapshot.py",
    "expertise.py",
    "expertise_catalog.json",
    "hosted_inference.py",
    "inference_budget.py",
    "member_enrichment.py",
    "membership.py",
    "people_match.py",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Path for the source ZIP")
    output = parser.parse_args().output
    sources = {name: FLEX / name for name in FLEX_FILES}
    sources.update({name: ROOT / name for name in SHARED_FILES})
    files = {name: source.read_bytes() for name, source in sources.items()}
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            entry = ZipInfo(name)
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content, compress_type=ZIP_DEFLATED)
    print(f"Built {output} with {len(files)} source files.")


if __name__ == "__main__":
    main()
