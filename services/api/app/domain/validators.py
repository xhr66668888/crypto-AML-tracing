import re

from app.domain.chains import supported_chain_ids


ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def detect_target_type(target: str) -> str:
    value = target.strip()
    if ADDRESS_RE.match(value):
        return "address"
    if TX_HASH_RE.match(value):
        return "transaction_hash"
    raise ValueError("Target must be an Ethereum address or transaction hash.")


def normalize_address(address: str) -> str:
    if not ADDRESS_RE.match(address.strip()):
        raise ValueError("Invalid Ethereum address.")
    return address.strip().lower()


def normalize_hash(tx_hash: str) -> str:
    if not TX_HASH_RE.match(tx_hash.strip()):
        raise ValueError("Invalid Ethereum transaction hash.")
    return tx_hash.strip().lower()


def validate_chain_id(chain_id: str) -> str:
    value = str(chain_id).strip()
    if value not in supported_chain_ids():
        supported = ", ".join(sorted(supported_chain_ids(), key=int))
        raise ValueError(f"Unsupported chain_id. Supported values: {supported}.")
    return value
