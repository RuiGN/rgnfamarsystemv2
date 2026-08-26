from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from knowledge.models import KnowledgeDocument, RAGChatMessage
from knowledge.services import InvalidChatSession, answer_question
from tests.test_knowledge_models import create_manual_source, create_user


class KnowledgeChatServiceTests(TestCase):
    def setUp(self):
        self.user = create_user('rag.owner')
        self.other = create_user('rag.other')
        source = create_manual_source()
        document = KnowledgeDocument.objects.create(
            source=source,
            title='Manual de produtos',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Cadastro de produto.',
        )
        document.replace_chunks(
            [
                {
                    'content': 'Para cadastrar produto, acesse Cadastros, Produtos e selecione Adicionar.',
                    'section_reference': 'Produtos',
                }
            ]
        )

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_local_answer_persists_history_and_public_citations(self):
        result = answer_question(self.user, 'Como cadastrar produto?')

        assert result.keys() == {'session_id', 'message_id', 'answer', 'citations'}
        assert result['citations'][0].keys() == {
            'title',
            'section_reference',
            'url',
            'excerpt',
        }
        assert RAGChatMessage.objects.filter(session_id=result['session_id']).count() == 2

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_other_user_cannot_continue_session(self):
        first = answer_question(self.user, 'Como cadastrar produto?')

        with pytest.raises(InvalidChatSession):
            answer_question(self.other, 'Continue', session_id=first['session_id'])

    @patch('knowledge.services.invoke_openai', side_effect=RuntimeError('provider down'))
    def test_provider_failure_returns_local_answer_without_internal_error(self, _invoke):
        result = answer_question(self.user, 'Como cadastrar produto?')

        assert result['answer']
        assert 'provider down' not in result['answer']
        assert 'provider_payload' not in result
