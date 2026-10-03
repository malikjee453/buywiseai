import os
from functools import lru_cache
from typing import Optional
from dotenv import load_dotenv
from groq import Groq
load_dotenv()
DEFAULT_MODEL = "openai/gpt-oss-120b"

class LLMConfigurationError(RuntimeError):
    pass

@lru_cache(maxsize=1)
def get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise LLMConfigurationError("GROQ_API_KEY is not configured.")
    return Groq(api_key=api_key)

def get_llm(model: Optional[str] = None, temperature: Optional[float] = None) -> Groq:
    return get_groq_client()

def chat_completion(messages: list[dict[str, str]], *, model: Optional[str] = None,
                    temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
    client = get_groq_client()
    response = client.chat.completions.create(
        model=model or os.getenv("BUYWISE_MODEL", DEFAULT_MODEL),
        messages=messages,
        temperature=float(temperature if temperature is not None else os.getenv("BUYWISE_TEMPERATURE", "0.2")),
        max_tokens=int(max_tokens if max_tokens is not None else os.getenv("BUYWISE_MAX_TOKENS", "1200")),
    )
    return response.choices[0].message.content or ""
