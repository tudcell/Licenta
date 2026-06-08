"""
Digital signature module using ECDSA.
Ensures authenticity and non-repudiation of transactions.
"""

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

logger = logging.getLogger("blockchain_audit")


@dataclass
class KeyPair:
    """
    Represents a cryptographic key pair (public and private).
    """
    private_key: ec.EllipticCurvePrivateKey
    public_key: ec.EllipticCurvePublicKey

    def get_public_key_hex(self) -> str:
        """Returns the public key in hexadecimal format."""
        public_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.CompressedPoint
        )
        return public_bytes.hex()

    def sign(self, data: Any) -> str:
        """Sign data with this keypair's private key. Returns base64 signature.

        This is the only way to use the private key from outside KeyPair.
        The raw key material never leaves the object via this path.
        """
        return DigitalSignature.sign(self.private_key, data)

    def export_private_key_hex(self) -> str:
        """Export the private key as hex bytes for persistence.

        WARNING: this exposes the raw key. Only the persistence adapter
        should call it, immediately wrapping the result in encryption
        before writing to disk. Do not log, repr, or include in HTTP
        responses.
        """
        private_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        return private_bytes.hex()

    def get_address(self) -> str:
        """
        Generates an address from the public key (similar to Bitcoin addresses).
        Uses the hash of the public key.
        """
        public_hex = self.get_public_key_hex()
        # SHA-256 of the public key
        sha256_hash = hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()
        # Return first 40 characters as address
        return sha256_hash[:40]


class DigitalSignature:
    """
    Implements digital signatures using ECDSA (Elliptic Curve Digital Signature Algorithm).

    ECDSA offers:
    - Security equivalent to RSA at much smaller key sizes
    - Shorter signatures and faster verification
    - Used in Bitcoin, Ethereum and other blockchains
    """

    CURVE = ec.SECP256K1()  # Curve used by Bitcoin

    @staticmethod
    def generate_key_pair() -> KeyPair:
        """
        Generates a new ECDSA key pair.

        Returns:
            KeyPair with private and public keys
        """
        private_key = ec.generate_private_key(
            DigitalSignature.CURVE,
            default_backend()
        )
        public_key = private_key.public_key()
        return KeyPair(private_key=private_key, public_key=public_key)

    @staticmethod
    def sign(private_key: ec.EllipticCurvePrivateKey, data: Any) -> str:
        """
        Signs data with the private key.

        Args:
            private_key: ECDSA private key
            data: Data to sign (will be serialized to JSON)

        Returns:
            Signature in base64 format
        """
        # Deterministic serialization
        if isinstance(data, str):
            message = data.encode('utf-8')
        else:
            json_string = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
            message = json_string.encode('utf-8')

        # Sign with ECDSA
        signature = private_key.sign(
            message,
            ec.ECDSA(hashes.SHA256())
        )

        return base64.b64encode(signature).decode('utf-8')

    @staticmethod
    def verify(public_key: ec.EllipticCurvePublicKey, data: Any, signature: str) -> bool:
        """
        Verifies the digital signature.

        Args:
            public_key: ECDSA public key
            data: Original data
            signature: Signature in base64 format

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Deterministic serialization (identical to sign)
            if isinstance(data, str):
                message = data.encode('utf-8')
            else:
                json_string = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
                message = json_string.encode('utf-8')

            # Decode signature
            signature_bytes = base64.b64decode(signature)

            # Verify
            public_key.verify(
                signature_bytes,
                message,
                ec.ECDSA(hashes.SHA256())
            )
            return True

        except InvalidSignature:
            return False
        except Exception as e:
            logger.warning("Error verifying signature: %s", e)
            return False

    @staticmethod
    def public_key_from_hex(hex_string: str) -> ec.EllipticCurvePublicKey:
        """
        Reconstructs the public key from hexadecimal format.

        Args:
            hex_string: Public key in hex format (compressed point)

        Returns:
            Public key object
        """
        public_bytes = bytes.fromhex(hex_string)
        return ec.EllipticCurvePublicKey.from_encoded_point(
            DigitalSignature.CURVE,
            public_bytes
        )

    @staticmethod
    def private_key_from_hex(hex_string: str) -> ec.EllipticCurvePrivateKey:
        """
        Reconstructs the private key from hexadecimal format.

        Args:
            hex_string: Private key in hex format (DER encoded)

        Returns:
            Private key object
        """
        private_bytes = bytes.fromhex(hex_string)
        return serialization.load_der_private_key(
            private_bytes,
            password=None,
            backend=default_backend()
        )

    @staticmethod
    def sign_with_hex_key(private_key_hex: str, data: Any) -> str:
        """
        Signs using the private key in hex format.

        Args:
            private_key_hex: Private key in hex format
            data: Data to sign

        Returns:
            Signature in base64 format
        """
        private_key = DigitalSignature.private_key_from_hex(private_key_hex)
        return DigitalSignature.sign(private_key, data)

    @staticmethod
    def verify_with_hex_key(public_key_hex: str, data: Any, signature: str) -> bool:
        """
        Verifies signature using the public key in hex format.

        Args:
            public_key_hex: Public key in hex format
            data: Original data
            signature: Signature to verify

        Returns:
            True if valid, False otherwise
        """
        try:
            public_key = DigitalSignature.public_key_from_hex(public_key_hex)
            return DigitalSignature.verify(public_key, data, signature)
        except Exception as e:
            logger.warning("Error verifying with hex key: %s", e)
            return False
