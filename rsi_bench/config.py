"""
Configuration and provider defaults for RSI-Bench.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ProviderMetadata:
    """Metadata and defaults for an LLM provider."""
    name: str
    display_name: str
    default_model: str
    default_base_url: str
    env_key_names: List[str]
    supports_thinking: bool = True
    supports_prompt_caching: bool = True
    doc_url: str = ""


PROVIDER_REGISTRY: Dict[str, ProviderMetadata] = {
    "anthropic": ProviderMetadata(
        name="anthropic",
        display_name="Anthropic (Messages API)",
        default_model="claude-3-7-sonnet-20250219",
        default_base_url="https://api.anthropic.com/v1",
        env_key_names=["ANTHROPIC_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://docs.anthropic.com/en/api/messages",
    ),
    "gemini": ProviderMetadata(
        name="gemini",
        display_name="Google Gemini (Interactions & Content API)",
        default_model="gemini-2.5-flash",
        default_base_url="https://generativelanguage.googleapis.com/v1beta",
        env_key_names=["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://ai.google.dev/api/rest",
    ),
    "openai_chat": ProviderMetadata(
        name="openai_chat",
        display_name="OpenAI (Chat Completions Route)",
        default_model="gpt-4o",
        default_base_url="https://api.openai.com/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://platform.openai.com/docs/api-reference/chat",
    ),
    "openai_responses": ProviderMetadata(
        name="openai_responses",
        display_name="OpenAI (Responses API)",
        default_model="gpt-4o",
        default_base_url="https://api.openai.com/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://platform.openai.com/docs/api-reference/responses",
    ),
    "deepseek": ProviderMetadata(
        name="deepseek",
        display_name="DeepSeek",
        default_model="deepseek-reasoner",
        default_base_url="https://api.deepseek.com",
        env_key_names=["DEEPSEEK_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://api-docs.deepseek.com/",
    ),
    "openrouter": ProviderMetadata(
        name="openrouter",
        display_name="OpenRouter",
        default_model="deepseek/deepseek-r1",
        default_base_url="https://openrouter.ai/api/v1",
        env_key_names=["OPENROUTER_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=True,
        doc_url="https://openrouter.ai/docs",
    ),
    "groq": ProviderMetadata(
        name="groq",
        display_name="Groq",
        default_model="deepseek-r1-distill-llama-70b",
        default_base_url="https://api.groq.com/openai/v1",
        env_key_names=["GROQ_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="https://console.groq.com/docs",
    ),
    "mistral": ProviderMetadata(
        name="mistral",
        display_name="Mistral AI",
        default_model="mistral-large-latest",
        default_base_url="https://api.mistral.ai/v1",
        env_key_names=["MISTRAL_API_KEY"],
        supports_thinking=False,
        supports_prompt_caching=False,
        doc_url="https://docs.mistral.ai/",
    ),
    "together": ProviderMetadata(
        name="together",
        display_name="Together AI",
        default_model="deepseek-ai/DeepSeek-R1",
        default_base_url="https://api.together.xyz/v1",
        env_key_names=["TOGETHER_API_KEY", "TOGETHERAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="https://docs.together.ai/",
    ),
    "cohere": ProviderMetadata(
        name="cohere",
        display_name="Cohere (V2 Chat)",
        default_model="command-r-plus-08-2024",
        default_base_url="https://api.cohere.com/v2",
        env_key_names=["COHERE_API_KEY", "CO_API_KEY"],
        supports_thinking=False,
        supports_prompt_caching=False,
        doc_url="https://docs.cohere.com/reference/chat",
    ),
    "generic_openai": ProviderMetadata(
        name="generic_openai",
        display_name="Generic OpenAI-Compatible (Ollama, vLLM, LMStudio, etc.)",
        default_model="default",
        default_base_url="http://localhost:11434/v1",
        env_key_names=["OPENAI_API_KEY"],
        supports_thinking=True,
        supports_prompt_caching=False,
        doc_url="",
    ),
}


def get_api_key_for_provider(provider_name: str, explicit_key: Optional[str] = None) -> Optional[str]:
    """Retrieve the API key for a provider from explicit argument or environment variables."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    meta = PROVIDER_REGISTRY.get(provider_name.lower())
    if not meta:
        return os.environ.get(f"{provider_name.upper()}_API_KEY")

    for env_name in meta.env_key_names:
        key = os.environ.get(env_name)
        if key and key.strip():
            return key.strip()

    return None


def get_available_configured_providers() -> List[str]:
    """Return list of provider names that currently have API keys set in the environment."""
    configured: List[str] = []
    for name, meta in PROVIDER_REGISTRY.items():
        if name == "generic_openai":
            continue  # local generic doesn't necessarily need a real key
        for env_name in meta.env_key_names:
            if os.environ.get(env_name):
                configured.append(name)
                break
    return configured
