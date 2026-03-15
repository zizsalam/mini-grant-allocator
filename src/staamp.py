"""STAAMP credential isolation for agent API calls.

Instead of agents directly reading ANTHROPIC_API_KEY from the environment,
they go through this module which implements the STAAMP pattern:

1. Agent requests "I need Anthropic API access"
2. STAAMP resolves the credential (via HLOS vault, hlos run injection, or env)
3. Agent gets a configured client — never sees the raw key
4. Access is logged in the HLOS audit trail

This ensures the Anthropic API key never appears in agent code, prompts,
or reasoning traces — matching HLOS's zero-value-exposure model.
"""

from __future__ import annotations

from typing import Optional

_cached_client = None


def get_anthropic_client(wallet=None):
    """Get an Anthropic client via STAAMP credential isolation.

    Resolution order:
    1. If wallet is provided and not mock, use HLOS credential lookup
    2. Fall back to anthropic.Anthropic() which reads ANTHROPIC_API_KEY from env
       (this works with both `hlos run` injection and direct env vars)

    The key insight: even in fallback mode, if you're running under
    `hlos run -- python -m src.main`, the API key was injected by HLOS
    and never touched your .env file — STAAMP is still satisfied.
    """
    global _cached_client

    if _cached_client is not None:
        return _cached_client

    import anthropic

    api_key = None

    # Try HLOS credential retrieval if wallet is available
    if wallet and not wallet._mock:
        api_key = wallet.get_credential("ANTHROPIC_API_KEY")

    if api_key:
        _cached_client = anthropic.Anthropic(api_key=api_key)
    else:
        # Falls back to ANTHROPIC_API_KEY env var
        # Under `hlos run`, this was injected by HLOS — still zero-exposure
        _cached_client = anthropic.Anthropic()

    return _cached_client


def reset_client():
    """Reset the cached client (useful for testing)."""
    global _cached_client
    _cached_client = None
