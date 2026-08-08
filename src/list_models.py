"""Lists every model alias in the catalog (used to confirm the correct alias name)."""
import sys

from foundry_local_sdk import Configuration, FoundryLocalManager

sys.stdout.reconfigure(encoding="utf-8")

config = Configuration(app_name="foundry_rag_demo")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

for m in manager.catalog.list_models():
    print(m.alias if hasattr(m, "alias") else m)
