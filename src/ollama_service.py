import ollama
import json
import os
from typing import List, Dict, Optional, Any
import httpx

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 300.0):
        """
        Initialize OllamaService with configurable timeout.

        Args:
            base_url: Ollama server URL
            timeout: Request timeout in seconds (default: 300 seconds / 5 minutes)
        """
        # The SDK uses OLLAMA_HOST environment variable or default localhost:11434
        # We can set the host if needed
        if base_url != "http://localhost:11434":
            os.environ['OLLAMA_HOST'] = base_url
        self.base_url = base_url
        self.timeout = timeout

        # Create client with timeout configuration
        self.client = ollama.Client(
            host=base_url,
            timeout=httpx.Timeout(timeout)
        )

    def list_models(self) -> List[Dict[str, Any]]:
        """Lists locally available Ollama models."""
        try:
            response = self.client.list()
            return response.get("models", [])
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Ollama server. Is it running? Error: {e}")

    @staticmethod
    def is_vision_model(model_name: str) -> bool:
        """
        Determine if a model is a vision model based on its name.
        Vision models typically have specific name patterns.
        """
        vision_keywords = [
            'llava', 'bakllava', 'llava-phi', 'llava-llama3', 'llava-v1',
            'moondream', 'cogvlm', 'qwen-vl', 'qwen2-vl', 'qwen2.5-vl', 'qwen3-vl',
            'deepseek-vl', 'yi-vl', 'phi-3-vision', 'phi3-vision',
            'internvl', 'minicpm-v', 'vision', 'vl-', '-vl', '-vision'
        ]
        model_lower = model_name.lower()
        return any(keyword in model_lower for keyword in vision_keywords)

    def pull_model(self, model_name: str, progress_callback=None) -> None:
        """Pulls an Ollama model. This will block until the download is complete."""
        try:
            # The SDK's pull method handles streaming
            for progress in self.client.pull(model_name, stream=True):
                if progress_callback and 'status' in progress:
                    status = progress.get('status', '')
                    completed = progress.get('completed', 0)
                    total = progress.get('total', 0)
                    if total > 0:
                        pct = int((completed / total) * 100)
                        progress_callback(f"{status}: {pct}%")
                    else:
                        progress_callback(status)

            # Verify model was pulled
            if not any(m['name'].startswith(model_name) for m in self.list_models()):
                raise Exception(f"Model '{model_name}' did not appear in list_models after pull operation.")
        except Exception as e:
            raise Exception(f"An unexpected error occurred during model pull: {e}")

    def chat_with_vision_model(self,
                               model_name: str,
                               image_paths: List[str],
                               prompt: str,
                               format_json: bool = False
                               ) -> Dict[str, Any]:
        """
        Chats with a vision-capable Ollama model using the Python SDK.
        Args:
            model_name: The name of the vision model to use.
            image_paths: A list of paths to image files (e.g., PNG) to include in the message.
            prompt: The text prompt for the model.
            format_json: If True, instructs the model to respond in JSON format.
        Returns:
            The model's response.
        """
        # DEBUG: Show what images are being processed
        print(f"\n=== DEBUG: WinScanLLM Vision Request (SDK) ===")
        print(f"Model: {model_name}")
        print(f"Image paths received: {len(image_paths)}")
        for i, path in enumerate(image_paths, 1):
            exists = os.path.exists(path) if path else False
            size = os.path.getsize(path) if exists else 0
            print(f"  Image {i}: {path}")
            print(f"    Exists: {exists} | Size: {size} bytes")

        try:
            # The SDK accepts file paths directly and handles encoding
            # Build the request parameters
            chat_params = {
                'model': model_name,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': image_paths  # SDK accepts paths directly!
                    }
                ],
                'options': {
                    'temperature': 0.1  # Keep temperature low for factual extraction
                }
            }

            # Only add format parameter if we want JSON
            if format_json:
                chat_params['format'] = 'json'

            # Use client with configured timeout
            response = self.client.chat(**chat_params)

            print(f"SDK Response received successfully")
            print(f"  Message content length: {len(response['message']['content'])} chars")
            print(f"  Timeout setting: {self.timeout} seconds")
            print("==========================================\n")

            return response.get("message", {})

        except Exception as e:
            print(f"ERROR in chat_with_vision_model: {e}")
            print("==========================================\n")
            raise ConnectionError(f"Failed to communicate with Ollama: {e}")

    # --- Specific Application Prompts ---

    def validate_grouping(self, model_name: str, image_paths: List[str], custom_prompt: str = None) -> bool:
        """
        Uses Ollama to determine if a list of images likely belongs to the same document.
        Returns True if they do, False otherwise.
        """
        if custom_prompt:
            prompt = custom_prompt
        else:
            # Default prompt
            prompt = (
                "You are an expert document analyst. Examine the provided images. "
                "Determine if all pages belong to the *same continuous physical document*. "
                "Respond ONLY with 'YES' if all pages are from the same document, or 'NO' if they are not. "
                "Do not add any other text or explanation."
            )

        response = self.chat_with_vision_model(model_name, image_paths, prompt)
        response_message = response.get("content", "").strip()

        # DEBUG: Show raw response
        print(f"\n=== DEBUG: Validation Response ===")
        print(f"Raw response: '{response_message}'")
        print(f"Upper case: '{response_message.upper()}'")
        print(f"Equals 'YES': {response_message.upper() == 'YES'}")
        print(f"Contains 'YES': {'YES' in response_message.upper()}")
        print("=================================\n")

        return response_message.upper() == "YES"

    def validate_grouping_with_page_number(self, model_name: str, image_paths: List[str], custom_prompt: str = None) -> Dict[str, Any]:
        """
        Validates which images belong to same document using improved JSON format.

        Now uses the Document Validation Prompt which returns structured data about
        which pages belong together and which don't.

        Args:
            model_name: The vision model to use
            image_paths: List of image paths for the document pages (first is anchor)
            custom_prompt: Optional custom prompt override from settings

        Returns:
            {
                'belongs': bool,  # True if ALL pages belong, False if any don't
                'doc_page_count': int,  # Number of pages that belong together
                'do_not_belong': List[int],  # 1-based indices of pages that don't belong
                'page_number': Optional[int],  # For backward compatibility
                'total_pages': Optional[int],  # For backward compatibility
                'page_position': Optional[str],
                'confidence': str,
                'company': Optional[str],
                'document_type': Optional[str],
                'document_date': Optional[str],
                'additional': Dict[str, Any]
            }
        """
        # Use custom prompt from settings if provided
        prompt = custom_prompt if custom_prompt else None

        if not prompt:
            # Fallback to default if no custom prompt (shouldn't happen)
            prompt = """You are an expert document analyst. Examine the provided images and determine which pages belong to the same continuous physical document.

The first image should ALWAYS be considered as belonging to the document (it's the anchor page). Analyze each subsequent page to determine if it belongs with the first page or not.

Respond ONLY with valid JSON in this format:
{
  "all_belong": boolean,
  "doc_page_count": integer,
  "do_not_belong": [array of integers]
}"""

        try:
            response = self.chat_with_vision_model(model_name, image_paths, prompt, format_json=True)
            content = response.get("content", "{}")

            # Clean JSON
            content = content.strip()
            if content.startswith("```"):
                lines = content.split('\n')
                content = '\n'.join(line for line in lines if not line.strip().startswith("```"))
                content = content.strip()

            parsed = json.loads(content)

            # Debug output
            print(f"\n=== DEBUG: Document Validation (New Format) ===")
            print(f"Raw response: {content}")
            print(f"Parsed: {parsed}")
            print("=============================================\n")

            # Extract new format fields
            all_belong = parsed.get('all_belong', False)
            doc_page_count = parsed.get('doc_page_count', 1)
            do_not_belong = parsed.get('do_not_belong', [])

            # For backward compatibility, set belongs to True only if ALL belong
            belongs = all_belong

            return {
                'belongs': belongs,
                'doc_page_count': doc_page_count,
                'do_not_belong': do_not_belong,
                # Legacy fields for backward compatibility (extract from last belonging page)
                'page_number': None,  # Would need separate metadata extraction
                'total_pages': doc_page_count if all_belong else None,
                'page_position': None,
                'confidence': 'high' if all_belong else 'medium',
                'company': None,  # Metadata extraction is separate now
                'document_type': None,
                'document_date': None,
                'additional': {}
            }
        except Exception as e:
            print(f"Error in validate_grouping_with_page_number: {e}")
            import traceback
            traceback.print_exc()
            return {
                'belongs': False,
                'doc_page_count': 1,
                'do_not_belong': list(range(2, len(image_paths) + 1)),  # Assume only first belongs
                'page_number': None,
                'total_pages': None,
                'page_position': None,
                'confidence': 'low',
                'company': None,
                'document_type': None,
                'document_date': None,
                'additional': {}
            }

    def extract_document_info(self,
                              model_name: str,
                              image_paths: List[str],
                              title_keywords: str
                              ) -> Dict[str, Optional[str]]:
        """
        Uses Ollama to extract source company, document title, and relevant date.
        Args:
            model_name: The vision model to use.
            image_paths: List of image paths for the document.
            title_keywords: Comma-separated string of keywords to help identify title.
        Returns:
            A dictionary with 'company', 'title', and 'date' keys.
        """
        prompt = f"""Extract key information from the document images.

CRITICAL: Respond with ONLY valid JSON. No explanations, no markdown, no code blocks.

Required JSON format:
{{
  "company": "company name or null",
  "title": "document type or null",
  "date": "YYYY-MM-DD or null"
}}

Task:
1. Company: Organization name from headers/footers/logos
2. Title: Document type. Use one of these if applicable: {title_keywords}
3. Date: Primary document date in YYYY-MM-DD format

Rules:
- Return ONLY the JSON object
- Use null for missing values
- Keep company/title concise (under 50 chars)
- Date must be YYYY-MM-DD format or null
"""

        try:
            # Try without format='json' first - rely on prompt only
            response = self.chat_with_vision_model(model_name, image_paths, prompt, format_json=False)
            content = response.get("content", "{}")

            print(f"\n=== DEBUG: Metadata Extraction Response ===")
            print(f"Raw content: {content}")
            print("==========================================\n")

            # Try to clean the JSON if it has markdown code blocks or extra text
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code blocks
                lines = content.split('\n')
                content = '\n'.join(line for line in lines if not line.strip().startswith("```"))
                content = content.strip()

            # Try to extract JSON object if surrounded by other text
            if not content.startswith("{"):
                # Find first { and last }
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    content = content[start:end+1]

            # If content is still not valid, try manual extraction
            if not content.endswith("}"):
                # Might be incomplete - try to find a valid JSON substring
                end = content.rfind("}")
                if end != -1:
                    content = content[:end+1]

            print(f"Cleaned content: {content}")

            extracted_info = json.loads(content)

            # Ensure keys exist, even if null
            return {
                "company": extracted_info.get("company"),
                "title": extracted_info.get("title"),
                "date": extracted_info.get("date")
            }
        except json.JSONDecodeError as e:
            print(f"JSON decode error in extract_document_info: {e}")
            print(f"Content was: {content}")

            # Try to manually parse what we can from the broken JSON
            # Look for key-value pairs even if JSON is incomplete
            company = None
            title = None
            date = None

            if "company" in content.lower():
                # Try to extract company value
                import re
                match = re.search(r'"company"\s*:\s*"([^"]*)"', content, re.IGNORECASE)
                if match:
                    company = match.group(1)

            if "title" in content.lower():
                match = re.search(r'"title"\s*:\s*"([^"]*)"', content, re.IGNORECASE)
                if match:
                    title = match.group(1)

            if "date" in content.lower():
                match = re.search(r'"date"\s*:\s*"([^"]*)"', content, re.IGNORECASE)
                if match:
                    date = match.group(1)

            print(f"Manually extracted: company={company}, title={title}, date={date}")
            return {"company": company, "title": title, "date": date}
        except Exception as e:
            print(f"Error in extract_document_info: {e}")
            # Silently handle extraction errors - return None values
            return {"company": None, "title": None, "date": None}

    def infer_page_order_from_content(self, model_name: str, image_paths: List[str]) -> Dict[str, Any]:
        """
        Uses Ollama to infer logical page order from content flow (Phase 5).

        Args:
            model_name: The vision model to use
            image_paths: List of image paths for the document pages

        Returns:
            {
                'ordered_indices': List[int],
                'confidence': str
            }
        """
        prompt = f"""Analyze the content flow of these {len(image_paths)} document pages.
Determine the logical reading order based on:
- Content continuation (text flow, paragraph breaks)
- Topic progression
- Visual layout clues

Respond with ONLY valid JSON:
{{
  "ordered_indices": [list of 0-based indices in correct order],
  "confidence": "high" or "medium" or "low"
}}

Example for 3 pages: {{"ordered_indices": [1, 0, 2], "confidence": "high"}}

Current order is: [0, 1, 2, ..., {len(image_paths)-1}]
Provide the CORRECT order as indices."""

        try:
            response = self.chat_with_vision_model(model_name, image_paths, prompt, format_json=True)
            content = response.get("content", "{}")

            # Clean JSON
            content = content.strip()
            if content.startswith("```"):
                lines = content.split('\n')
                content = '\n'.join(line for line in lines if not line.strip().startswith("```"))
                content = content.strip()

            parsed = json.loads(content)
            ordered_indices = parsed.get('ordered_indices', list(range(len(image_paths))))
            confidence = parsed.get('confidence', 'low')

            print(f"\n=== DEBUG: Content-Based Ordering ===")
            print(f"Raw response: {content}")
            print(f"Ordered indices: {ordered_indices}")
            print(f"Confidence: {confidence}")
            print("====================================\n")

            # Validate indices
            if (len(ordered_indices) != len(image_paths) or
                set(ordered_indices) != set(range(len(image_paths)))):
                print(f"Invalid ordering received: {ordered_indices}")
                return {'ordered_indices': list(range(len(image_paths))), 'confidence': 'low'}

            return {'ordered_indices': ordered_indices, 'confidence': confidence}
        except Exception as e:
            print(f"Error in infer_page_order_from_content: {e}")
            return {'ordered_indices': list(range(len(image_paths))), 'confidence': 'low'}

    def extract_text_and_coords(self,
                                model_name: str,
                                image_paths: List[str],
                                progress_callback=None
                                ) -> Dict[str, Any]:
        """
        Uses Ollama (specifically a model known for structured OCR output like Qwen2.5-VL)
        to extract text and its bounding box coordinates from document images.

        Note: This functionality heavily depends on the chosen model's capabilities
        to provide structured (e.g., JSON) output with bounding box information.

        Args:
            model_name: The vision model to use (e.g., 'qwen2.5-vl').
            image_paths: List of image paths for the document.
        Returns:
            A dictionary containing extracted text and coordinate information,
            structured per the model's output. Returns empty dict if no structured
            data is found.
        """
        prompt = """You are an advanced OCR engine. Analyze the provided image(s) to extract all text.
For each detected text block or word, provide its content and its bounding box coordinates.
Respond ONLY in JSON format, structured as an array of pages, where each page
contains an array of text elements. Each text element should have 'text' (string)
and 'bbox' (an array of [x_min, y_min, x_max, y_max] integers).
Example:
[
  {
    "page_number": 1,
    "elements": [
      {"text": "Invoice", "bbox": [100, 50, 200, 70]},
      {"text": "Date:", "bbox": [100, 100, 150, 120]},
      {"text": "2023-10-26", "bbox": [160, 100, 280, 120]}
    ]
  }
]
"""

        try:
            response = self.chat_with_vision_model(model_name, image_paths, prompt, format_json=True)
            content = response.get("content", "[]")
            extracted_data = json.loads(content)
            if isinstance(extracted_data, list):
                return {"pages": extracted_data}
            else:
                # Silently handle unexpected format
                return {"pages": []}
        except json.JSONDecodeError:
            # Silently handle JSON decode errors
            return {"pages": []}
        except Exception as e:
            # Silently handle extraction errors
            return {"pages": []}


# Example Usage (for testing during development)
if __name__ == "__main__":
    ollama_service = OllamaService()

    try:
        print("Listing available models...")
        models = ollama_service.list_models()
        if models:
            print("Available models:")
            for model in models:
                print(f"- {model['name']}")
        else:
            print("No models found. Please pull some models using 'ollama pull <model_name>'.")

        # Dummy image file for testing chat_with_vision_model
        dummy_image_path = "temp_dummy_image.png"
        from PIL import Image
        img = Image.new('RGB', (60, 30), color = 'red')
        img.save(dummy_image_path)

        if models:
            vision_model = next((m['name'] for m in models if 'vision' in m.get('family', '') or 'llava' in m['name'] or 'qwen' in m['name']), None)
            if vision_model:
                print(f"\nUsing vision model: {vision_model}")

                # Test grouping validation
                print("\nTesting grouping validation...")
                is_grouped = ollama_service.validate_grouping(vision_model, [dummy_image_path])
                print(f"Are images grouped? {is_grouped}")

                # Test document info extraction
                print("\nTesting document info extraction...")
                doc_info = ollama_service.extract_document_info(vision_model, [dummy_image_path], "Invoice, Statement")
                print(f"Extracted Info: {doc_info}")

            else:
                print("No suitable vision model found for testing chat functions.")

        if os.path.exists(dummy_image_path):
            os.remove(dummy_image_path)

    except ConnectionError as e:
        print(f"Connection Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
