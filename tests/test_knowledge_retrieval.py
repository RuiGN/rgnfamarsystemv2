from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase, override_settings

from knowledge.openai_gateway import OpenAIGateway, OpenAIResponseError
from knowledge.retrieval import retrieve_context


class KnowledgeRetrievalTests(TestCase):
    def test_retrieval_returns_empty_without_active_generation(self):
        assert retrieve_context('Como informar lote?') == []


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_TIMEOUT_SECONDS=10,
    OPENAI_MODEL='test-model',
    OPENAI_EMBEDDING_MODEL='test-embedding',
    OPENAI_EMBEDDING_DIMENSIONS=3,
)
class KnowledgeProviderTests(SimpleTestCase):
    @patch('knowledge.openai_gateway.OpenAI')
    def test_gateway_rejects_response_without_text(self, openai):
        openai.return_value.responses.create.return_value = SimpleNamespace(
            output_text='',
            model='test-model',
            id='resp-1',
        )

        with pytest.raises(OpenAIResponseError):
            OpenAIGateway().generate_text(instructions='Use o manual.', input='Pergunta')

    @patch('knowledge.openai_gateway.OpenAI')
    def test_gateway_orders_embeddings_by_input_index(self, openai):
        openai.return_value.embeddings.create.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(index=1, embedding=[4, 5, 6]),
                SimpleNamespace(index=0, embedding=[1, 2, 3]),
            ],
            model='test-embedding',
            usage=SimpleNamespace(prompt_tokens=7),
        )

        result = OpenAIGateway().embed_texts(['primeiro', 'segundo'])

        assert result.vectors == ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0))
        assert result.model == 'test-embedding'
        assert result.input_tokens == 7

    @patch('knowledge.openai_gateway.OpenAI')
    def test_gateway_rejects_embedding_with_wrong_dimension(self, openai):
        openai.return_value.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1, 2])],
            model='test-embedding',
            usage=SimpleNamespace(prompt_tokens=1),
        )

        with pytest.raises(OpenAIResponseError):
            OpenAIGateway().embed_texts(['texto'])
