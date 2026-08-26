from dataclasses import dataclass

from django.conf import settings
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError


class OpenAIGatewayError(RuntimeError):
    pass


class OpenAIConfigurationError(OpenAIGatewayError):
    pass


class OpenAIServiceError(OpenAIGatewayError):
    pass


class OpenAIResponseError(OpenAIGatewayError):
    pass


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    input_tokens: int


@dataclass(frozen=True, slots=True)
class TextGeneration:
    text: str
    model: str
    response_id: str


class OpenAIGateway:
    """Gateway da OpenAI para embeddings e respostas do assistente."""

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise OpenAIConfigurationError('Chave da OpenAI não configurada.')
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SECONDS,
        )

    def embed_texts(self, texts):
        ordered_texts = list(texts)
        if not ordered_texts:
            return EmbeddingBatch(
                vectors=(),
                model=settings.OPENAI_EMBEDDING_MODEL,
                input_tokens=0,
            )
        try:
            response = self.client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=ordered_texts,
                encoding_format='float',
                dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            )
        except APITimeoutError as exc:
            raise OpenAIServiceError('A geração de embeddings excedeu o tempo limite.') from exc
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise OpenAIServiceError(
                'O serviço de embeddings está temporariamente indisponível.'
            ) from exc

        sorted_items = sorted(response.data, key=lambda item: item.index)
        if len(sorted_items) != len(ordered_texts):
            raise OpenAIResponseError('A OpenAI retornou uma quantidade inválida de embeddings.')
        vectors = tuple(tuple(float(value) for value in item.embedding) for item in sorted_items)
        if any(len(vector) != settings.OPENAI_EMBEDDING_DIMENSIONS for vector in vectors):
            raise OpenAIResponseError('A OpenAI retornou embeddings com dimensão inválida.')
        usage = getattr(response, 'usage', None)
        return EmbeddingBatch(
            vectors=vectors,
            model=str(getattr(response, 'model', settings.OPENAI_EMBEDDING_MODEL)),
            input_tokens=int(getattr(usage, 'prompt_tokens', 0) or 0),
        )

    def generate_text(self, *, instructions, input, model=None):
        try:
            response = self.client.responses.create(
                model=model or settings.OPENAI_MODEL,
                instructions=instructions,
                input=input,
            )
        except APITimeoutError as exc:
            raise OpenAIServiceError('A geração da resposta excedeu o tempo limite.') from exc
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise OpenAIServiceError(
                'O serviço de respostas da OpenAI está temporariamente indisponível.'
            ) from exc

        text = str(getattr(response, 'output_text', '') or '').strip()
        if not text:
            raise OpenAIResponseError('A OpenAI retornou uma resposta sem conteúdo textual.')
        return TextGeneration(
            text=text,
            model=str(getattr(response, 'model', model or settings.OPENAI_MODEL)),
            response_id=str(getattr(response, 'id', '')),
        )
