# utils/llm_interface.py

import asyncio
import logging
from typing import Optional, List
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI
from core.config import LLMConfig

logger = logging.getLogger(__name__)


class LLMInterface:
    """Interface for interacting with various LLM providers"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = None
        self._setup_client()

    def _setup_client(self):
        """Setup LLM client based on provider"""
        if self.config.provider == "openai":
            self.client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=float(getattr(self.config, "timeout", 60)),
            )
        elif self.config.provider == "azure":
            self.client = AsyncAzureOpenAI(
                azure_endpoint=self.config.base_url,
                api_key=self.config.api_key,
                api_version=getattr(self.config, 'api_version', '2025-04-01-preview'),
            )
            logger.info(f"Azure OpenAI client initialized: endpoint={self.config.base_url}, model={self.config.model_name}")
        elif self.config.provider == "anthropic":
            # Anthropic / Anthropic-compatible (e.g. MiniMax) endpoint
            #   provider: anthropic
            #   base_url: ENDPOINT_PLACEHOLDER
            #   api_key: <key>
            #   model_name: MiniMax-M2.1
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=float(getattr(self.config, "timeout", 60)),
                max_retries=0,
            )
            logger.info(f"Anthropic client initialized: base_url={self.config.base_url}, model={self.config.model_name}")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.provider}")

    async def generate_response(
        self, prompt: str, system_message: Optional[str] = None, **kwargs
    ) -> str:
        """
        Generate response from LLM

        Args:
            prompt: User prompt
            system_message: Optional system message
            **kwargs: Additional parameters

        Returns:
            Generated response text
        """
        for attempt in range(self.config.retry_attempts):
            try:
                if self.config.provider == "anthropic":
                    # Anthropic API: system is a top-level arg, not a message
                    params = {
                        "model": self.config.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": kwargs.get("temperature", self.config.temperature),
                        "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                    }
                    if system_message:
                        params["system"] = system_message
                    logger.debug(f"Anthropic request: model={params['model']}, max_tokens={params['max_tokens']}")
                    response = await asyncio.wait_for(
                        self.client.messages.create(**params),
                        timeout=self.config.timeout,
                    )
                    # Extract text from content blocks (skip thinking blocks)
                    parts = []
                    for block in response.content:
                        if getattr(block, 'type', None) == 'text':
                            parts.append(block.text)
                    content = "".join(parts)
                    if not content:
                        logger.warning("Anthropic returned no text content (maybe only thinking blocks)")
                    return content

                messages = []
                if system_message:
                    messages.append({"role": "system", "content": system_message})
                messages.append({"role": "user", "content": prompt})

                # Prepare parameters
                params = {
                    "model": self.config.model_name,
                    "messages": messages,
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                }

                logger.debug(f"LLM request: provider={self.config.provider}, model={params['model']}, "
                           f"temperature={params['temperature']}, max_tokens={params['max_tokens']}")

                # Both OpenAI and Azure use the same chat completions API
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(**params),
                    timeout=self.config.timeout,
                )

                content = response.choices[0].message.content
                logger.debug(f"LLM response received: {len(content) if content else 0} chars")
                logger.debug(f"LLM raw response: {response}")

                # Handle None or empty content
                if content is None:
                    logger.warning("LLM returned None content, using empty string")
                    content = ""

                return content

            except asyncio.TimeoutError:
                logger.warning(f"LLM request timeout on attempt {attempt + 1}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise

            except Exception as e:
                logger.warning(f"LLM request failed on attempt {attempt + 1}: {str(e)}")
                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise

        raise RuntimeError("All LLM request attempts failed")

    async def generate_batch_responses(
        self, prompts: List[str], system_message: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Generate responses for multiple prompts"""

        tasks = [
            self.generate_response(prompt, system_message, **kwargs)
            for prompt in prompts
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(
                    f"Failed to generate response for prompt {i}: {str(response)}"
                )
                results.append("")
            else:
                results.append(response)

        return results

    def validate_connection(self) -> bool:
        """Validate LLM connection and configuration"""
        try:
            # Simple test request
            test_response = asyncio.run(
                self.generate_response("Test connection", max_tokens=10)
            )
            return test_response is not None and len(test_response) > 0

        except Exception as e:
            logger.error(f"LLM connection validation failed: {str(e)}")
            return False
