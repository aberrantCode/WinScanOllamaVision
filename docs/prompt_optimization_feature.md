# Prompt Optimization Feature - Implementation Summary

## Overview

The Prompt Optimization feature allows users to improve their document analysis prompts using AI. The feature sends the current prompt to the active LLM provider (Ollama, Claude CLI, or Gemini CLI) and receives an optimized version with better clarity and structure while preserving JSON schema requirements.

## Implementation Details

### Files Modified

- **src/settings_window_enhanced.py**
  - Added `PromptOptimizationThread` class for background processing
  - Added `PromptComparisonDialog` class for before/after comparison
  - Replaced placeholder `_optimize_prompt()` method with full implementation
  - Added `_handle_optimization_result()` method for result processing

### Key Components

#### 1. PromptOptimizationThread (QThread)

Background worker thread that:
- Gets the active LLM provider from config
- Sends optimization request to the provider
- Handles provider-specific behavior:
  - **Ollama**: Uses subprocess to call `ollama run` for text-only chat
  - **Claude CLI / Gemini CLI**: Uses `analyze_images()` with empty image list
- Emits `finished` signal with results

**Optimization Prompt Template:**
```
You are an AI prompt engineer. Improve this prompt for better responses from vision models.
Keep the JSON schema requirements intact. Return ONLY the improved prompt.

Current prompt:
{current_prompt}
```

#### 2. PromptComparisonDialog (QDialog)

Dialog window showing:
- **Left side**: Original prompt (read-only)
- **Right side**: Optimized prompt (editable)
- User can:
  - Review the AI's suggestions
  - Edit the optimized prompt before accepting
  - Accept changes (updates prompt editor)
  - Cancel (preserves original prompt)

#### 3. Enhanced _optimize_prompt() Method

Main method triggered by "Optimize Prompt" button:
1. **Validation**
   - Checks prompt is not empty
   - Gets active provider configuration
2. **Confirmation**
   - Shows dialog with provider name
   - User confirms before sending request
3. **Progress Indication**
   - Shows non-blocking progress dialog
   - Indicates request may take 10-60 seconds
4. **Background Processing**
   - Creates and starts optimization thread
   - Connects to result handler
5. **Result Handling**
   - On success: Shows comparison dialog
   - On failure: Shows detailed error message

### Error Handling

The implementation handles multiple error scenarios:

1. **Empty Prompt**
   - Shows warning dialog
   - Does not proceed with optimization

2. **Provider Not Configured**
   - Shows configuration error
   - Guides user to check settings

3. **LLM Connection Failure**
   - Shows error with connection details
   - Suggests checking provider configuration

4. **Request Timeout**
   - Shows timeout error
   - Suggests increasing timeout in settings

5. **Invalid Response**
   - Shows warning if response is empty
   - Suggests trying again or manual edit

6. **Provider-Specific Errors**
   - Detects image requirement issues
   - Provides helpful error messages

## Provider Support

### Ollama
- Uses direct subprocess call: `ollama run {model} {prompt}`
- Supports text-only optimization without images
- Works with any Ollama text/vision model

### Claude CLI
- Uses `analyze_images()` with empty image list
- Command template supports text-only prompts
- Falls back gracefully if images required

### Gemini CLI
- Uses `analyze_images()` with empty image list
- Command template supports text-only prompts
- Falls back gracefully if images required

## User Interface Flow

```
[User clicks "Optimize Prompt"]
          ↓
[Validation: Check prompt not empty]
          ↓
[Confirmation: "Send to {provider}?"]
          ↓ (User confirms)
[Progress Dialog: "Optimizing..."]
          ↓
[Background Thread: Send to LLM]
          ↓
[Success] → [Comparison Dialog]
          ↓
[User reviews/edits] → [Accept/Cancel]
          ↓ (Accept)
[Prompt Updated] → [Info: "Don't forget to save"]
```

## Testing

### Unit Tests
**File**: `tests/test_prompt_optimization.py`

Tests:
- ✅ Thread creation
- ✅ Comparison dialog creation
- ✅ Success flow with mock provider
- ✅ Failure handling
- ✅ Ollama-specific subprocess behavior
- ✅ UI element validation

### Integration Tests
**File**: `tests/test_prompt_optimization_integration.py`

Tests:
- ✅ Empty prompt warning
- ✅ Confirmation dialog
- ✅ Successful optimization flow
- ✅ Error dialog on failure
- ✅ User editing capability
- ✅ All three providers supported

### Manual Testing
**Script**: `scripts/test_prompt_optimization_manual.py`

Run with:
```bash
python scripts/test_prompt_optimization_manual.py
```

## Usage Instructions

### For Users

1. Open **Settings** → **LLM Provider** tab
2. Ensure active provider is configured and running
3. Locate prompt editor (e.g., "Document Validation Prompt")
4. Click **"Optimize Prompt"** button
5. Confirm sending prompt to LLM
6. Wait 10-60 seconds for optimization
7. Review the before/after comparison
8. Optionally edit the optimized version
9. Click **OK** to accept or **Cancel** to keep original
10. Click **OK** in settings to save changes

### For Developers

#### Adding New Providers

To support additional LLM providers:

1. Add provider case in `PromptOptimizationThread.run()`:
```python
elif active_provider_name == 'new_provider':
    # Custom text-only request logic
    result = provider.text_only_method(prompt)
```

2. Ensure provider implements text-only support or workaround

#### Customizing Optimization Prompt

Modify the optimization request in `PromptOptimizationThread.run()`:
```python
optimization_request = (
    "Your custom instruction here.\n\n"
    f"Current prompt:\n{self.current_prompt}"
)
```

## Configuration Requirements

### Ollama
- Ollama service must be running
- Default: `http://localhost:11434`
- Model must support text chat (e.g., qwen2.5-vl, llama3, gemma)

### Claude CLI
- `claude` command must be in PATH
- Command template must be configured
- API key must be set up

### Gemini CLI
- `gemini` command must be in PATH
- Command template must be configured
- API key must be set up

## Known Limitations

1. **Timeout**: Long prompts may take longer to optimize
   - Default timeout: 300 seconds
   - Can be increased in provider settings

2. **Network Dependency**: Requires active connection to LLM provider
   - Offline mode not supported

3. **Cost**: CLI providers may incur API costs
   - Consider using Ollama for free local optimization

4. **Language**: Currently optimizes for English prompts
   - Multilingual support depends on model

## Future Enhancements

Potential improvements:
- [ ] Batch optimization of all prompts
- [ ] History of optimizations with rollback
- [ ] A/B testing of prompt variations
- [ ] Automatic prompt scoring and suggestions
- [ ] Template library of optimized prompts
- [ ] Export/import optimized prompts

## Troubleshooting

### "Cannot optimize an empty prompt"
**Solution**: Enter a prompt before optimizing

### "Failed to get active provider"
**Solution**: Select a provider in LLM Provider dropdown

### "Cannot connect to the LLM provider"
**Solution**:
- Check Ollama service is running: `ollama list`
- Check Claude CLI works: `claude --version`
- Verify network connection

### "Request timed out"
**Solution**: Increase timeout in provider settings

### "The current provider may require image inputs"
**Solution**: Provider doesn't support text-only optimization
- Try Ollama for text-only support
- Or use manual editing

## Related Documentation

- `docs/phase6_multi_provider_support.md` - Provider architecture
- `docs/phase9_modern_ui_redesign.md` - UI design patterns
- `src/llm_providers/README.md` - Provider implementation details
