"""Read data snapshots from supplied exercise files; shape adapters for pure services."""

import json
from pathlib import Path
from app.services.taxes import TaxCatalog

DATA_DIR = (
    Path(__file__).resolve().parents[2] / "exercise-pack" / "starter-kit" / "data"
)


# Read a supplied exercise fixture without mutating its source file.
def load_json(filename: str, data_dir: Path = DATA_DIR):
    "Read a supplied exercise fixture without mutating its source file."
    with (data_dir / filename).open(encoding="utf-8") as handle:
        return json.load(handle)


# Build effective-dated HSN tax lookup from the supplied configuration.
def tax_catalog(data_dir: Path = DATA_DIR) -> TaxCatalog:
    "Build effective-dated HSN tax lookup from the supplied configuration."
    return TaxCatalog(load_json("tax_rates.json", data_dir)["rates"])


# Find lens and tax metadata for a source catalog variant.
def variant_metadata(variant_id: str, data_dir: Path = DATA_DIR) -> dict:
    "Find lens and tax metadata for a source catalog variant."
    for product in load_json("products.json", data_dir):
        for variant in product["variants"]:
            if str(variant["id"]) == str(variant_id):
                return variant["eluno"]
    raise KeyError(f"Variant not found: {variant_id}")
