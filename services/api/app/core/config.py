from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only relevant before dependencies install.
    load_dotenv = None

if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "Cregis ETH AML Tracing"
    api_v1_prefix: str = "/api/v1"
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    etherscan_api_key: str = ""
    etherscan_base_url: str = "https://api.etherscan.io/v2/api"
    goplus_token: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    chain_id: str = "1"
    demo_mode: bool = True
    max_stable_nodes: int = 75
    max_experimental_nodes: int = 160


def get_settings() -> Settings:
    cors = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    demo_mode = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"}
    return Settings(
        cors_origins=tuple(origin.strip() for origin in cors.split(",") if origin.strip()),
        etherscan_api_key=os.getenv("ETHERSCAN_API_KEY", ""),
        etherscan_base_url=os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api"),
        goplus_token=os.getenv("GOPLUS_TOKEN", ""),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
        chain_id=os.getenv("CHAIN_ID", "1"),
        demo_mode=demo_mode,
        max_stable_nodes=int(os.getenv("MAX_STABLE_NODES", "75")),
        max_experimental_nodes=int(os.getenv("MAX_EXPERIMENTAL_NODES", "160")),
    )
