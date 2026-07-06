from dataclasses import dataclass, field
from pathlib import Path


ASSISTANT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = ASSISTANT_DIR.parent


@dataclass(frozen=True)
class AppConfig:
    project_path: Path = PROJECT_ROOT
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    default_chat_model: str = "qwen2.5-coder:14b"
    default_architect_model: str = "qwen2.5:7b"
    ollama_base_url: str = "http://localhost:11434"
    api_host: str = "127.0.0.1"
    api_port: int = 8008
    top_k: int = 5
    ollama_timeout_seconds: int = 600
    max_context_chars: int = 7000
    cache_path: Path = field(default_factory=lambda: ASSISTANT_DIR / "index_cache.pkl")
    index_path: Path = field(default_factory=lambda: ASSISTANT_DIR / "index.faiss")
    metadata_path: Path = field(default_factory=lambda: ASSISTANT_DIR / "meta.pkl")
    graph_path: Path = field(default_factory=lambda: ASSISTANT_DIR / "knowledge_graph.json")
    batch_size: int = 64
    chunk_size: int = 1000
    chunk_overlap: int = 150
    banned_dirs: tuple[str, ...] = (".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv")
    allowed_extensions: tuple[str, ...] = (".ts", ".js", ".jsx", ".tsx", ".py", ".sql", ".json", ".md", ".yml", ".yaml", ".env", "dockerfile", ".sh")

    @property
    def llm_model(self) -> str:
        return self.default_chat_model

    @property
    def ollama_url(self) -> str:
        return self.ollama_base_url


DEFAULT_CONFIG = AppConfig()

PROJECT_PATH = str(DEFAULT_CONFIG.project_path)
EMBEDDING_MODEL = DEFAULT_CONFIG.embedding_model
LLM_MODEL = DEFAULT_CONFIG.llm_model
OLLAMA_BASE_URL = DEFAULT_CONFIG.ollama_base_url
DEFAULT_CHAT_MODEL = DEFAULT_CONFIG.default_chat_model
DEFAULT_ARCHITECT_MODEL = DEFAULT_CONFIG.default_architect_model
API_HOST = DEFAULT_CONFIG.api_host
API_PORT = DEFAULT_CONFIG.api_port
TOP_K = DEFAULT_CONFIG.top_k

