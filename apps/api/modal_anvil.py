"""Hosts the demo chain (Anvil) on Modal as a public JSON-RPC endpoint.

    modal deploy apps/api/modal_anvil.py

This is the piece that lets a customer pay from their own MetaMask on their own
phone: the wallet needs an RPC URL it can reach over the public internet, which
`http://anvil:8545` on a Docker Compose network is not.

Three things here are load-bearing and easy to get wrong:

1. `unauthenticated=True`. Modal Servers reject unauthenticated traffic with a
   401 by default. MetaMask cannot send a Modal proxy token, so without this the
   wallet simply cannot talk to the chain.

2. `min_containers=1`. Unlike Functions, Server requests are *not* queued while a
   container boots — a Server scaled to zero rejects with 503. MetaMask does not
   retry a 503, so a cold start mid-demo looks like the chain does not exist.
   Keeping one container warm is what makes this a real always-on endpoint.

3. `--state` on a Volume. Anvil holds the entire chain in memory. A container
   recycle without this wipes every deployed contract, which would strand the
   addresses configured in the API's secret and break the demo silently. Anvil
   reloads this file on boot and rewrites it every few seconds.

Note `target_concurrency` is deliberately unset: this must be a *singleton*.
Two containers would be two independent chains that disagree about who has paid.
The guide prefers unset over `max_containers=1` so a redeploy can still hand off
gracefully.
"""

import os
import subprocess
from pathlib import Path

import modal

# Anvil's default. Kept as-is so the well-known development accounts and their
# published private keys work — that is a feature for a demo chain holding
# nothing of value, since it is how a judge gets a funded wallet in seconds.
CHAIN_ID = 31337

STATE_DIR = "/data"
STATE_FILE = f"{STATE_DIR}/anvil-state.json"

# Modal Servers default to port 8000, so bind Anvil there rather than its usual
# 8545 and skip a port declaration.
PORT = 8000

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "git", "ca-certificates")
    .run_commands(
        "curl -L https://foundry.paradigm.xyz | bash",
        "/root/.foundry/bin/foundryup",
    )
    .env({"PATH": "/root/.foundry/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"})
)

volume = modal.Volume.from_name("settleflow-chain", create_if_missing=True)

app = modal.App("settleflow-anvil", image=image)


@app.server(
    unauthenticated=True,
    volumes={STATE_DIR: volume},
    min_containers=1,
    scaledown_window=1200,
    startup_timeout=180,
)
class Anvil:
    @modal.enter()
    def start(self):
        cmd = [
            "anvil",
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--chain-id",
            str(CHAIN_ID),
            # Loads this file if it exists, creates it otherwise, and rewrites
            # it on the interval below plus on SIGTERM.
            "--state",
            STATE_FILE,
            "--state-interval",
            "5",
        ]
        print("starting:", " ".join(cmd))
        subprocess.Popen(cmd)


# --- Contract deployment -----------------------------------------------------
# Anvil starts empty, so the router and the mock stablecoin have to be deployed
# onto it before any invoice can be paid. Running this from Modal rather than
# the laptop means no local Foundry install is required, and it works the same
# way from CI.

# contracts/lib is already vendored in the repo, so the image needs Foundry but
# not a `forge install` (which would need network and git at runtime).
#
# Guarded on is_local() because this module is imported inside the container
# too, where there is no repo to point at — `Path(__file__).parents[2]` resolves
# against /root/modal_anvil.py and raises, which fails the *whole* App including
# the Anvil server. add_local_dir only ever needs to run on the deploying
# machine, so the remote import simply skips it.
#
# copy=True bakes the sources into a layer so `forge build` can run as a build
# step. That matters: forge downloads the solc binary on first compile, and a
# container doing that at *run* time failed against binaries.soliditylang.org.
# Compiling at build time caches both solc and the artifacts in the image, so
# deployment is a pure broadcast with no toolchain downloads.
if modal.is_local():
    _repo_root = Path(__file__).resolve().parents[2]
    contracts_image = image.add_local_dir(
        _repo_root / "contracts", remote_path="/contracts", copy=True
    ).run_commands("cd /contracts && forge build")
else:
    contracts_image = image

# Anvil's first default account. Publicly known, funded with 10000 test ETH, and
# safe precisely because this chain's money is worthless — never reuse it
# anywhere with real value.
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@app.function(image=contracts_image, timeout=900)
def deploy_contracts(rpc_url: str):
    """modal run apps/api/modal_anvil.py::deploy_contracts --rpc-url https://...

    Prints the two addresses to put in the API's Modal Secret.
    """
    result = subprocess.run(
        [
            "forge",
            "script",
            "script/Deploy.s.sol",
            "--rpc-url",
            rpc_url,
            "--private-key",
            DEPLOYER_KEY,
            "--broadcast",
        ],
        cwd="/contracts",
        # Inherit the real environment rather than replacing it. Passing a bare
        # dict dropped HOME and the TLS trust store, which broke forge's HTTPS
        # calls before it ever reached the RPC.
        env={**os.environ, "PRIVATE_KEY": DEPLOYER_KEY},
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"forge script failed with code {result.returncode}")
    return result.stdout
