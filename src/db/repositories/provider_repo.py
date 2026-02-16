"""
Provider repository for managing LLM provider configuration.

Simplified CRUD operations for provider registration and activation.
"""

import json
from typing import Any

from db.connection import DatabaseConnection


class ProviderRepository:
    """Manages LLM provider configuration persistence."""

    def __init__(self, conn: DatabaseConnection):
        """
        Initialize provider repository.

        Args:
            conn: Database connection
        """
        self.conn = conn

    def add(
        self,
        provider_name: str,
        provider_type: str,
        config: dict[str, Any],
        default_model: str | None = None,
        available_models: list[str] | None = None,
    ) -> None:
        """
        Add or update LLM provider configuration.

        Args:
            provider_name: Unique provider identifier
            provider_type: Type (ollama, claude_cli, gemini_cli)
            config: Provider configuration dict
            default_model: Default model name
            available_models: List of available model names
        """
        self.conn.execute(  # pragma: no cover
            """
            INSERT OR REPLACE INTO llm_providers (
                provider_name, provider_type, config,
                default_model, available_models,
                endpoint, timeout, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (
                provider_name,
                provider_type,
                json.dumps(config),
                default_model,
                json.dumps(available_models) if available_models else None,
                config.get("endpoint"),
                config.get("timeout", 300),
            ),
        )
        self.conn.commit()  # pragma: no cover

    def get_active(self) -> dict[str, Any] | None:
        """
        Get the currently active provider configuration.

        Returns:
            Active provider dict with parsed config and models, None if not found
        """
        return self.conn.fetch_one_dict(
            "SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1",
            json_fields=["config", "available_models"],
        )

    def set_active(self, provider_name: str) -> None:
        """
        Set the active provider.

        Args:
            provider_name: Name of provider to activate
        """
        self.conn.execute("UPDATE llm_providers SET is_active = 0")  # pragma: no cover
        self.conn.execute(  # pragma: no cover
            """
            UPDATE llm_providers
            SET is_active = 1, last_used_at = CURRENT_TIMESTAMP
            WHERE provider_name = ?
        """,
            (provider_name,),
        )
        self.conn.commit()  # pragma: no cover
