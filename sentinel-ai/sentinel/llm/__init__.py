"""
SENTINEL-AI LLM package.

Provides the Cerebras Cloud LLM client and centralised system prompts.
"""

from sentinel.llm.cerebras_client import get_client, CerebrasClient, MockCerebrasClient

__all__ = ["get_client", "CerebrasClient", "MockCerebrasClient"]
