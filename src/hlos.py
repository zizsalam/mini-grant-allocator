"""HLOS / STAAMP integration layer.

Architecture (mirrors HLOS security model):
- Agent = merchant terminal (makes decisions)
- HLOS = payment network (enforces constraints)
- Wallet balance = available credit line (hard limit)
- STAAMP = credential isolation (agent requests capabilities, never holds keys)

Integration modes:
1. HLOS_MOCK=true (default): Fully simulated for local dev. No external calls.
2. HLOS_MOCK=false + hlos run: HLOS injects secrets at runtime via env vars.
   Wallet is still local (HLOS wallet API not yet available).
3. HLOS_MOCK=false + HLOS_API_KEY: Direct API calls to HLOS secrets vault.
   Agent retrieves credentials on-demand via STAAMP pattern.

The system is architected so that when HLOS ships wallet/settlement endpoints,
only this file needs to change — the rest of the system is wallet-agnostic.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class HLOSError(Exception):
    """Raised when an HLOS operation fails."""


@dataclass
class HLOSReceipt:
    """Notarized receipt for a disbursement.

    In HLOS production, receipts are cryptographically signed by HLOS
    infrastructure and form the verifiable audit trail. Our local
    implementation generates SHA-256 hashes as a structural placeholder.
    """
    receipt_hash: str
    amount: float
    proposal_id: str
    timestamp: float
    balance_after: float = 0.0


@dataclass
class AuditEntry:
    """Mirrors HLOS audit log format (from `hlos audit`)."""
    action: str          # "get_balance", "notarize", "get_credential"
    resource: str        # proposal_id or secret_name
    result: str          # "success", "denied", "error"
    balance_before: float = 0.0
    balance_after: float = 0.0
    timestamp: str = ""
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "resource": self.resource,
            "result": self.result,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "timestamp": self.timestamp,
            "details": self.details,
        }


@dataclass
class HLOSWallet:
    """HLOS wallet + credential client.

    Implements the STAAMP pattern:
    - Agent decides (evaluator/skeptic/coordinator make scoring decisions)
    - Infrastructure enforces (wallet balance is a hard constraint)
    - Credentials never appear in agent code or logs
    """

    _balance: float = 0.0
    _mock: bool = True
    _receipts: list[HLOSReceipt] = field(default_factory=list)
    _audit_log: list[AuditEntry] = field(default_factory=list)
    _api_key: Optional[str] = None
    _base_url: str = "https://api.hlos.ai"
    _space: str = "grant-allocator"
    _hlos_managed: bool = False  # True when running under `hlos run`

    @classmethod
    def connect(cls) -> HLOSWallet:
        """Initialize wallet from environment configuration.

        Detection order:
        1. Check HLOS_MOCK=true → full mock mode
        2. Check if running under `hlos run` (HLOS_SPACE env var present)
        3. Check HLOS_API_KEY for direct API mode
        4. Fall back to mock mode
        """
        mock = os.getenv("HLOS_MOCK", "true").lower() == "true"
        balance = float(os.getenv("HLOS_INITIAL_BALANCE", "10000.00"))
        api_key = os.getenv("HLOS_API_KEY")
        hlos_space = os.getenv("HLOS_SPACE")

        if mock:
            return cls(_balance=balance, _mock=True)

        # Detect if running under `hlos run` — HLOS injects secrets as env vars
        hlos_managed = hlos_space is not None
        space = hlos_space or os.getenv("HLOS_SPACE_NAME", "grant-allocator")

        wallet = cls(
            _balance=balance,
            _mock=False,
            _api_key=api_key,
            _space=space,
            _hlos_managed=hlos_managed,
        )

        if hlos_managed:
            wallet._log_audit("connect", "wallet", "success",
                              details=f"Connected via hlos run (space: {space})")
        elif api_key:
            wallet._verify_connection()
            wallet._log_audit("connect", "wallet", "success",
                              details="Connected via direct API key")
        else:
            # No HLOS credentials — fall back to mock
            wallet._mock = True
            wallet._log_audit("connect", "wallet", "fallback",
                              details="No HLOS credentials found, using mock mode")

        return wallet

    def _verify_connection(self) -> None:
        """Verify HLOS API is reachable and credentials are valid."""
        try:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                f"{self._base_url}/v1/auth/me",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise HLOSError(
                    "HLOS authentication failed. Check your HLOS_API_KEY. "
                    "Generate one at: HLOS Dashboard > Settings > API Keys"
                )
        except Exception:
            pass  # HLOS unreachable — continue with local wallet

    def get_balance(self) -> float:
        """Return current wallet balance.

        Future: GET /v1/wallet/balance — HLOS balance is source of truth.
        If local and HLOS diverge, HLOS wins (per PRD).
        """
        self._log_audit("get_balance", "wallet", "success",
                        balance_before=self._balance,
                        balance_after=self._balance)
        return self._balance

    def notarize(
        self,
        proposal_id: str,
        amount: float,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ) -> HLOSReceipt:
        """Disburse funds and return a notarized receipt.

        Critical path — balance check MUST precede any notarize() call:
        1. Synchronous balance check
        2. Atomic deduction
        3. Receipt generation (SHA-256 hash)
        4. Audit log entry

        Retry with exponential backoff on failure.

        Future: POST /v1/wallet/notarize — receipt hash from HLOS infra.
        """
        balance = self._balance  # Direct read, no API call
        if amount > balance:
            self._log_audit("notarize", proposal_id, "denied",
                            balance_before=balance, balance_after=balance,
                            details=f"Insufficient: need ${amount:.2f}, have ${balance:.2f}")
            raise HLOSError(
                f"Insufficient balance: requested ${amount:.2f}, "
                f"available ${balance:.2f}"
            )
        if amount <= 0:
            raise HLOSError(f"Invalid disbursement amount: ${amount:.2f}")

        last_error = None
        for attempt in range(max_retries):
            try:
                receipt = self._execute_notarize(proposal_id, amount)
                self._log_audit("notarize", proposal_id, "success",
                                balance_before=balance,
                                balance_after=self._balance,
                                details=f"Disbursed ${amount:.2f}, receipt: {receipt.receipt_hash}")
                return receipt
            except HLOSError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = backoff_base * (2 ** attempt)
                    time.sleep(wait)

        self._log_audit("notarize", proposal_id, "error",
                        balance_before=balance, balance_after=self._balance,
                        details=f"Failed after {max_retries} retries: {last_error}")
        raise HLOSError(
            f"Notarize failed after {max_retries} retries. "
            f"Last error: {last_error}"
        )

    def _execute_notarize(self, proposal_id: str, amount: float) -> HLOSReceipt:
        """Execute the atomic notarization."""
        self._balance -= amount
        ts = time.time()

        # Cryptographic receipt — in production, HLOS signs this
        hash_input = json.dumps({
            "proposal_id": proposal_id,
            "amount": amount,
            "ts": ts,
            "balance_after": self._balance,
            "space": self._space,
        }, sort_keys=True)
        receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

        prefix = "mock" if self._mock else "hlos"
        receipt = HLOSReceipt(
            receipt_hash=f"{prefix}-{receipt_hash}",
            amount=amount,
            proposal_id=proposal_id,
            timestamp=ts,
            balance_after=self._balance,
        )
        self._receipts.append(receipt)
        return receipt

    def get_credential(self, secret_name: str) -> Optional[str]:
        """Retrieve a credential via STAAMP pattern.

        STAAMP flow:
        1. Agent requests capability by name (e.g., "ANTHROPIC_API_KEY")
        2. HLOS returns the credential value
        3. Agent uses it for one operation, never stores it
        4. Audit log records the access

        In `hlos run` mode: secrets are already in env vars (injected by CLI).
        In direct API mode: fetches from HLOS secrets vault.
        In mock mode: reads from local env vars.
        """
        # Under `hlos run`, secrets are injected as env vars
        if self._hlos_managed or self._mock:
            value = os.getenv(secret_name)
            self._log_audit("get_credential", secret_name,
                            "success" if value else "not_found",
                            details="via env" if self._hlos_managed else "via mock env")
            return value

        # Direct HLOS API call
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self._base_url}/v1/secrets/{secret_name}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "X-HLOS-Space": self._space,
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                self._log_audit("get_credential", secret_name, "success",
                                details="via HLOS API")
                return data.get("value")
        except Exception as e:
            # Fall back to env var
            value = os.getenv(secret_name)
            self._log_audit("get_credential", secret_name,
                            "fallback" if value else "error",
                            details=f"HLOS API failed ({e}), fell back to env")
            return value

    def _log_audit(self, action: str, resource: str, result: str, *,
                   balance_before: float = 0, balance_after: float = 0,
                   details: str = "") -> None:
        """Append to local audit log (mirrors `hlos audit` format)."""
        self._audit_log.append(AuditEntry(
            action=action,
            resource=resource,
            result=result,
            balance_before=balance_before,
            balance_after=balance_after,
            timestamp=datetime.utcnow().isoformat(),
            details=details,
        ))

    @property
    def receipts(self) -> list[HLOSReceipt]:
        return list(self._receipts)

    @property
    def audit_log(self) -> list[dict]:
        return [e.to_dict() for e in self._audit_log]

    @property
    def mode_label(self) -> str:
        if self._mock:
            return "mock"
        if self._hlos_managed:
            return f"hlos-run (space: {self._space})"
        return f"hlos-api (space: {self._space})"
