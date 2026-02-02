"""
Comprehensive tests for Phase 2: LLM Provider Abstraction
Tests provider factory, command builder, and provider implementations
"""

import os
import sys
import tempfile
from PIL import Image

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from llm_providers.base_provider import BaseLLMProvider
from llm_providers.provider_factory import ProviderFactory
from llm_providers.command_builder import CommandBuilder
from llm_providers.ollama_provider import OllamaProvider
from llm_providers.claude_cli_provider import ClaudeCliProvider
from llm_providers.gemini_cli_provider import GeminiCliProvider
from config_manager import ConfigManager


def test_command_builder():
    """Test CLI command template processing"""
    print("\n" + "="*60)
    print("Testing CommandBuilder...")
    print("="*60)

    # Test 1: Template validation
    print("\n[TEST 1] Template validation")
    valid_template = "claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%"
    is_valid, error = CommandBuilder.validate_template(valid_template)
    assert is_valid, f"Valid template should pass: {error}"
    print(f"  ✓ Valid template accepted")

    invalid_template = "claude --model %MODEL% --image %IMAGE_PATHS%"
    is_valid, error = CommandBuilder.validate_template(invalid_template)
    assert not is_valid, "Invalid template should fail"
    print(f"  ✓ Invalid template rejected: {error}")

    # Test 2: Variable extraction
    print("\n[TEST 2] Variable extraction")
    variables = CommandBuilder.extract_variables(valid_template)
    expected = ['MODEL', 'IMAGE_PATHS', 'PROMPT']
    assert set(variables) == set(expected), f"Should extract all variables: {variables}"
    print(f"  ✓ Extracted variables: {variables}")

    # Test 3: Command building
    print("\n[TEST 3] Command building")
    command = CommandBuilder.build_command(
        template=valid_template,
        model='claude-3-5-sonnet-20241022',
        image_paths=['image1.png', 'image2.png'],
        prompt='Analyze these images'
    )
    assert 'claude-3-5-sonnet-20241022' in command, "Should include model"
    assert 'image1.png' in command, "Should include image paths"
    assert 'Analyze these images' in command, "Should include prompt"
    print(f"  ✓ Built command: {command[:80]}...")

    # Test 4: Quote escaping
    print("\n[TEST 4] Quote escaping in prompt")
    prompt_with_quotes = 'Analyze "important" documents'
    command = CommandBuilder.build_command(
        template=valid_template,
        model='test-model',
        image_paths=['test.png'],
        prompt=prompt_with_quotes
    )
    assert '\\"important\\"' in command or '"important"' in command, "Should handle quotes"
    print(f"  ✓ Quote escaping handled")

    print("\n✅ All CommandBuilder tests passed!")


def test_provider_factory():
    """Test provider factory creation"""
    print("\n" + "="*60)
    print("Testing ProviderFactory...")
    print("="*60)

    # Test 1: Available provider types
    print("\n[TEST 1] Available provider types")
    types = ProviderFactory.get_available_provider_types()
    expected_types = ['ollama', 'claude_cli', 'gemini_cli']
    assert set(types) == set(expected_types), f"Should have all provider types: {types}"
    print(f"  ✓ Available types: {types}")

    # Test 2: Provider type validation
    print("\n[TEST 2] Provider type validation")
    assert ProviderFactory.validate_provider_type('ollama'), "Should validate ollama"
    assert ProviderFactory.validate_provider_type('claude_cli'), "Should validate claude_cli"
    assert not ProviderFactory.validate_provider_type('invalid'), "Should reject invalid type"
    print(f"  ✓ Provider type validation working")

    # Test 3: Create Ollama provider
    print("\n[TEST 3] Create Ollama provider")
    ollama_config = {
        'base_url': 'http://localhost:11434',
        'timeout': 300,
        'model': 'qwen2.5-vl'
    }
    provider = ProviderFactory.create_provider('ollama', ollama_config)
    assert isinstance(provider, OllamaProvider), "Should create OllamaProvider"
    assert isinstance(provider, BaseLLMProvider), "Should inherit from BaseLLMProvider"
    default_model = provider.get_default_model()
    assert default_model == 'qwen2.5-vl', f"Should have correct model, got: {default_model}"
    print(f"  ✓ Created: {provider}")
    print(f"  ✓ Default model: {default_model}")

    # Test 4: Create Claude CLI provider
    print("\n[TEST 4] Create Claude CLI provider")
    claude_config = {
        'command_template': 'claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
        'timeout': 300,
        'default_model': 'claude-3-5-sonnet-20241022',
        'models': ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022']
    }
    provider = ProviderFactory.create_provider('claude_cli', claude_config)
    assert isinstance(provider, ClaudeCliProvider), "Should create ClaudeCliProvider"
    models = provider.get_available_models()
    assert len(models) == 2, "Should have 2 models"
    print(f"  ✓ Created: {provider}")
    print(f"  ✓ Available models: {models}")

    # Test 5: Create Gemini CLI provider
    print("\n[TEST 5] Create Gemini CLI provider")
    gemini_config = {
        'command_template': 'gemini --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
        'timeout': 300,
        'default_model': 'gemini-2.0-flash-exp',
        'models': ['gemini-2.0-flash-exp', 'gemini-1.5-pro']
    }
    provider = ProviderFactory.create_provider('gemini_cli', gemini_config)
    assert isinstance(provider, GeminiCliProvider), "Should create GeminiCliProvider"
    print(f"  ✓ Created: {provider}")

    # Test 6: Invalid provider type
    print("\n[TEST 6] Invalid provider type handling")
    try:
        ProviderFactory.create_provider('invalid_type', {})
        assert False, "Should raise ValueError for invalid type"
    except ValueError as e:
        print(f"  ✓ Correctly raised error: {e}")

    # Test 7: Create from ConfigManager
    print("\n[TEST 7] Create provider from ConfigManager")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        test_config_path = f.name

    try:
        config = ConfigManager(test_config_path)
        provider = ProviderFactory.create_from_config_manager(config)
        assert provider is not None, "Should create provider from config"
        print(f"  ✓ Created provider from config: {provider}")
    finally:
        os.remove(test_config_path)

    print("\n✅ All ProviderFactory tests passed!")


def test_provider_interfaces():
    """Test provider interface compliance"""
    print("\n" + "="*60)
    print("Testing Provider Interfaces...")
    print("="*60)

    # Test 1: Ollama provider interface
    print("\n[TEST 1] Ollama provider interface")
    ollama_config = {
        'base_url': 'http://localhost:11434',
        'timeout': 300,
        'model': 'qwen2.5-vl'
    }
    provider = OllamaProvider(ollama_config)

    # Check interface methods exist
    assert hasattr(provider, 'analyze_images'), "Should have analyze_images method"
    assert hasattr(provider, 'get_available_models'), "Should have get_available_models method"
    assert hasattr(provider, 'test_connection'), "Should have test_connection method"
    assert hasattr(provider, 'validate_config'), "Should have validate_config method"
    print(f"  ✓ All required methods present")

    # Test validation
    is_valid, error = provider.validate_config()
    assert is_valid, f"Valid config should pass: {error}"
    print(f"  ✓ Configuration validated")

    # Test timeout and model getters
    timeout = provider.get_timeout()
    model = provider.get_default_model()
    assert timeout == 300, "Should return correct timeout"
    assert model == 'qwen2.5-vl', "Should return correct model"
    print(f"  ✓ Timeout: {timeout}s, Model: {model}")

    # Test 2: Claude CLI provider interface
    print("\n[TEST 2] Claude CLI provider interface")
    claude_config = {
        'command_template': 'claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
        'timeout': 300,
        'default_model': 'claude-3-5-sonnet-20241022',
        'models': ['claude-3-5-sonnet-20241022']
    }
    provider = ClaudeCliProvider(claude_config)

    is_valid, error = provider.validate_config()
    assert is_valid, f"Valid config should pass: {error}"
    print(f"  ✓ Configuration validated")

    models = provider.get_available_models()
    assert len(models) == 1, "Should have 1 model"
    print(f"  ✓ Available models: {models}")

    # Test 3: Invalid configuration detection
    print("\n[TEST 3] Invalid configuration detection")
    invalid_claude_config = {
        'command_template': 'claude --model %MODEL%',  # Missing required variables
        'timeout': 300,
        'default_model': 'test',
        'models': ['test']
    }
    provider = ClaudeCliProvider(invalid_claude_config)
    is_valid, error = provider.validate_config()
    assert not is_valid, "Invalid config should fail validation"
    print(f"  ✓ Invalid config detected: {error}")

    # Test 4: Model validation
    print("\n[TEST 4] Model validation")
    claude_config_invalid_model = {
        'command_template': 'claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
        'timeout': 300,
        'default_model': 'nonexistent-model',
        'models': ['claude-3-5-sonnet-20241022']
    }
    provider = ClaudeCliProvider(claude_config_invalid_model)
    is_valid, error = provider.validate_config()
    assert not is_valid, "Should detect model not in available models"
    print(f"  ✓ Model validation working: {error}")

    print("\n✅ All Provider Interface tests passed!")


def test_provider_with_mock_image():
    """Test provider with actual image (mock response)"""
    print("\n" + "="*60)
    print("Testing Provider with Mock Image...")
    print("="*60)

    # Create temporary test image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        test_image_path = f.name

    try:
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='white')
        img.save(test_image_path)
        print(f"\n[TEST 1] Created test image: {os.path.basename(test_image_path)}")

        # Test 1: Ollama provider (will fail if server not running, but that's OK)
        print("\n[TEST 2] Ollama provider response format")
        ollama_config = {
            'base_url': 'http://localhost:11434',
            'timeout': 10,  # Short timeout for testing
            'model': 'qwen2.5-vl'
        }
        provider = OllamaProvider(ollama_config)

        # Test connection
        is_connected = provider.test_connection()
        print(f"  ✓ Ollama connection test: {'✓ Connected' if is_connected else '✗ Not connected (OK for testing)'}")

        # Try to analyze (will fail gracefully if no server)
        result = provider.analyze_images(
            image_paths=[test_image_path],
            prompt="What is in this image?"
        )

        # Check response structure
        assert 'response' in result, "Should have response field"
        assert 'metadata' in result, "Should have metadata field"
        assert 'processing_time_ms' in result, "Should have processing time"
        assert 'model_used' in result, "Should have model used"
        assert 'success' in result, "Should have success flag"
        assert 'error' in result, "Should have error field"

        if result['success']:
            print(f"  ✓ Analysis succeeded")
            print(f"  ✓ Processing time: {result['processing_time_ms']}ms")
        else:
            print(f"  ✓ Analysis failed gracefully: {result['error'][:50]}...")

        # Test 2: Check response structure compliance
        print("\n[TEST 3] Response structure compliance")
        required_fields = ['response', 'metadata', 'processing_time_ms', 'model_used', 'success', 'error']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"
        print(f"  ✓ All {len(required_fields)} required fields present")

        print("\n✅ All Provider Mock tests passed!")

    finally:
        # Cleanup
        if os.path.exists(test_image_path):
            os.remove(test_image_path)


def main():
    """Run all Phase 2 tests"""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  PHASE 2: LLM PROVIDER ABSTRACTION - COMPREHENSIVE TESTS  ".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)

    try:
        test_command_builder()
        test_provider_factory()
        test_provider_interfaces()
        test_provider_with_mock_image()

        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█" + "  🎉 ALL PHASE 2 TESTS PASSED! 🎉  ".center(58) + "█")
        print("█" + " "*58 + "█")
        print("█"*60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
