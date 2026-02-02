"""Simple test runner for phases 1-3"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

print("\n" + "="*70)
print("TESTING PHASES 1-3")
print("="*70)

passed = 0
failed = 0

# Test Phase 1
print("\n>>> Phase 1: Database Foundation")
try:
    from metadata_db import MetadataDB
    from analysis_db import AnalysisDB
    from config_manager import ConfigManager
    import tempfile

    print("\n[TEST] MetadataDB creation")
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name
    db = MetadataDB(test_db)
    version = db.get_schema_version()
    assert version >= 1
    db.close()
    os.remove(test_db)
    print("  [OK] MetadataDB works, schema version:", version)

    print("\n[TEST] AnalysisDB creation")
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name
    db = AnalysisDB(test_db)
    stats = db.get_extended_statistics()
    assert 'total_analyzed_pages' in stats
    db.close()
    os.remove(test_db)
    print("  [OK] AnalysisDB works")

    print("\n[TEST] ConfigManager")
    with tempfile.NamedTemporaryFile(suffix='.ini', delete=False) as f:
        test_config = f.name
    config = ConfigManager(test_config)
    provider = config.get_active_provider()
    assert provider in ['ollama', 'claude_cli', 'gemini_cli']
    os.remove(test_config)
    print("  [OK] ConfigManager works, active provider:", provider)

    print("[PASS] Phase 1")
    passed += 1
except Exception as e:
    print(f"[FAIL] Phase 1: {e}")
    import traceback
    traceback.print_exc()
    failed += 1

# Test Phase 2
print("\n>>> Phase 2: LLM Provider Abstraction")
try:
    from llm_providers.provider_factory import ProviderFactory
    from llm_providers.command_builder import CommandBuilder

    print("\n[TEST] CommandBuilder")
    template = "claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%"
    is_valid, error = CommandBuilder.validate_template(template)
    assert is_valid, f"Template validation failed: {error}"
    print("  [OK] CommandBuilder validation works")

    print("\n[TEST] OllamaProvider")
    config = {
        'base_url': 'http://localhost:11434',
        'timeout': 300,
        'model': 'qwen2.5-vl'
    }
    provider = ProviderFactory.create_provider('ollama', config)
    default_model = provider.get_default_model()
    assert default_model == 'qwen2.5-vl', f"Model mismatch: got {default_model}"
    print("  [OK] OllamaProvider created, model:", default_model)

    print("\n[TEST] ProviderFactory")
    types = ProviderFactory.get_available_provider_types()
    assert all(t in types for t in ['ollama', 'claude_cli', 'gemini_cli'])
    print("  [OK] Factory has all types:", types)

    print("[PASS] Phase 2")
    passed += 1
except Exception as e:
    print(f"[FAIL] Phase 2: {e}")
    import traceback
    traceback.print_exc()
    failed += 1

# Test Phase 3
print("\n>>> Phase 3: Analysis & Bundling Services")
try:
    from analysis_service import AnalysisService
    from bundling_service import BundlingService
    from analysis_db import AnalysisDB
    from metadata_db import MetadataDB
    from config_manager import ConfigManager
    import tempfile
    import time

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name
    with tempfile.NamedTemporaryFile(suffix='.ini', delete=False) as f:
        test_config = f.name

    try:
        print("\n[TEST] Service initialization")
        config = ConfigManager(test_config)
        analysis_db = AnalysisDB(test_db)
        metadata_db = MetadataDB(test_db)

        analysis_svc = AnalysisService(config, analysis_db, metadata_db)
        bundling_svc = BundlingService(analysis_db)
        print("  [OK] Services created")

        print("\n[TEST] Analysis data storage")
        test_data = {
            'file_path': 'test1.png',
            'company': 'Test Corp',
            'document_type': 'Invoice',
            'page_number': 1,
            'confidence_score': 0.9
        }
        analysis_db.save_analysis(
            file_path=test_data['file_path'],
            file_hash='hash1',
            provider_name='test',
            model_name='test',
            analysis_data=test_data,
            raw_response='{}',
            processing_time_ms=100
        )
        print("  [OK] Mock data saved")

        print("\n[TEST] Bundling recommendations")
        bundles = bundling_svc.generate_bundle_recommendations()
        print("  [OK] Bundling service works, bundles:", len(bundles))

        analysis_db.close()
        metadata_db.close()
        time.sleep(0.5)
        os.remove(test_db)
        os.remove(test_config)

    except Exception as e:
        for path in [test_db, test_config]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
        raise e

    print("[PASS] Phase 3")
    passed += 1
except Exception as e:
    print(f"[FAIL] Phase 3: {e}")
    import traceback
    traceback.print_exc()
    failed += 1

# Summary
print("\n" + "="*70)
print(f"SUMMARY: {passed} passed, {failed} failed out of 3 phases")
print("="*70 + "\n")

exit(0 if failed == 0 else 1)
