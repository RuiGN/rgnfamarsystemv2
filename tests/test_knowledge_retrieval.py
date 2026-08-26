from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase, override_settings

from knowledge.models import (
    KnowledgeDocument,
    KnowledgeIndexGeneration,
    KnowledgeSource,
)
from knowledge.openai_gateway import OpenAIGateway, OpenAIResponseError
from knowledge.retrieval import retrieve_context
from tests.test_knowledge_models import create_manual_source


class KnowledgeRetrievalTests(TestCase):
    def test_retrieval_returns_empty_without_active_generation(self):
        assert retrieve_context('Como informar lote?') == []


class KnowledgeServiceRetrievalTests(TestCase):
    def setUp(self):
        self.source = create_manual_source('ERP-STOCK-MANUAL')
        self.document = KnowledgeDocument.objects.create(
            source=self.source,
            title='Manual de estoque',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Entrada de estoque com lote.',
        )
        self.document.replace_chunks(
            [
                {
                    'content': 'Para dar entrada, informe produto, lote e quantidade.',
                    'section_reference': 'Entrada',
                }
            ]
        )

    @patch('knowledge.retrieval.OpenAIGateway')
    @patch('knowledge.services.knowledge_redis_health', return_value={'available': False})
    def test_unhealthy_redis_skips_embedding_and_uses_postgres(self, _health, gateway):
        KnowledgeIndexGeneration.objects.create(
            generation_id='g-active',
            redis_index_name='idx:rgn:knowledge:g-active',
            status=KnowledgeIndexGeneration.Status.ACTIVE,
        )
        from knowledge.services import retrieve_context as retrieve_service_context

        context = retrieve_service_context('Como informar lote?', limit=5)

        assert context[0]['document_id'] == self.document.pk
        gateway.assert_not_called()

    def test_postgres_retrieval_ignores_external_source_even_if_eligible(self):
        external = KnowledgeSource.objects.create(
            code='EXTERNAL-REGULATION',
            title='Regulação externa',
            source_type=KnowledgeSource.SourceType.REGULATION,
            publisher='Órgão externo',
            is_active=True,
            chat_eligible=True,
        )
        external_document = KnowledgeDocument.objects.create(
            source=external,
            title='Regulação externa de estoque',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Para dar entrada, informe produto, lote e quantidade.',
        )
        external_document.replace_chunks(
            [{'content': 'Para dar entrada, informe produto, lote e quantidade.'}]
        )
        from knowledge.services import retrieve_context as retrieve_service_context

        context = retrieve_service_context('Como informar lote?', limit=5)

        assert context
        assert {item['source_id'] for item in context} == {self.source.pk}


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
