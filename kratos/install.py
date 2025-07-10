from sh import curl, sh  # pyright: ignore

# Install uv and ollama
try:
    from sh import uv, ollama  # pyright: ignore
except ImportError:
    sh(_in=curl("-LsSf", "https://astral.sh/uv/install.sh"))
    sh(_in=curl("-LsSf", "https://ollama.com/install.sh"))

from sh import uv, ollama  # pyright: ignore

uv.init()
uv.add("ollama")
uv.add("agno")