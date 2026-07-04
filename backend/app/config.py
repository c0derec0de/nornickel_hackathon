from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "scigraph123"

    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # LLM провайдер: "ollama" (локальный, приватный), "openai" (OpenRouter и т.п.)
    #                или "anthropic"
    llm_provider: str = "ollama"
    llm_model: str = "qwen3:4b"

    # OpenAI-совместимый API (по умолчанию OpenRouter — разрешён в РФ)
    openai_base_url: str = "https://openrouter.ai/api/v1"
    openai_api_key: str = ""

    # Локальный Ollama (приватный fallback)
    ollama_host: str = "http://host.docker.internal:11434"

    anthropic_api_key: str = ""

    embed_model: str = "intfloat/multilingual-e5-large"

    # лимит чанков на документ при массовом ингесте (контроль времени)
    max_chunks_per_doc: int = 6

    corpus_dir: str = "data/corpus"
    chunk_size: int = 1400
    chunk_overlap: int = 200

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
