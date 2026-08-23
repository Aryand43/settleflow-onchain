"""Rebuilds the `settleflow` Modal Secret from apps/api/.env.

    python3 scripts/sync_modal_secret.py        (or: make modal-secret)

The hosted deployment reads its configuration from one Modal Secret. That secret
is *derived* from the local .env rather than maintained by hand, so there is a
single place to change a key — but a handful of values mean different things in
the two environments, and copying those verbatim is what breaks the deployment.

Values are never printed. `modal secret create --force` replaces the secret
wholesale, so this always sends the complete set.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = REPO_ROOT / "apps" / "api" / ".env"

# Hosted values that differ from local ones. Everything else is copied as-is.
OVERRIDES = {
    # The chain is the Modal-hosted Anvil, not the one in Docker Compose.
    "RPC_URL": "https://vyoj--settleflow-anvil-anvil.us-east.modal.direct",
    "CHAIN_ID": "31337",
    # Deterministic: a fresh Anvil always redeploys these to the same addresses,
    # so a chain reset does not require touching this file.
    "USDC_CONTRACT_ADDRESS": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
    "PAYMENT_CONTRACT_ADDRESS": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    # Emailed payment links are built from this. localhost is unreachable from
    # the phone that receives the email.
    "WEB_BASE_URL": "https://settleflow-onchain.vercel.app",
    # Points every seeded customer at one real inbox via +tags. Without it
    # seed.py writes @example.com addresses, which bounce.
    "DEMO_CUSTOMER_EMAIL": "settleflowhackathon@gmail.com",
}

# Local-only keys that must NOT reach the deployment.
#
# PUBLIC_RPC_URL is the important one: locally it is http://localhost:8545, so
# the browser can bypass the compose network. Copying that to Modal would hand
# every customer's wallet an RPC URL pointing at their own machine. Hosted, the
# API and the browser share one public URL, so leaving it unset is correct —
# config.py falls back to RPC_URL.
SKIP = {"PUBLIC_RPC_URL"}


def main() -> int:
    if not ENV_FILE.exists():
        print(f"error: {ENV_FILE} not found", file=sys.stderr)
        return 1

    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key in SKIP or not value:
            continue
        env[key] = value

    env.update(OVERRIDES)

    print(f"syncing {len(env)} keys to the 'settleflow' Modal Secret")
    print("  overridden:", ", ".join(sorted(OVERRIDES)))
    print("  skipped:   ", ", ".join(sorted(SKIP)))

    result = subprocess.run(
        ["modal", "secret", "create", "settleflow", *[f"{k}={v}" for k, v in env.items()], "--force"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print("done — redeploy for it to take effect: make modal-deploy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
