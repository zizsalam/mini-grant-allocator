"""HLOS Setup Verification Script.

Runs through the PRD's Appendix checklist to verify everything is configured:
1. HLOS CLI installed
2. HLOS_API_KEY set (never hardcoded)
3. MCP server config exists
4. hlos.get_balance returns correctly
5. Test notarize() call returns receipt hash
6. Wallet balance decrements after notarize
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from dotenv import load_dotenv

load_dotenv()

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

results = []


def check(name: str, passed: bool, detail: str = "") -> None:
    status = PASS if passed else FAIL
    results.append(passed)
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def warn(name: str, detail: str = "") -> None:
    msg = f"  [{WARN}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def main() -> None:
    print()
    print("=" * 55)
    print("  HLOS Setup Verification (PRD Appendix Checklist)")
    print("=" * 55)
    print()

    # --- 1. HLOS CLI installed ---
    try:
        result = subprocess.run(
            ["hlos", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        check("HLOS CLI installed", True, f"v{version}")
    except FileNotFoundError:
        check("HLOS CLI installed", False, "Run: npm install -g @hlos/cli")
    except Exception as e:
        check("HLOS CLI installed", False, str(e))

    # --- 2. HLOS_API_KEY set (not hardcoded) ---
    api_key = os.getenv("HLOS_API_KEY")
    if api_key:
        check("HLOS_API_KEY environment variable set", True, f"{api_key[:8]}...")
    else:
        warn("HLOS_API_KEY not set", "Optional: needed for live HLOS mode")

    # Check no raw API keys are hardcoded in source files
    hardcoded_files = []
    for root, dirs, files in os.walk("src"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path) as fh:
                    for i, line in enumerate(fh, 1):
                        # Only flag actual key values, not os.getenv() references
                        if "sk-ant-" in line or "sk-proj-" in line:
                            hardcoded_files.append(f"{path}:{i}")
    if not hardcoded_files:
        check("No hardcoded API keys in source", True)
    else:
        check("No hardcoded API keys in source", False,
              f"Found in: {', '.join(hardcoded_files)}")

    # --- 3. ANTHROPIC_API_KEY set ---
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        check("ANTHROPIC_API_KEY set", True, f"{anthropic_key[:12]}...")
    else:
        warn("ANTHROPIC_API_KEY not set", "Agents will use mock mode")

    # --- 4. MCP server config ---
    mcp_path = ".claude/mcp.json"
    if os.path.exists(mcp_path):
        with open(mcp_path) as f:
            mcp_config = json.load(f)
        has_hlos = "hlos" in mcp_config.get("mcpServers", {})
        check("MCP server config exists", True, mcp_path)
        check("HLOS MCP server configured", has_hlos,
              "@hlos/mcp-server" if has_hlos else "Missing hlos entry")
    else:
        check("MCP server config exists", False, f"{mcp_path} not found")

    # --- 5. hlos.get_balance returns correctly ---
    print()
    print("  --- Wallet Operations Test ---")
    from src.hlos import HLOSWallet

    wallet = HLOSWallet.connect()
    balance = wallet.get_balance()
    check("get_balance() returns correctly", balance > 0,
          f"${balance:,.2f} ({wallet.mode_label})")

    # --- 6. Test notarize() call ---
    initial_balance = wallet.get_balance()
    try:
        receipt = wallet.notarize("TEST-001", 100.00)
        check("notarize() returns receipt hash", bool(receipt.receipt_hash),
              receipt.receipt_hash)

        # --- 7. Balance decrements ---
        new_balance = wallet.get_balance()
        decremented = new_balance == initial_balance - 100.00
        check("Balance decrements after notarize",
              decremented,
              f"${initial_balance:,.2f} -> ${new_balance:,.2f}")
    except Exception as e:
        check("notarize() returns receipt hash", False, str(e))
        check("Balance decrements after notarize", False, "notarize failed")

    # --- 8. Audit log populated ---
    audit = wallet.audit_log
    check("HLOS audit log populated", len(audit) > 0,
          f"{len(audit)} entries")

    # --- Summary ---
    print()
    print("=" * 55)
    passed = sum(results)
    total = len(results)
    print(f"  Results: {passed}/{total} checks passed")
    if passed == total:
        print(f"  All checks passed — system is ready.")
    else:
        print(f"  {total - passed} check(s) need attention.")
    print("=" * 55)
    print()

    # Show HLOS audit log
    if audit:
        print("  HLOS Audit Log:")
        for entry in audit:
            print(f"    [{entry['result']:8s}] {entry['action']:16s} "
                  f"{entry['resource']:20s} {entry['details']}")
        print()


if __name__ == "__main__":
    main()
