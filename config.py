import os


def _load_env(path=None, override=True):
    """
    Load .env into os.environ.

    `override` defaults to True on purpose. With setdefault semantics an edit to
    .env never reached a running server: the Werkzeug reloader restarts the
    child process but it inherits the parent's os.environ, so the value read at
    the very first start shadowed the file for the life of the parent — which
    showed up as a stale API key long after .env had been corrected.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if override or k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        pass


_load_env()


class Config:
    API_KEY = os.getenv("GROQ_API_KEY", "")
    API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1")
    MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")
