"""
Circle Wallets API service.
All API keys are loaded from environment variables - NEVER hardcoded.
Implements proper entity secret encryption per Circle's security requirements.
"""
import httpx
import base64
import uuid
from typing import Dict, Any, Optional
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from app.config import settings
from app.utils.exceptions import CircleAPIException
import logging

logger = logging.getLogger(__name__)


class CircleWalletsService:
    """
    Circle Wallets API client.
    API keys are ONLY loaded from environment variables.
    Properly encrypts entity secret for each API request per Circle's requirements.
    """

    def __init__(self):
        # API credentials from environment (NEVER hardcoded!)
        self.api_key = settings.CIRCLE_API_KEY
        self.entity_secret_hex = settings.CIRCLE_ENTITY_SECRET
        self.base_url = settings.CIRCLE_API_BASE_URL

        # Verify credentials are set
        if not self.api_key or not self.entity_secret_hex:
            raise ValueError(
                "Circle API credentials not configured. "
                "Set CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET in environment variables."
            )

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _get_entity_public_key(self) -> str:
        """
        Fetch Circle's current entity public key.
        This key changes periodically, so we fetch it for each request.

        Returns:
            PEM-formatted RSA public key

        Raises:
            CircleAPIException: If public key fetch fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/w3s/config/entity/publicKey",
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code != 200:
                    logger.error("Failed to fetch public key: %s", response.text)
                    raise CircleAPIException(f"Failed to fetch entity public key: {response.text}")

                data = response.json()
                public_key_pem = data.get("data", {}).get("publicKey")

                if not public_key_pem:
                    raise CircleAPIException("Public key not found in response")

                return public_key_pem

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching public key: %s", str(e))
            raise CircleAPIException(f"Network error fetching public key: {str(e)}") from e

    async def _encrypt_entity_secret(self) -> str:
        """
        Encrypt entity secret with Circle's public key using RSA-OAEP.
        This MUST be done for EVERY API request to prevent replay attacks.

        Returns:
            Base64-encoded encrypted entity secret ciphertext

        Raises:
            CircleAPIException: If encryption fails
        """
        try:
            public_key_pem = await self._get_entity_public_key()
            entity_secret_bytes = bytes.fromhex(self.entity_secret_hex)
            public_key = RSA.import_key(public_key_pem)
            cipher = PKCS1_OAEP.new(public_key, hashAlgo=SHA256)
            ciphertext = cipher.encrypt(entity_secret_bytes)
            entity_secret_ciphertext = base64.b64encode(ciphertext).decode('utf-8')
            logger.debug("Entity secret encrypted successfully")
            return entity_secret_ciphertext

        except ValueError as e:
            logger.error("Invalid entity secret format: %s", str(e))
            raise CircleAPIException(
                f"Entity secret must be a 64-character hex string. Error: {str(e)}"
            ) from e
        except Exception as e:
            logger.error("Encryption error: %s", str(e))
            raise CircleAPIException(f"Failed to encrypt entity secret: {str(e)}") from e

    async def create_wallet(self, username: str) -> Dict[str, Any]:
        """
        Create a new developer-controlled wallet for a user on Arc Testnet.

        Args:
            username: Username for wallet description

        Returns:
            Wallet data with id and address

        Raises:
            CircleAPIException: If wallet creation fails
        """
        try:
            entity_secret_ciphertext = await self._encrypt_entity_secret()
            idempotency_key = str(uuid.uuid4())

            async with httpx.AsyncClient() as client:
                payload = {
                    "idempotencyKey": idempotency_key,
                    "blockchains": ["ARC-TESTNET"],
                    "count": 1,
                    "walletSetId": settings.CIRCLE_WALLET_SET_ID,
                    "entitySecretCiphertext": entity_secret_ciphertext,
                    "metadata": [
                        {
                            "name": f"FLUX_{username}",
                            "refId": username
                        }
                    ]
                }

                response = await client.post(
                    f"{self.base_url}/w3s/developer/wallets",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code not in [200, 201]:
                    logger.error("Circle API error: %s", response.text)
                    raise CircleAPIException(f"Failed to create wallet: {response.text}")

                data = response.json()
                logger.info("Circle create wallet response: %s", data)
                wallets = data.get("data", {}).get("wallets", [])

                if not wallets:
                    raise CircleAPIException("No wallet returned from Circle API")

                wallet = wallets[0]

                return {
                    "wallet_id": wallet.get("id"),
                    "address": wallet.get("address"),
                    "blockchain": wallet.get("blockchain", "ARC-TESTNET")
                }

        except httpx.HTTPError as e:
            logger.error("HTTP error creating wallet: %s", str(e))
            raise CircleAPIException(f"Network error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error creating wallet: %s", str(e))
            raise CircleAPIException(f"Failed to create wallet: {str(e)}") from e

    async def get_balance(self, wallet_id: str) -> str:
        """
        Get token balances for a developer-controlled wallet.

        Args:
            wallet_id: Circle wallet ID

        Returns:
            USDC balance as string
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/w3s/wallets/{wallet_id}/balances",
                    headers=self.headers,
                    timeout=30.0
                )

                if response.status_code == 404:
                    raise CircleAPIException(f"Wallet {wallet_id} not found in Circle")

                if response.status_code != 200:
                    logger.error("Circle API error: %s", response.text)
                    raise CircleAPIException(f"Failed to get balance: {response.text}")

                data = response.json()
                token_balances = data.get("data", {}).get("tokenBalances", [])

                for balance in token_balances:
                    token = balance.get("token", {})
                    if token.get("symbol") == "USDC":
                        return balance.get("amount", "0")

                return "0"

        except httpx.HTTPError as e:
            logger.error("HTTP error getting balance: %s", str(e))
            raise CircleAPIException(f"Network error: {str(e)}") from e

    async def send_usdc(
        self,
        from_wallet_id: str,
        to_address: str,
        amount: str
    ) -> Dict[str, Any]:
        """
        Send USDC via Circle W3S developer-controlled wallet API on Arc Testnet.
        Note: No tokenAddress needed — Arc uses native USDC.

        Args:
            from_wallet_id: Sender wallet ID
            to_address: Recipient wallet address
            amount: Amount in USDC (with decimals)

        Returns:
            Transaction data with id and status
        """
        try:
            entity_secret_ciphertext = await self._encrypt_entity_secret()
            idempotency_key = str(uuid.uuid4())

            async with httpx.AsyncClient() as client:
                payload = {
                    "idempotencyKey": idempotency_key,
                    "walletId": from_wallet_id,
                    "blockchain": "ARC-TESTNET",
                    # No tokenAddress — Arc Testnet uses native USDC, not an ERC-20 contract
                    "destinationAddress": to_address,
                    "amounts": [amount],
                    "feeLevel": "MEDIUM",
                    "entitySecretCiphertext": entity_secret_ciphertext
                }

                response = await client.post(
                    f"{self.base_url}/w3s/developer/transactions/transfer",
                    json=payload,
                    headers=self.headers,
                    timeout=60.0
                )

                if response.status_code not in [200, 201, 202]:
                    logger.error("Circle API error: %s", response.text)
                    raise CircleAPIException(f"Failed to send USDC: {response.text}")

                data = response.json()
                transaction = data.get("data", {})

                return {
                    "transfer_id": transaction.get("id"),
                    "status": transaction.get("state", "PENDING"),
                    "tx_hash": transaction.get("txHash"),
                }

        except httpx.HTTPError as e:
            logger.error("HTTP error sending USDC: %s", str(e))
            raise CircleAPIException(f"Network error: {str(e)}") from e
        except Exception as e:
            logger.error("Unexpected error sending USDC: %s", str(e))
            raise CircleAPIException(f"Failed to send USDC: {str(e)}") from e


# Global service instance
circle_service = CircleWalletsService()
