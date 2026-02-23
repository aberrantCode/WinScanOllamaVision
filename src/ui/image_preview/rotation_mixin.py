# mypy: disable-error-code=attr-defined
"""_RotationPersistenceMixin — per-file rotation load/save via AnalysisDB."""


class _RotationPersistenceMixin:
    """Mixin providing rotation persistence methods for ImagePreviewWidget."""

    def _is_rotation_persistence_enabled(self) -> bool:
        """Check if rotation persistence is enabled in settings."""
        if not self.config_manager:
            return False
        return bool(self.config_manager.get_bool("GUI", "persist_rotation", True))

    def _load_saved_rotation(self, file_path: str) -> int:
        """
        Load saved rotation for a file from database.

        Args:
            file_path: Absolute path to image file

        Returns:
            Rotation angle in degrees (0, 90, 180, 270), or 0 if not found
        """
        if not self.analysis_db:
            return 0

        try:
            from db.repositories.rotation_repo import RotationRepository

            rotation_repo = RotationRepository(self.analysis_db.connection)
            return rotation_repo.get(file_path)
        except Exception as e:
            from services.logging_service import get_logger

            logger = get_logger()
            logger.warning(f"Failed to load rotation for {file_path}: {e}")
            return 0

    def _save_rotation(self, file_path: str, rotation_degrees: int) -> None:
        """
        Save rotation for a file to database.

        Args:
            file_path: Absolute path to image file
            rotation_degrees: Rotation angle in degrees
        """
        if not self.analysis_db:
            return

        try:
            from db.repositories.rotation_repo import RotationRepository

            rotation_repo = RotationRepository(self.analysis_db.connection)
            rotation_repo.save(file_path, rotation_degrees)

            from services.logging_service import get_logger

            logger = get_logger()
            logger.info(f"Saved rotation {rotation_degrees}° for {file_path}")
        except Exception as e:
            from services.logging_service import get_logger

            logger = get_logger()
            logger.error(f"Failed to save rotation for {file_path}: {e}", exc_info=True)
