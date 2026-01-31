import unittest
import os
import sys
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from unittest.mock import patch, MagicMock
import requests
from ollama_service import OllamaService

class TestOllamaService(unittest.TestCase):
    def setUp(self):
        self.mock_base_url = "http://mockhost:11434"
        self.ollama_service = OllamaService(base_url=self.mock_base_url)
        self.dummy_image_path = "dummy_test_image.png"
        with open(self.dummy_image_path, "w") as f:
            f.write("dummy image content")

    def tearDown(self):
        if os.path.exists(self.dummy_image_path):
            os.remove(self.dummy_image_path)

    @patch('ollama_service.requests.Session.request')
    def test_list_models_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llava:latest"}]}
        mock_request.return_value = mock_response

        models = self.ollama_service.list_models()
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]['name'], "llava:latest")

    @patch('ollama_service.requests.Session.request')
    def test_list_models_connection_error(self, mock_request):
        mock_request.side_effect = requests.exceptions.ConnectionError("Mocked error")
        with self.assertRaises(ConnectionError):
            self.ollama_service.list_models()

    @patch('ollama_service.requests.Session.request')
    @patch('ollama_service.OllamaService._encode_image')
    def test_chat_with_vision_model_success(self, mock_encode_image, mock_request):
        mock_encode_image.return_value = "base64_string"
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Response"}}
        mock_request.return_value = mock_response

        response = self.ollama_service.chat_with_vision_model("model", [self.dummy_image_path], "prompt")
        
        self.assertEqual(response['content'], "Response")
        sent_payload = mock_request.call_args[1]['json']
        self.assertEqual(sent_payload['model'], "model")
        self.assertEqual(sent_payload['messages'][0]['content'], "prompt")
        self.assertEqual(sent_payload['messages'][0]['images'][0], "base64_string")

    @patch('ollama_service.OllamaService.chat_with_vision_model')
    def test_extract_document_info_parsing(self, mock_chat):
        mock_chat.return_value = {"content": '{"company": "A", "title": "B", "date": "C"}'}
        info = self.ollama_service.extract_document_info("model", [], "keywords")
        self.assertEqual(info['company'], "A")
        self.assertEqual(info['title'], "B")
        self.assertEqual(info['date'], "C")

    @patch('ollama_service.OllamaService.chat_with_vision_model')
    def test_extract_document_info_bad_json(self, mock_chat):
        mock_chat.return_value = {"content": 'this is not json'}
        info = self.ollama_service.extract_document_info("model", [], "keywords")
        self.assertIsNone(info['company'])
        self.assertIsNone(info['title'])
        self.assertIsNone(info['date'])

if __name__ == '__main__':
    unittest.main()
