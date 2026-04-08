"""
Cryptographic hash functions module.
Ensures data integrity through SHA-256 hashes.
"""

import hashlib
import json
from typing import Any, Union


class HashUtils:
    """
    Utility for cryptographic hashing operations.
    Uses SHA-256 to generate deterministic and collision-resistant hashes.
    """

    ALGORITHM = 'sha256'

    @staticmethod
    def hash_string(data: str) -> str:
        """
        Calculates the SHA-256 hash of a string.

        Args:
            data: The string to hash

        Returns:
            64-character hexadecimal hash
        """
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """
        Calculates the SHA-256 hash of bytes.

        Args:
            data: Bytes to hash

        Returns:
            64-character hexadecimal hash
        """
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def hash_object(obj: Any) -> str:
        """
        Calculates the SHA-256 hash of a Python object.
        The object is serialized to JSON with sorted keys for determinism.

        Args:
            obj: JSON-serializable object (dict, list, etc.)

        Returns:
            64-character hexadecimal hash
        """
        json_string = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
        return HashUtils.hash_string(json_string)

    @staticmethod
    def double_hash(data: str) -> str:
        """
        Applies double-hashing (hash of hash) for increased security.
        Used in Bitcoin to prevent length-extension attacks.

        Args:
            data: The string to hash

        Returns:
            Double hexadecimal hash
        """
        first_hash = hashlib.sha256(data.encode('utf-8')).digest()
        return hashlib.sha256(first_hash).hexdigest()

    @staticmethod
    def hash_pair(left: str, right: str) -> str:
        """
        Concatenates and hashes two hashes.
        Used in Merkle Tree construction.

        Args:
            left: Left hash
            right: Right hash

        Returns:
            Combined hash
        """
        combined = left + right
        return HashUtils.hash_string(combined)

    @staticmethod
    def verify_hash(data: Union[str, bytes], expected_hash: str) -> bool:
        """
        Verifies if the data hash matches the expected hash.

        Args:
            data: Original data
            expected_hash: Expected hash

        Returns:
            True if hashes match, False otherwise
        """
        if isinstance(data, bytes):
            actual_hash = HashUtils.hash_bytes(data)
        else:
            actual_hash = HashUtils.hash_string(data)
        return actual_hash == expected_hash

    @staticmethod
    def generate_nonce_hash(data: str, nonce: int) -> str:
        """
        Generates hash for proof-of-work.

        Args:
            data: Base data
            nonce: Nonce value

        Returns:
            Combined hash
        """
        return HashUtils.hash_string(f"{data}{nonce}")

    @staticmethod
    def meets_difficulty(hash_value: str, difficulty: int) -> bool:
        """
        Checks if a hash meets the difficulty requirement.
        (First 'difficulty' characters must be 0)

        Args:
            hash_value: Hash to verify
            difficulty: Number of zeros required at the beginning

        Returns:
            True if hash meets difficulty
        """
        return hash_value.startswith('0' * difficulty)
