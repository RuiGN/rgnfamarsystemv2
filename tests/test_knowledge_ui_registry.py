from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from ai_agents.models import AIAgentProfile
from base.ui.registry import get_module
from knowledge.models import RAGChatSession


class KnowledgeUiRegistryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='knowledge-ui@example.com',
            email='knowledge-ui@example.com',
            password='S3curePass!123',
        )
        self.client.force_login(self.user)

    def test_registry_exposes_only_read_only_knowledge_resources(self):
        module = get_module('knowledge')

        self.assertIsNotNone(module)
        self.assertSetEqual(
            {resource.slug for resource in module.resources},
            {
                'sources',
                'documents',
                'chunks',
                'sessions',
                'messages',
                'ingestion-logs',
            },
        )
        self.assertTrue(all(resource.read_only for resource in module.resources))

    def test_agent_chat_requires_rag_chat_permission(self):
        profile = AIAgentProfile.objects.create(
            code='AI-RAG-PERMISSION',
            name='Agente protegido',
            agent_type=AIAgentProfile.AgentType.SUMMARY,
            source_module=AIAgentProfile.SourceModule.DOCUMENTS,
            provider=AIAgentProfile.Provider.OPENAI,
            model_name='gpt-4o',
            system_prompt='Teste',
            allowed_source_modules=[AIAgentProfile.SourceModule.DOCUMENTS],
            created_by=self.user,
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='ai_agents',
                codename='view_aiagentprofile',
            )
        )
        url = reverse(
            'app:resource_chat',
            kwargs={
                'module_slug': 'ai_agents',
                'resource_slug': 'profiles',
                'pk': profile.pk,
            },
        )

        denied_response = self.client.get(url)

        self.assertEqual(denied_response.status_code, 403)

        self.user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label='knowledge',
                content_type__model=RAGChatSession._meta.model_name,
                codename='view_ragchatsession',
            )
        )

        allowed_response = self.client.get(url)

        self.assertEqual(allowed_response.status_code, 200)

