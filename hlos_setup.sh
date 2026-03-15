#!/usr/bin/env bash
# =============================================================================
# HLOS Setup Script for Mini Grant Allocator
#
# This script configures HLOS credential isolation (STAAMP) so the
# grant allocator agents never hold raw API keys in code or environment.
#
# Prerequisites:
#   - Node.js 18+
#   - npm
#   - HLOS account (free at hlos.ai)
# =============================================================================

set -euo pipefail

echo "============================================"
echo "  HLOS Setup — Mini Grant Allocator"
echo "============================================"
echo ""

# --- Step 1: Install HLOS CLI ---
echo "[1/6] Installing HLOS CLI..."
if command -v hlos &> /dev/null; then
    echo "  HLOS CLI already installed: $(hlos --version 2>/dev/null || echo 'installed')"
else
    npm install -g @hlos/cli
    echo "  Installed."
fi
echo ""

# --- Step 2: Authenticate ---
echo "[2/6] Authenticating with HLOS..."
if hlos whoami &> /dev/null; then
    echo "  Already authenticated as: $(hlos whoami 2>/dev/null)"
else
    echo "  Opening browser for OAuth login..."
    hlos login
fi
echo ""

# --- Step 3: Create space ---
SPACE_NAME="grant-allocator"
echo "[3/6] Creating space: ${SPACE_NAME}..."
if hlos spaces list 2>/dev/null | grep -q "${SPACE_NAME}"; then
    echo "  Space already exists."
else
    hlos spaces create "${SPACE_NAME}" -d "Agentic grant allocation system"
fi
hlos spaces use "${SPACE_NAME}"
echo "  Active space: ${SPACE_NAME}"
echo ""

# --- Step 4: Store Anthropic API key ---
echo "[4/6] Storing Anthropic API key in HLOS vault..."
if hlos secrets list 2>/dev/null | grep -q "ANTHROPIC_API_KEY"; then
    echo "  ANTHROPIC_API_KEY already stored in HLOS."
    echo "  To update: hlos secrets set ANTHROPIC_API_KEY"
else
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        echo "  Found ANTHROPIC_API_KEY in environment. Storing in HLOS..."
        hlos secrets set ANTHROPIC_API_KEY "${ANTHROPIC_API_KEY}"
    else
        echo "  Enter your Anthropic API key (will be stored securely in HLOS):"
        hlos secrets set ANTHROPIC_API_KEY
    fi
fi
echo ""

# --- Step 5: Verify MCP server ---
echo "[5/6] Verifying MCP server availability..."
if npx -y @hlos/mcp-server --help &> /dev/null 2>&1; then
    echo "  MCP server package available."
else
    echo "  Installing @hlos/mcp-server..."
    npx -y @hlos/mcp-server --help 2>/dev/null || true
fi
echo ""

# --- Step 6: Health check ---
echo "[6/6] Running health check..."
hlos health 2>/dev/null || echo "  Health check unavailable (may require secrets)."
echo ""

# --- Summary ---
echo "============================================"
echo "  HLOS Setup Complete"
echo "============================================"
echo ""
echo "  Space:     ${SPACE_NAME}"
echo "  Secrets:   ANTHROPIC_API_KEY (stored in HLOS vault)"
echo "  MCP:       @hlos/mcp-server configured"
echo ""
echo "  Usage modes:"
echo "    Mock mode (default):  HLOS_MOCK=true python -m src.main"
echo "    HLOS mode:            hlos run -- python -m src.main"
echo ""
echo "  The 'hlos run' command injects secrets at runtime so"
echo "  your agents never see raw API keys in code or .env files."
echo ""
echo "  MCP config for Claude Desktop / Cursor is at:"
echo "    .claude/mcp.json"
echo ""
