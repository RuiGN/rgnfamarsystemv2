import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from knowledge.models import (
    KnowledgeDocument,
    KnowledgeIndexGeneration,
    KnowledgeSource,
    RAGChatSession,
)


def create_user(username='rag.models'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@example.com',
        password='test-pass',
    )


def create_manual_source(code='ERP-MANUAL'):
    return KnowledgeSource.objects.create(
        code=code,
        title='Manual ERP',
        source_type=KnowledgeSource.SourceType.SYSTEM_MANUAL,
        publisher='RGN Farma System',
        is_official=True,
        is_active=True,
        chat_eligible=True,
    )


class KnowledgeModelTests(TestCase):
    def test_document_replaces_chunks_atomically(self):
        source = create_manual_source()
        document = KnowledgeDocument.objects.create(
            source=source,
            title='Fórmulas',
            document_type=KnowledgeDocument.DocumentType.TEXT,
            extracted_text='Cadastro de fórmula mestra.',
        )

        created = document.replace_chunks(
            [
                {
                    'content': 'Acesse Formulações e selecione Nova fórmula.',
                    'section_reference': 'Cadastro',
                },
                {
                    'content': 'Salve a fórmula como rascunho.',
                    'section_reference': 'Estado',
                },
            ]
        )

        assert len(created) == 2
        assert document.chunks.count() == 2
        assert document.status == KnowledgeDocument.Status.INGESTED
        assert all(chunk.source_id == source.pk for chunk in document.chunks.all())

    def test_only_ready_generation_can_be_activated(self):
        generation = KnowledgeIndexGeneration.objects.create(
            generation_id='g-1',
            redis_index_name='idx:rgn:knowledge:g-1',
        )
        with pytest.raises(ValidationError):
            generation.activate()

    def test_chat_session_belongs_to_creator(self):
        user = create_user()
        session = RAGChatSession.objects.create(title='Minha conversa', created_by=user)

        message = session.add_user_message('Como cadastrar um produto?')

        assert message.created_by == user
        assert message.session == session
        assert session.last_question_at is not None
