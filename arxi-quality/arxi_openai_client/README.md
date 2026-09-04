# Arxi OpenAI Client

## Overview

This module provides a secure and reusable OpenAI API client wrapper for Odoo modules. It centralizes OpenAI API calls and allows the code to be obfuscated for security purposes.

## Features

- **Centralized API Key Management**: API keys are stored in Odoo system parameters instead of hardcoded in the code
- **Reusable Client**: Can be used by any Odoo module that needs OpenAI functionality
- **Obfuscation Ready**: Designed to be easily obfuscated to protect API keys and business logic
- **Multiple Use Cases**: Supports various OpenAI operations including:
  - Chat completions
  - Module analysis
  - Text generation

## Installation

1. Copy the module to your Odoo addons directory
2. Update the app list in Odoo
3. Install the module: `arxi_openai_client`

## Configuration

The OpenAI API key is hardcoded in the module for security through obfuscation.

Optionally, you can configure:
1. Go to **Settings** → **Technical** → **Parameters** → **System Parameters**
2. Configure `arxi.openai.default_model` (default: `gpt-5-nano`)

## Usage

### Basic Usage in Python Code

```python
# Get the OpenAI client
openai_client = self.env['arxi.openai.client']

# Make a simple chat completion
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello, how are you?"}
]
response = openai_client.chat_completion(messages)
print(response)
```

### Analyze Odoo Modules

```python
# Analyze an Odoo module
openai_client = env['arxi.openai.client']
description = openai_client.analyze_odoo_module(
    module_name='my_module',
    manifest_content=manifest_text,
    readme_content=readme_text,
    language='pt-PT'  # or 'en', 'es', 'fr'
)
```

### Generate Text

```python
# Generate text with custom prompts
openai_client = env['arxi.openai.client']
result = openai_client.generate_text(
    prompt="Explain quantum computing in simple terms",
    system_prompt="You are a science teacher explaining complex topics simply",
    temperature=0.7,
    max_tokens=500
)
```

### Advanced Chat Completion

```python
# Make a chat completion with custom parameters
openai_client = env['arxi.openai.client']
response = openai_client.chat_completion(
    messages=[
        {"role": "system", "content": "You are a technical analyst."},
        {"role": "user", "content": "Analyze this code..."}
    ],
    model="gpt-4",  # Override default model
    temperature=0.5,
    max_tokens=1000
)
```

## API Reference

### Methods

#### `chat_completion(messages, model=None, temperature=None, max_tokens=None, **kwargs)`

Make a chat completion API call to OpenAI.

**Parameters:**
- `messages` (list): List of message dicts with 'role' and 'content' keys
- `model` (str, optional): Model to use. Defaults to configured default model.
- `temperature` (float, optional): Sampling temperature
- `max_tokens` (int, optional): Maximum tokens to generate
- `**kwargs`: Additional parameters to pass to the API

**Returns:** str - The response content from OpenAI

#### `analyze_odoo_module(module_name, manifest_content, readme_content, language='pt-PT')`

Analyze an Odoo module and generate a description using OpenAI.

**Parameters:**
- `module_name` (str): Name of the module
- `manifest_content` (str): Content of __manifest__.py file
- `readme_content` (str): Content of README.md file
- `language` (str, optional): Language for the response ('pt-PT', 'en', 'es', 'fr')

**Returns:** str - AI-generated description of the module

#### `generate_text(prompt, system_prompt=None, model=None, temperature=0.7, max_tokens=None)`

Generate text using OpenAI chat completion.

**Parameters:**
- `prompt` (str): The user prompt
- `system_prompt` (str, optional): System prompt to set context
- `model` (str, optional): Model to use
- `temperature` (float, optional): Sampling temperature. Defaults to 0.7.
- `max_tokens` (int, optional): Maximum tokens to generate

**Returns:** str - Generated text

## Security and Obfuscation

This module has the API key hardcoded and is designed to be obfuscated to protect:
- API keys and credentials (hardcoded in the module)
- Business logic
- Proprietary prompts and system messages

**Important:** The API key is stored in plaintext in `models/openai_client.py`. You MUST obfuscate this module before distribution.

To obfuscate the module:
1. Use Python obfuscation tools (e.g., pyarmor, cython)
2. Compile the Python files to .pyc or .pyd
3. Distribute only the obfuscated version

Example with pyarmor:
```bash
cd /home/andresilva/odoo/odoo18/custom/
pyarmor gen -O arxi_openai_client_obf arxi_openai_client/
```

## Dependencies

- `openai` Python package
- Odoo base module

## License

LGPL-3

## Author

Arxi - https://www.arxi.pt
