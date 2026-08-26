from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from knowledge.models import RAGChatSession
from knowledge.views import RAGChatMessageViewSet, RAGChatSessionViewSet
from tests.test_knowledge_models import create_user


def grant_chat_permission(user):
    user.user_permissions.add(Permission.objects.get(codename='view_ragchatsession'))


class KnowledgeApiTests(TestCase):
    def test_scoped_viewsets_declare_models_for_schema_introspection(self):
        assert RAGChatSessionViewSet.queryset.model._meta.label == 'knowledge.RAGChatSession'
        assert RAGChatMessageViewSet.queryset.model._meta.label == 'knowledge.RAGChatMessage'

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_chat_requires_explicit_permission(self):
        denied = create_user('rag.denied')
        allowed = create_user('rag.allowed')
        grant_chat_permission(allowed)
        client = APIClient()

        anonymous = client.post(
            '/api/knowledge/chat/',
            {'question': 'Como usar o sistema?'},
            format='json',
        )
        client.force_authenticate(denied)
        forbidden = client.post(
            '/api/knowledge/chat/',
            {'question': 'Como usar o sistema?'},
            format='json',
        )
        client.force_authenticate(allowed)
        success = client.post(
            '/api/knowledge/chat/',
            {'question': 'Como usar o sistema?', 'session_id': None},
            format='json',
        )

        assert anonymous.status_code in {401, 403}
        assert forbidden.status_code == 403
        assert success.status_code == 200
        assert success.json()['session_id']

    @override_settings(RAG_CHAT_LOCAL_ONLY=True)
    def test_session_id_from_another_user_is_rejected(self):
        owner = create_user('rag.api.owner')
        attacker = create_user('rag.api.other')
        grant_chat_permission(attacker)
        session = RAGChatSession.objects.create(title='Privada', created_by=owner)
        client = APIClient()
        client.force_authenticate(attacker)

        response = client.post(
            '/api/knowledge/chat/',
            {'question': 'Continue', 'session_id': session.pk},
            format='json',
        )

        assert response.status_code == 400
        assert response.json() == {
            'session_id': ['A conversa informada não existe ou não está disponível.']
        }

    def test_session_listing_is_scoped_to_authenticated_user(self):
        owner = create_user('rag.list.owner')
        other = create_user('rag.list.other')
        grant_chat_permission(owner)
        own_session = RAGChatSession.objects.create(title='Minha', created_by=owner)
        RAGChatSession.objects.create(title='Outra', created_by=other)
        client = APIClient()
        client.force_authenticate(owner)

        response = client.get('/api/knowledge/sessions/')

        assert response.status_code == 200
        payload = response.json()
        rows = payload.get('results', payload)
        assert [row['id'] for row in rows] == [own_session.pk]

    def test_actions_route_does_not_exist(self):
        user = create_user('rag.no.actions')
        client = APIClient()
        client.force_authenticate(user)

        assert client.get('/api/knowledge/actions/').status_code == 404
