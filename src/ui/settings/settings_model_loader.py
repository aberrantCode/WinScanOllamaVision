# mypy: disable-error-code=attr-defined
"""Mixin class providing model-loading methods for EnhancedSettingsWindow."""

import json
import subprocess
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QComboBox

from ui.styles import show_warning


class _ModelLoaderMixin:
    """Mixin that provides LLM model loading and caching methods.

    Expects the host class to provide:
        self.config_manager   – ConfigManager instance
        self.ollama_service   – OllamaService instance
        self.ollama_model_combo / self.claude_model_combo / self.gemini_model_combo
        self._get_logger()    – returns a logging.Logger
    """

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    def _load_ollama_models(self, force_refresh: bool = False, cache_only: bool = False):
        """Load available Ollama vision models with download status and caching

        Args:
            force_refresh: If True, bypass cache and check download status fresh
            cache_only: If True, skip network calls — use cached or default list only
        """
        self.ollama_model_combo.clear()

        # Popular vision models available in Ollama
        available_vision_models = [
            "llava:latest",
            "llava:7b",
            "llava:13b",
            "llava:34b",
            "llava-llama3:latest",
            "llava-phi3:latest",
            "bakllava:latest",
            "moondream:latest",
            "qwen2-vl:latest",
            "qwen2-vl:2b",
            "qwen2-vl:7b",
            "qwen2.5-vl:latest",
            "minicpm-v:latest",
            "minicpm-v:8b",
            "cogvlm:latest",
            "phi3-vision:latest",
            "internvl:latest",
        ]

        downloaded_model_names: set = set()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_downloaded = self.config_manager.get_setting(
                "ModelCache", "ollama_downloaded_cache"
            )
            cached_timestamp = self.config_manager.get_setting(
                "ModelCache", "ollama_models_timestamp"
            )

            if cached_downloaded and cached_timestamp:
                try:
                    last_updated = datetime.fromisoformat(cached_timestamp)
                    now = datetime.now()

                    if now - last_updated < timedelta(hours=24):
                        # Use cached download status
                        downloaded_model_names = set(json.loads(cached_downloaded))
                        self._get_logger().debug(
                            f"Using cached Ollama download status (last checked: {last_updated.strftime('%Y-%m-%d %I:%M %p')})"
                        )
                except (ValueError, json.JSONDecodeError):
                    pass  # Cache invalid, will refresh

        # Refresh download status if not loaded from cache
        if not downloaded_model_names or force_refresh:
            if cache_only:
                # Skip network call — populate without download status markers
                pass
            else:
                try:
                    local_models = self.ollama_service.list_models()
                    downloaded_model_names = {
                        (m.get("name") or m.get("model")).split(":")[0] for m in local_models
                    }

                    # Cache the download status
                    timestamp = datetime.now().isoformat()
                    self.config_manager.set_setting(
                        "ModelCache",
                        "ollama_downloaded_cache",
                        json.dumps(list(downloaded_model_names)),
                    )
                    self.config_manager.set_setting(
                        "ModelCache", "ollama_models_timestamp", timestamp
                    )
                    self._get_logger().debug(f"Checked Ollama download status at {timestamp}")

                except Exception as e:
                    show_warning(self, "Error", f"Failed to load Ollama models: {e}")
                    return

        # Add models with download status
        for model in available_vision_models:
            model_base = model.split(":")[0]
            is_downloaded = model_base in downloaded_model_names

            display_text = f"{model} ✓ (Downloaded)" if is_downloaded else f"{model}"

            self.ollama_model_combo.addItem(display_text, model)

        # Set current model
        current_model = self.config_manager.get_setting("Ollama", "model")
        if current_model:
            model_found = False

            # Try exact match first
            for i in range(self.ollama_model_combo.count()):
                if self.ollama_model_combo.itemData(i) == current_model:
                    self.ollama_model_combo.setCurrentIndex(i)
                    model_found = True
                    break

            # Try partial match (base name) if exact match failed
            if not model_found:
                current_base = current_model.split(":")[0]
                for i in range(self.ollama_model_combo.count()):
                    if self.ollama_model_combo.itemData(i).startswith(current_base):
                        self.ollama_model_combo.setCurrentIndex(i)
                        model_found = True
                        break

            # If model not found in list, add it
            if not model_found:
                # Check if it's downloaded
                model_base = current_model.split(":")[0]
                is_downloaded = model_base in downloaded_model_names

                if is_downloaded:
                    display_text = f"{current_model} ✓ (Downloaded)"
                else:
                    display_text = f"{current_model}"

                self.ollama_model_combo.addItem(display_text, current_model)
                self.ollama_model_combo.setCurrentIndex(self.ollama_model_combo.count() - 1)

    # ------------------------------------------------------------------
    # Claude
    # ------------------------------------------------------------------

    def _load_claude_models(self, force_refresh: bool = False, cache_only: bool = False):
        """Load available Claude vision models with caching

        Args:
            force_refresh: If True, bypass cache and fetch fresh from web
            cache_only: If True, skip network calls — use cached or hardcoded defaults only
        """
        self.claude_model_combo.clear()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = self._get_cached_models("claude")
            if cached_models:
                claude_vision_models = cached_models
            elif cache_only:
                # No cache, no network call — use hardcoded curated defaults
                claude_vision_models = [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                    "claude-3-sonnet-20240229",
                    "claude-3-haiku-20240307",
                ]
            else:
                # Cache miss or expired - fetch from web
                claude_vision_models = self._fetch_claude_models_from_web()
                self._cache_models("claude", claude_vision_models)
        else:
            # Force refresh - fetch from web and update cache
            claude_vision_models = self._fetch_claude_models_from_web()
            self._cache_models("claude", claude_vision_models)

        # Populate dropdown
        for model in claude_vision_models:
            self.claude_model_combo.addItem(model)

        # Set current model
        current_model = self.config_manager.get_setting("ClaudeCLI", "default_model")
        if current_model:
            index = self.claude_model_combo.findText(current_model)
            if index >= 0:
                self.claude_model_combo.setCurrentIndex(index)
            else:
                # If saved model not in list, add it
                self.claude_model_combo.addItem(current_model)
                self.claude_model_combo.setCurrentIndex(self.claude_model_combo.count() - 1)

    # ------------------------------------------------------------------
    # Combobox helpers
    # ------------------------------------------------------------------

    def _apply_combobox_chevron_fix(self, combobox: QComboBox):
        """Apply custom paint event to draw dropdown chevron in dark mode

        Args:
            combobox: QComboBox widget to apply the fix to
        """
        from PyQt6.QtCore import QPoint
        from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon

        # Determine theme from config
        current_theme = self.config_manager.get_setting("Theme", "theme", "light")
        is_dark = current_theme == "dark"

        # Determine colors based on theme
        if is_dark:
            arrow_color = "#E0E0E0"  # Light arrow for dark mode
            bg_color = "#2D2D2D"
            text_color = "#E0E0E0"
            border_color = "#4A4A4A"
        else:
            arrow_color = "#111827"  # Dark arrow for light mode
            bg_color = "#FFFFFF"
            text_color = "#111827"
            border_color = "#E5E7EB"

        # Apply stylesheet to hide default arrow and style the combobox
        combobox.setStyleSheet(f"""
            QComboBox {{
                background: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px 30px 5px 10px;
                min-height: 20px;
            }}
            QComboBox:focus {{
                border: 1px solid #3B82F6;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 25px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                border: none;
                width: 12px;
                height: 12px;
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background: {bg_color};
                color: {text_color};
                selection-background-color: #3B82F6;
                border: 1px solid {border_color};
            }}
        """)

        # Save original paint event
        original_paint = combobox.paintEvent

        def custom_paint(event):
            """Custom paint event that draws the dropdown arrow"""
            original_paint(event)
            painter = QPainter(combobox)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Draw down arrow triangle on the right side
            arrow_x = combobox.width() - 18
            arrow_y = combobox.height() // 2

            # Create triangle points
            points = [
                QPoint(arrow_x - 4, arrow_y - 2),  # Top left
                QPoint(arrow_x + 4, arrow_y - 2),  # Top right
                QPoint(arrow_x, arrow_y + 3),  # Bottom center
            ]

            polygon = QPolygon(points)
            painter.setPen(QPen(QColor(arrow_color), 1))
            painter.setBrush(QColor(arrow_color))
            painter.drawPolygon(polygon)
            painter.end()

        # Replace paint event
        combobox.paintEvent = custom_paint  # type: ignore[method-assign]

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _get_cached_models(self, provider: str) -> list[str] | None:
        """Get cached model list if still valid (< 24 hours old)

        Args:
            provider: 'claude', 'gemini', or 'ollama'

        Returns:
            List of model names if cache is valid, None otherwise
        """
        # Get cached models and timestamp from config
        cache_key = f"{provider}_models_cache"
        timestamp_key = f"{provider}_models_timestamp"

        cached_json = self.config_manager.get_setting("ModelCache", cache_key)
        cached_timestamp = self.config_manager.get_setting("ModelCache", timestamp_key)

        if not cached_json or not cached_timestamp:
            return None

        try:
            # Parse timestamp
            last_updated = datetime.fromisoformat(cached_timestamp)
            now = datetime.now()

            # Check if cache is still valid (< 24 hours old)
            if now - last_updated < timedelta(hours=24):
                # Cache is valid - parse and return models
                models = json.loads(cached_json)
                if isinstance(models, list) and len(models) > 0:
                    self._get_logger().debug(
                        f"Using cached {provider} models (last updated: {last_updated.strftime('%Y-%m-%d %I:%M %p')})"
                    )
                    return models

        except (ValueError, json.JSONDecodeError) as e:
            self._get_logger().warning(f"Error parsing cached {provider} models: {e}")

        return None

    def _cache_models(self, provider: str, models: list[str]):
        """Cache model list with current timestamp

        Args:
            provider: 'claude', 'gemini', or 'ollama'
            models: List of model names to cache
        """
        cache_key = f"{provider}_models_cache"
        timestamp_key = f"{provider}_models_timestamp"

        # Store models as JSON array
        models_json = json.dumps(models)
        timestamp = datetime.now().isoformat()

        self.config_manager.set_setting("ModelCache", cache_key, models_json)
        self.config_manager.set_setting("ModelCache", timestamp_key, timestamp)

        self._get_logger().debug(f"Cached {len(models)} {provider} models at {timestamp}")

    # ------------------------------------------------------------------
    # Web fetch helpers
    # ------------------------------------------------------------------

    def _fetch_claude_models_from_web(self) -> list[str]:
        """Use Claude to search the web for latest vision-capable models"""
        try:
            # Create prompt for Claude to search for latest models
            prompt = """Search the web for the latest Anthropic Claude vision-capable models.
Look for official Anthropic documentation or announcements about Claude models that support image input.

Return ONLY a JSON array of model IDs (full model names with dates, like "claude-3-5-sonnet-20241022").
Include only models that support vision/image inputs.
Order from newest to oldest.

Example format:
["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"]

Return ONLY the JSON array, no other text."""

            # Call Claude CLI to search
            result = subprocess.run(
                ["claude", "--model", "sonnet", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse JSON response
                response = result.stdout.strip()
                # Extract JSON array from response (might have markdown code fences)
                if "```json" in response:
                    json_start = response.find("[")
                    json_end = response.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        response = response[json_start:json_end]
                elif "```" in response:
                    # Remove code fences
                    response = response.replace("```json", "").replace("```", "").strip()

                models = json.loads(response)
                if isinstance(models, list) and len(models) > 0:
                    return models

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            self._get_logger().info(f"Could not fetch Claude models from web: {e}")

        # Fallback to curated list
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]

    def _load_gemini_models(self, force_refresh: bool = False, cache_only: bool = False):
        """Load available Gemini vision models with caching

        Args:
            force_refresh: If True, bypass cache and fetch fresh from web
            cache_only: If True, skip network calls — use cached or hardcoded defaults only
        """
        self.gemini_model_combo.clear()

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_models = self._get_cached_models("gemini")
            if cached_models:
                gemini_vision_models = cached_models
            elif cache_only:
                # No cache, no network call — use hardcoded curated defaults
                gemini_vision_models = [
                    "gemini-2.0-flash-exp",
                    "gemini-1.5-pro",
                    "gemini-1.5-pro-002",
                    "gemini-1.5-flash",
                    "gemini-1.5-flash-002",
                    "gemini-1.5-flash-8b",
                ]
            else:
                # Cache miss or expired - fetch from web
                gemini_vision_models = self._fetch_gemini_models_from_web()
                self._cache_models("gemini", gemini_vision_models)
        else:
            # Force refresh - fetch from web and update cache
            gemini_vision_models = self._fetch_gemini_models_from_web()
            self._cache_models("gemini", gemini_vision_models)

        # Populate dropdown
        for model in gemini_vision_models:
            self.gemini_model_combo.addItem(model)

        # Set current model
        current_model = self.config_manager.get_setting("GeminiCLI", "default_model")
        if current_model:
            index = self.gemini_model_combo.findText(current_model)
            if index >= 0:
                self.gemini_model_combo.setCurrentIndex(index)
            else:
                # If saved model not in list, add it
                self.gemini_model_combo.addItem(current_model)
                self.gemini_model_combo.setCurrentIndex(self.gemini_model_combo.count() - 1)

    def _fetch_gemini_models_from_web(self) -> list[str]:
        """Use Claude to search the web for latest Gemini vision-capable models"""
        try:
            # Create prompt for Claude to search for latest Gemini models
            prompt = """Search the web for the latest Google Gemini vision-capable models.
Look for official Google AI documentation or announcements about Gemini models that support image/vision inputs.

Return ONLY a JSON array of model IDs (like "gemini-2.0-flash-exp", "gemini-1.5-pro").
Include only models that support vision/image inputs (multimodal models).
Order from newest to oldest.

Example format:
["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

Return ONLY the JSON array, no other text."""

            # Call Claude CLI to search
            result = subprocess.run(
                ["claude", "--model", "sonnet", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Parse JSON response
                response = result.stdout.strip()
                # Extract JSON array from response (might have markdown code fences)
                if "```json" in response:
                    json_start = response.find("[")
                    json_end = response.rfind("]") + 1
                    if json_start >= 0 and json_end > json_start:
                        response = response[json_start:json_end]
                elif "```" in response:
                    # Remove code fences
                    response = response.replace("```json", "").replace("```", "").strip()

                models = json.loads(response)
                if isinstance(models, list) and len(models) > 0:
                    return models

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            self._get_logger().info(f"Could not fetch Gemini models from web: {e}")

        # Fallback to curated list
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-pro-002",
            "gemini-1.5-flash",
            "gemini-1.5-flash-002",
            "gemini-1.5-flash-8b",
        ]

    def _download_ollama_model(self):
        """Download an Ollama model"""
        from ui.styles import show_information

        show_information(
            self,
            "Download Model",
            "Model download functionality will be implemented in next phase.\n"
            "For now, use 'ollama pull <model-name>' in terminal.",
        )
