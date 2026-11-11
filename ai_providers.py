"""
ShipSage AI Providers - Abstract interface for multiple AI backends
Supports: IBM watsonx, OpenAI, Anthropic, Ollama (local), and rule-based fallback
"""
from abc import ABC, abstractmethod
from typing import Optional
import httpx
import asyncio


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, api_key: str = "", **kwargs):
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    async def analyze(self, prompt: str) -> Optional[str]:
        """Generate analysis from prompt."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return provider name."""
        pass
    
    @abstractmethod
    def get_cost_per_1k_tokens(self) -> float:
        """Return approximate cost per 1000 tokens."""
        pass


class WatsonxProvider(AIProvider):
    """IBM watsonx Granite provider."""
    
    def __init__(self, api_key: str = "", project_id: str = ""):
        super().__init__(api_key)
        self.project_id = project_id
        self.url = "https://us-south.ml.cloud.ibm.com/ml/v1/text/generation?version=2023-05-29"
        self.model = "ibm/granite-13b-instruct-v2"
    
    async def get_iam_token(self) -> Optional[str]:
        """Get IBM Cloud IAM token."""
        if not self.api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    'https://iam.cloud.ibm.com/identity/token',
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    data=f'grant_type=urn:ibm:params:oauth:grant-type:apikey&apikey={self.api_key}'
                )
                if resp.status_code == 200:
                    return resp.json().get('access_token')
        except Exception:
            pass
        return None
    
    async def analyze(self, prompt: str) -> Optional[str]:
        """Call IBM watsonx Granite model."""
        token = await self.get_iam_token()
        if not token or not self.project_id:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.url,
                    headers={
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    json={
                        "model_id": self.model,
                        "input": prompt,
                        "parameters": {
                            "decoding_method": "greedy",
                            "max_new_tokens": 600,
                            "stop_sequences": ["###", "---END---"]
                        },
                        "project_id": self.project_id
                    }
                )
                if resp.status_code == 200:
                    results = resp.json().get('results', [])
                    if results:
                        return results[0].get('generated_text', '').strip()
        except Exception:
            pass
        return None
    
    def get_name(self) -> str:
        return "IBM watsonx Granite"
    
    def get_cost_per_1k_tokens(self) -> float:
        return 0.0  # Free tier or enterprise pricing


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: str = "", model: str = "gpt-4-turbo"):
        super().__init__(api_key)
        self.model = model
        self.url = "https://api.openai.com/v1/chat/completions"
    
    async def analyze(self, prompt: str) -> Optional[str]:
        """Call OpenAI API."""
        if not self.api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.url,
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a senior software engineer analyzing code repositories."},
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.7
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data['choices'][0]['message']['content'].strip()
        except Exception:
            pass
        return None
    
    def get_name(self) -> str:
        return f"OpenAI {self.model}"
    
    def get_cost_per_1k_tokens(self) -> float:
        costs = {
            "gpt-4-turbo": 0.01,
            "gpt-4": 0.03,
            "gpt-3.5-turbo": 0.0015
        }
        return costs.get(self.model, 0.01)


class AnthropicProvider(AIProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: str = "", model: str = "claude-3-sonnet-20240229"):
        super().__init__(api_key)
        self.model = model
        self.url = "https://api.anthropic.com/v1/messages"
    
    async def analyze(self, prompt: str) -> Optional[str]:
        """Call Anthropic API."""
        if not self.api_key:
            return None
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self.url,
                    headers={
                        'x-api-key': self.api_key,
                        'anthropic-version': '2023-06-01',
                        'Content-Type': 'application/json'
                    },
                    json={
                        "model": self.model,
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data['content'][0]['text'].strip()
        except Exception:
            pass
        return None
    
    def get_name(self) -> str:
        return f"Anthropic {self.model.split('-')[1].title()}"
    
    def get_cost_per_1k_tokens(self) -> float:
        costs = {
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
            "claude-3-haiku": 0.00025
        }
        for key, cost in costs.items():
            if key in self.model:
                return cost
        return 0.003


class OllamaProvider(AIProvider):
    """Ollama local LLM provider."""
    
    def __init__(self, model: str = "llama3", endpoint: str = "http://localhost:11434"):
        super().__init__()
        self.model = model
        self.endpoint = endpoint
    
    async def analyze(self, prompt: str) -> Optional[str]:
        """Call local Ollama API."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.endpoint}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get('response', '').strip()
        except Exception:
            pass
        return None
    
    def get_name(self) -> str:
        return f"Ollama {self.model}"
    
    def get_cost_per_1k_tokens(self) -> float:
        return 0.0  # Local, no cost


class RuleBasedProvider(AIProvider):
    """Fallback rule-based provider (no AI)."""
    
    def __init__(self):
        super().__init__()
    
    async def analyze(self, prompt: str) -> Optional[str]:
        """Return None to trigger rule-based fallback."""
        return None
    
    def get_name(self) -> str:
        return "Rule-based Analysis"
    
    def get_cost_per_1k_tokens(self) -> float:
        return 0.0


class AIProviderFactory:
    """Factory for creating AI providers."""
    
    @staticmethod
    def create_provider(provider_type: str, **kwargs) -> AIProvider:
        """
        Create an AI provider instance.
        
        Args:
            provider_type: One of 'watsonx', 'openai', 'anthropic', 'ollama', 'rule-based'
            **kwargs: Provider-specific configuration
        
        Returns:
            AIProvider instance
        """
        providers = {
            'watsonx': WatsonxProvider,
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
            'ollama': OllamaProvider,
            'rule-based': RuleBasedProvider
        }
        
        provider_class = providers.get(provider_type.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_type}")
        
        return provider_class(**kwargs)
    
    @staticmethod
    def get_available_providers() -> list:
        """Return list of available providers with metadata."""
        return [
            {
                "id": "watsonx",
                "name": "IBM watsonx Granite",
                "description": "Enterprise-grade AI from IBM",
                "requires_api_key": True,
                "cost_per_1k": 0.0,
                "features": ["Code analysis", "Architecture insights", "Best practices"]
            },
            {
                "id": "openai",
                "name": "OpenAI GPT-4",
                "description": "Advanced language model from OpenAI",
                "requires_api_key": True,
                "cost_per_1k": 0.01,
                "features": ["Deep code understanding", "Context-aware", "Multi-language"]
            },
            {
                "id": "anthropic",
                "name": "Anthropic Claude",
                "description": "Constitutional AI with strong reasoning",
                "requires_api_key": True,
                "cost_per_1k": 0.003,
                "features": ["Long context", "Detailed analysis", "Safety-focused"]
            },
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "description": "Run LLMs locally on your machine",
                "requires_api_key": False,
                "cost_per_1k": 0.0,
                "features": ["Privacy", "No API costs", "Offline capable"]
            },
            {
                "id": "rule-based",
                "name": "Rule-based",
                "description": "Smart heuristics without AI",
                "requires_api_key": False,
                "cost_per_1k": 0.0,
                "features": ["Fast", "Deterministic", "Always available"]
            }
        ]


async def test_provider(provider: AIProvider) -> dict:
    """Test if a provider is working."""
    test_prompt = "Say 'OK' if you can read this."
    
    try:
        result = await asyncio.wait_for(provider.analyze(test_prompt), timeout=10.0)
        return {
            "provider": provider.get_name(),
            "status": "available" if result else "unavailable",
            "response": result[:50] if result else None
        }
    except asyncio.TimeoutError:
        return {
            "provider": provider.get_name(),
            "status": "timeout",
            "response": None
        }
    except Exception as e:
        return {
            "provider": provider.get_name(),
            "status": "error",
            "response": str(e)[:50]
        }

# Made with Bob
