from __future__ import annotations

from typing import Any, Literal, cast, AsyncIterable
from contextlib import asynccontextmanager
import logging

from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings, OpenAIStreamedResponse
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ModelRequest,
    ModelResponsePart,
    ThinkingPart,
    TextPart,
    ToolCallPart,
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    SystemPromptPart,
    UserPromptPart,
    ToolReturnPart,
    RetryPromptPart,
    ModelResponseStreamEvent,
    PartStartEvent
)
from pydantic_ai import usage
from pydantic_ai.settings import ModelSettings
from pydantic_ai.models import ModelRequestParameters, StreamedResponse
from pydantic_ai._run_context import RunContext
from openai.types import chat
from openai.types.chat import ChatCompletionMessageParam
from typing_extensions import assert_never

logger = logging.getLogger(__name__)

class OpenRouterGeminiStreamedResponse(OpenAIStreamedResponse):
    """
    Custom StreamedResponse for OpenRouter Gemini models to capture reasoning_details.
    """
    
    async def _get_event_iterator(self) -> AsyncIterable[ModelResponseStreamEvent]:
        # Import parent's _map_usage function
        from pydantic_ai.models.openai import _map_usage
        
        async for chunk in self._response:
            self._usage += _map_usage(chunk, self._provider_name, self._provider_url, self._model_name)

            if chunk.id:
                self.provider_response_id = chunk.id

            if chunk.model:
                self._model_name = chunk.model

            try:
                choice = chunk.choices[0]
            except IndexError:
                continue

            # Check for reasoning_details in the chunk
            # OpenRouter might send it in the delta or the choice object
            reasoning_details = getattr(choice, "reasoning_details", None) or getattr(choice.delta, "reasoning_details", None)
            
            if reasoning_details:
                if self.provider_details is None:
                    self.provider_details = {}
                self.provider_details["reasoning_details"] = reasoning_details
                # logger.debug(f"Captured streaming reasoning_details: {reasoning_details}")

            # Call parent's logic for standard processing
            # We can't easily call super()._get_event_iterator() because it's an async generator
            # So we have to replicate the logic or find a way to wrap it.
            # Replicating logic is safer to ensure we don't miss anything, 
            # but it's brittle if parent changes. 
            # However, since we just want to capture side effects (provider_details), 
            # maybe we can iterate over the parent's iterator?
            # BUT parent iterates over self._response which is an iterator that gets consumed.
            # So we cannot iterate over it twice.
            
            # Actually, we are iterating over self._response HERE.
            # So we must implement the full logic.
            
            # ... Copying logic from OpenAIStreamedResponse._get_event_iterator ...
            
            if choice.delta is None:
                continue

            if raw_finish_reason := choice.finish_reason:
                if self.provider_details is None:
                    self.provider_details = {}
                self.provider_details['finish_reason'] = raw_finish_reason
                # Ensure reasoning_details is preserved if we set it earlier
                # (It should be, as we are modifying the same dict if it exists)
                
                from pydantic_ai.models.openai import _CHAT_FINISH_REASON_MAP
                self.finish_reason = _CHAT_FINISH_REASON_MAP.get(raw_finish_reason)

            # Handle the text part of the response
            content = choice.delta.content
            if content is not None:
                maybe_event = self._parts_manager.handle_text_delta(
                    vendor_part_id='content',
                    content=content,
                    thinking_tags=self._model_profile.thinking_tags,
                    ignore_leading_whitespace=self._model_profile.ignore_streamed_leading_whitespace,
                )
                if maybe_event is not None:
                    if isinstance(maybe_event, PartStartEvent) and isinstance(maybe_event.part, ThinkingPart):
                         # Fix for PartStartEvent with ThinkingPart
                         maybe_event.part.id = 'content'
                         maybe_event.part.provider_name = self.provider_name
                    yield maybe_event

            # The `reasoning_content` field is only present in DeepSeek models.
            if reasoning_content := getattr(choice.delta, 'reasoning_content', None):
                yield self._parts_manager.handle_thinking_delta(
                    vendor_part_id='reasoning_content',
                    id='reasoning_content',
                    content=reasoning_content,
                    provider_name=self.provider_name,
                )

            for dtc in choice.delta.tool_calls or []:
                maybe_event = self._parts_manager.handle_tool_call_delta(
                    vendor_part_id=dtc.index,
                    tool_name=dtc.function and dtc.function.name,
                    args=dtc.function and dtc.function.arguments,
                    tool_call_id=dtc.id,
                )
                if maybe_event is not None:
                    yield maybe_event

class OpenRouterGeminiModel(OpenAIChatModel):
    """
    Custom OpenAIChatModel for OpenRouter Gemini models that require
    preservation of 'reasoning_details' (thinking blocks).
    """
    
    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
        run_context: RunContext[Any] | None = None,
    ) -> AsyncIterator[StreamedResponse]:
        # We need to call the parent's _completions_create with stream=True
        # But we can't call super().request_stream because it returns OpenAIStreamedResponse
        # So we replicate the logic of request_stream but return our custom response class
        
        from pydantic_ai.models.openai import check_allow_model_requests, OpenAIChatModelSettings
        from pydantic_ai._utils import number_to_datetime, PeekableAsyncStream, Unset
        
        check_allow_model_requests()
        response = await self._completions_create(
            messages, True, cast(OpenAIChatModelSettings, model_settings or {}), model_request_parameters
        )
        
        async with response:
            # Logic from _process_streamed_response
            peekable_response = PeekableAsyncStream(response)
            first_chunk = await peekable_response.peek()
            if isinstance(first_chunk, Unset):
                 # Should raise UnexpectedModelBehavior but we need to import it
                 from pydantic_ai import UnexpectedModelBehavior
                 raise UnexpectedModelBehavior('Streamed response ended without content or tool calls')

            model_name = first_chunk.model or self._model_name

            yield OpenRouterGeminiStreamedResponse(
                model_request_parameters=model_request_parameters,
                _model_name=model_name,
                _model_profile=self.profile,
                _response=peekable_response,
                _timestamp=number_to_datetime(first_chunk.created),
                _provider_name=self._provider.name,
                _provider_url=self._provider.base_url,
            )

    def _process_response(self, response: chat.ChatCompletion | str) -> ModelResponse:
        """
        Process the response and extract reasoning_details if present.
        """
        # Call the parent method to get the standard ModelResponse
        model_response = super()._process_response(response)

        # If it's a ChatCompletion, check for reasoning_details
        if isinstance(response, chat.ChatCompletion):
            choice = response.choices[0]
            message = choice.message
            
            # Check for reasoning_details (OpenRouter specific)
            # Note: The openai library might not have this field typed, so we access it dynamically
            reasoning_details = getattr(message, "reasoning_details", None)
            
            if reasoning_details:
                # Store reasoning_details in provider_details
                if model_response.provider_details is None:
                    model_response.provider_details = {}
                
                model_response.provider_details["reasoning_details"] = reasoning_details
                logger.debug(f"Captured reasoning_details for {self.model_name}")

        return model_response

    async def _map_messages(self, messages: list[ModelMessage], model_request_parameters: ModelRequestParameters | None = None) -> list[ChatCompletionMessageParam]:
        """
        Map messages to OpenAI format, injecting reasoning_details for Assistant messages.
        """
        openai_messages: list[ChatCompletionMessageParam] = []
        
        for message in messages:
            if isinstance(message, ModelRequest):
                # Use parent's logic for user/system messages
                async for item in self._map_user_message(message):
                    openai_messages.append(item)
            
            elif isinstance(message, ModelResponse):
                # Custom logic for Assistant messages to include reasoning_details
                texts: list[str] = []
                tool_calls: list[chat.ChatCompletionMessageFunctionToolCallParam] = []
                
                for item in message.parts:
                    if isinstance(item, TextPart):
                        texts.append(item.content)
                    elif isinstance(item, ThinkingPart):
                        # We don't send ThinkingPart back as text content for Gemini via OpenRouter
                        # The reasoning is sent via reasoning_details
                        pass
                    elif isinstance(item, ToolCallPart):
                        tool_calls.append(self._map_tool_call(item))
                    elif isinstance(item, BuiltinToolCallPart | BuiltinToolReturnPart):
                        pass
                    else:
                        assert_never(item)
                
                message_param = chat.ChatCompletionAssistantMessageParam(role='assistant')
                
                if texts:
                    message_param['content'] = '\n\n'.join(texts)
                else:
                    message_param['content'] = None
                
                if tool_calls:
                    message_param['tool_calls'] = tool_calls
                
                # INJECT REASONING_DETAILS
                if message.provider_details and "reasoning_details" in message.provider_details:
                    # We need to cast or ignore type checking because reasoning_details 
                    # is not in the standard ChatCompletionAssistantMessageParam definition
                    message_param["reasoning_details"] = message.provider_details["reasoning_details"] # type: ignore
                
                openai_messages.append(message_param)
                
            else:
                assert_never(message)
        
        # Add system instructions if present (using parent's logic helper if possible, 
        # but _get_instructions is private, so we replicate it or access it)
        # Accessing private method _get_instructions from parent
        if hasattr(self, '_get_instructions'):
            instructions = self._get_instructions(messages)
            if instructions:
                openai_messages.insert(0, chat.ChatCompletionSystemMessageParam(content=instructions, role='system'))
        
        return openai_messages
