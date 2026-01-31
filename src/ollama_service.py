import requests
import json
import base64
import os
from typing import List, Dict, Optional, Tuple, Any

class OllamaService:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.session = requests.Session()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Failed to connect to Ollama server at {self.base_url}. Is it running?")
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(f"HTTP Error: {e.response.status_code} - {e.response.text}")
        except json.JSONDecodeError:
            raise ValueError(f"Failed to decode JSON from response: {response.text}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred: {e}")

    def list_models(self) -> List[Dict[str, Any]]:
        """Lists locally available Ollama models."""
        response = self._make_request("GET", "api/tags")
        return response.get("models", [])

    def pull_model(self, model_name: str) -> None:
        """Pulls an Ollama model. This will block until the download is complete."""
        # The /api/pull endpoint is streamed, so we handle it differently
        url = f"{self.base_url}/api/pull"
        payload = {"name": model_name}
        try:
            with self.session.post(url, json=payload, stream=True) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=None): # Process as soon as chunks arrive
                    if chunk:
                        try:
                            # Each chunk might be a complete JSON object or part of one
                            decoded_chunk = chunk.decode('utf-8')
                            for line in decoded_chunk.splitlines():
                                if line.strip():
                                    data = json.loads(line)
                                    # print(f"Pulling {model_name}: {data.get('status', 'progress')} - {data.get('digest', '')} {data.get('total', '')}")
                                    # In a real GUI, you'd emit signals here for progress
                        except json.JSONDecodeError:
                            # Not a complete JSON line, might be partial or non-json output
                            pass # Or log it if necessary
            # Final check to see if the model is now in the list
            if not any(m['name'].startswith(model_name) for m in self.list_models()):
                raise Exception(f"Model '{model_name}' did not appear in list_models after pull operation.")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Failed to connect to Ollama server at {self.base_url}. Is it running?")
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(f"HTTP Error pulling model: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"An unexpected error occurred during model pull: {e}")

    def _encode_image(self, image_path: str) -> str:
        """Encodes an image file to a base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def chat_with_vision_model(self, 
                               model_name: str, 
                               image_paths: List[str], 
                               prompt: str,
                               format_json: bool = False
                               ) -> Dict[str, Any]:
        """
        Chats with a vision-capable Ollama model.
        Args:
            model_name: The name of the vision model to use.
            image_paths: A list of paths to image files (e.g., PNG) to include in the message.
            prompt: The text prompt for the model.
            format_json: If True, instructs the model to respond in JSON format.
        Returns:
            The model's response.
        """
        encoded_images = [self._encode_image(path) for path in image_paths]
        
        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": encoded_images
            }
        ]
        
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1 # Keep temperature low for factual extraction
            }
        }

        if format_json:
            payload["format"] = "json"

        response = self._make_request("POST", "api/chat", json=payload)
        return response.get("message", {})

    # --- Specific Application Prompts ---
    
    def validate_grouping(self, model_name: str, image_paths: List[str]) -> bool:
        """
        Uses Ollama to determine if a list of images likely belongs to the same document.
        Returns True if they do, False otherwise.
        """
        prompt = (
            "You are an expert document analyst. Examine the provided images. "
            "Determine if all pages belong to the *same continuous physical document*. "
            "Respond ONLY with 'YES' if all pages are from the same document, or 'NO' if they are not. "
            "Do not add any other text or explanation."
        )
        response_message = self.chat_with_vision_model(model_name, image_paths, prompt).get("content", "").strip().upper()
        return response_message == "YES"

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
        prompt = f"""You are an expert at extracting key information from scanned documents.
Analyze the provided images to identify the following:
1.  **Source Company:** The name of the organization that issued the document. Look at headers, footers, logos, or return addresses.
2.  **Document Title:** The main purpose or type of the document (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement). Consider the provided keywords: '{title_keywords}'. Choose the most appropriate and concise title.
3.  **Relevant Date:** The primary date associated with the document (e.g., issue date, statement date, invoice date, contract date). Prioritize the most prominent and relevant date.
Respond ONLY in JSON format. Your JSON should contain three keys: 'company', 'title', and 'date'.
If any information cannot be found, use null for its value.
Example: {{ "company": "Acme Corp", "title": "Invoice", "date": "2023-10-26" }}
"""

        try:
            response = self.chat_with_vision_model(model_name, image_paths, prompt, format_json=True)
            content = response.get("content", "{}")
            extracted_info = json.loads(content)
            
            # Ensure keys exist, even if null
            return {
                "company": extracted_info.get("company"),
                "title": extracted_info.get("title"),
                "date": extracted_info.get("date")
            }
        except json.JSONDecodeError:
            print(f"Warning: Ollama did not return valid JSON for info extraction: {content}")
            return {"company": None, "title": None, "date": None}
        except Exception as e:
            print(f"Error during document info extraction: {e}")
            return {"company": None, "title": None, "date": None}

    def extract_text_and_coords(self, 
                                model_name: str, 
                                image_paths: List[str]
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
                print(f"Warning: Ollama did not return expected list of pages for text and coords: {content}")
                return {"pages": []}
        except json.JSONDecodeError:
            print(f"Warning: Ollama did not return valid JSON for text and coords extraction: {content}")
            return {"pages": []}
        except Exception as e:
            print(f"Error during text and coords extraction: {e}")
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

        # Example for pull_model (uncomment to test, it will block)
        # print("\nAttempting to pull 'llava:latest' (this might take a while)...")
        # ollama_service.pull_model("llava:latest")
        # print("'llava:latest' pulled successfully.")

        # Dummy image file for testing chat_with_vision_model
        # You would replace this with actual image paths
        dummy_image_path = "temp_dummy_image.png"
        from PIL import Image
        img = Image.new('RGB', (60, 30), color = 'red')
        img.save(dummy_image_path)

        if models:
            vision_model = next((m['name'] for m in models if 'vision' in m['family'] or 'llava' in m['name'] or 'qwen' in m['name']), None)
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

                # Test text and coords extraction (requires a model like qwen2.5-vl)
                # Ensure qwen2.5-vl is pulled for this to work well
                qwen_model = next((m['name'] for m in models if 'qwen' in m['name']), None)
                if qwen_model:
                    print(f"\nTesting text and coords extraction with {qwen_model}...")
                    text_coords = ollama_service.extract_text_and_coords(qwen_model, [dummy_image_path])
                    print(f"Extracted Text and Coords: {json.dumps(text_coords, indent=2)}")
                else:
                    print("\nQwen model not found, skipping text and coords extraction test.")

            else:
                print("No suitable vision model found for testing chat functions.")
        
        if os.path.exists(dummy_image_path):
            os.remove(dummy_image_path)

    except ConnectionError as e:
        print(f"Connection Error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
