import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = Path(
    r"C:\Users\run_r\AppData\Local\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\development_behavior_packs\bunken-word-addin\manifest\manifest.production.xml.template"
)
OUTPUT_PATH = ROOT / "manifest.production.xml"


def main() -> None:
    base_url = os.getenv("BUNKEN_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL is required")
    if not base_url.startswith("https://"):
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL must start with https://")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    manifest = template.replace("__BASE_URL__", base_url)
    OUTPUT_PATH.write_text(manifest, encoding="utf-8")
    print(f"generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
