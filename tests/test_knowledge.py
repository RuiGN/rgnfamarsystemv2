import pytest

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient
from unittest.mock import Mock, patch


User = get_user_model()


def create_user(email='qa.rag@example.com'):
    return User.objects.create_user(username=email, email=email, password='S3curePass!123')


def create_source_and_document(title='RDC 658/2022', code='ANVISA-RDC-658-2022'):
    from knowledge.models import KnowledgeDocument, KnowledgeSource

    source = KnowledgeSource.objects.create(
        code=code,
        title=title,
        source_type=KnowledgeSource.SourceType.REGULATION,
        publisher='Anvisa',
        jurisdiction='BR',
        url='https://www.in.gov.br/en/web/dou/-/resolucao-rdc-n-658-de-30-de-marco-de-2022-389846242',
        is_official=True,
    )
    document = KnowledgeDocument.objects.create(
        source=source,
        title=title,
        document_type=KnowledgeDocument.DocumentType.HTML,
        source_url=source.url,
        content_hash='hash-rdc-658',
        extracted_text='BPF exige gerenciamento de risco da qualidade e revisao de registros de lote.',
    )
    return source, document


class KnowledgeModelTests(TestCase):
    def test_document_replaces_chunks_and_validates_source_relationship(self):
        from knowledge.models import KnowledgeDocument, KnowledgeSource, KnowledgeChunk

        source, document = create_source_and_document()
        other_source = KnowledgeSource.objects.create(
            code='ICH-Q9',
            title='ICH Q9(R1)',
            source_type=KnowledgeSource.SourceType.GUIDELINE,
            publisher='ICH',
            jurisdiction='ICH',
            url='https://database.ich.org/sites/default/files/ICH_Q9%28R1%29_Guideline_Step4_2022_1219.pdf',
            is_official=True,
        )

        document.replace_chunks(
            [
                {
                    'content': 'Gerenciamento de risco da qualidade deve ser cientifico e proporcional.',
                    'section_reference': 'Capitulo I',
                    'page_number': 1,
                },
                {
                    'content': 'Registros de producao devem ser revisados antes da liberacao do lote.',
                    'section_reference': 'Capitulo II',
                    'page_number': 2,
                },
            ]
        )
        document.replace_chunks(
            [
                {
                    'content': 'Controle de mudancas e CAPA devem manter evidencia objetiva.',
                    'section_reference': 'Capitulo III',
                    'page_number': 3,
                }
            ]
        )
        invalid_document = KnowledgeDocument(
            source=other_source,
            title='Fonte alternativa',
            document_type=KnowledgeDocument.DocumentType.HTML,
            source_url=other_source.url,
            content_hash='alternate-source',
        )

        invalid_document.full_clean()

        chunks = list(KnowledgeChunk.objects.filter(document=document).order_by('chunk_index'))
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].source == source
        assert 'CAPA' in chunks[0].content


class KnowledgeProviderTests(SimpleTestCase):
    @override_settings(
        OPENCODE_API_KEY='test-key',
        OPENCODE_BASE_URL='https://api.opencode.ai',
        OPENCODE_MODEL='opencode-go/qwen3.7-max',
    )
    def test_invoke_opencode_normalizes_opencode_go_messages_endpoint(self):
        from knowledge.services import invoke_opencode

        response = Mock()
        response.raise_for_status.return_value = None
        response.headers = {'content-type': 'application/json'}
        response.json.return_value = {
            'id': 'msg_test',
            'content': [{'type': 'text', 'text': 'Resposta remota.'}],
        }

        with patch('knowledge.services.httpx.post', return_value=response) as post:
            answer, metadata = invoke_opencode('Como validar um sistema GxP?', [])

        args, kwargs = post.call_args
        assert args[0] == 'https://opencode.ai/zen/go/v1/messages'
        assert kwargs['json']['model'] == 'qwen3.7-max'
        assert kwargs['json']['messages'][0]['role'] == 'user'
        assert kwargs['headers']['x-api-key'] == 'test-key'
        assert answer == 'Resposta remota.'
        assert metadata == {'provider': 'opencode', 'response_id': 'msg_test'}

    @override_settings(
        OPENCODE_API_KEY='test-key',
        OPENCODE_BASE_URL='https://api.opencode.ai',
        OPENCODE_MODEL='opencode-go/qwen3.7-max',
    )
    def test_invoke_opencode_reports_non_json_provider_response(self):
        from knowledge.services import invoke_opencode

        response = Mock()
        response.raise_for_status.return_value = None
        response.headers = {'content-type': 'text/plain;charset=UTF-8'}
        response.text = 'Not Found'
        response.json.side_effect = ValueError('Expecting value')

        with patch('knowledge.services.httpx.post', return_value=response):
            with self.assertRaisesMessage(ValueError, 'Resposta não JSON do provedor OpenCode'):
                invoke_opencode('Como validar um sistema GxP?', [])


class KnowledgeServiceTests(TestCase):
    @override_settings(OPENCODE_API_KEY='remote-key', RAG_CHAT_LOCAL_ONLY=True)
    def test_answer_question_uses_local_provider_when_local_mode_is_enabled(self):
        from knowledge.services import answer_question

        user = create_user('rag.local@example.com')
        _source, document = create_source_and_document()
        document.replace_chunks(
            [{'content': 'BPF exige registros completos, íntegros e rastreáveis.'}]
        )

        with patch('knowledge.services.httpx.post') as post:
            response = answer_question(user, 'O que a BPF exige sobre registros?')

        post.assert_not_called()
        assert response['answer']
        assert response['provider_payload']['provider'] == 'local'
        assert response['provider_payload']['reason'] == 'local_mode'
        assert response['citations']

    @override_settings(OPENCODE_API_KEY='')
    def test_retrieval_and_local_answer_return_ranked_citations(self):
        from knowledge.services import answer_question, retrieve_context

        user = create_user()
        _source, document = create_source_and_document()
        document.replace_chunks(
            [
                {
                    'content': 'A Farmacopeia Brasileira define requisitos minimos de qualidade para insumos e especialidades farmaceuticas.',
                    'section_reference': 'Farmacopeia Brasileira 8a edicao',
                },
                {
                    'content': 'A RDC 658 exige BPF, gerenciamento de risco da qualidade e revisao de registros de fabricacao.',
                    'section_reference': 'RDC 658/2022',
                },
            ]
        )

        results = retrieve_context('O que a RDC 658 exige sobre risco da qualidade?', limit=1)
        response = answer_question(user, 'O que a RDC 658 exige sobre risco da qualidade?')

        assert len(results) == 1
        assert 'risco da qualidade' in results[0]['content'].lower()
        assert response['answer']
        assert response['citations']
        assert response['session_id']
        assert response['message_id']
        assert response['citations'][0]['title'] == document.title

    def test_local_answer_without_context_is_friendly_and_actionable(self):
        from knowledge.services import local_answer

        response = local_answer('Como devo validar um sistema legado?', [])

        assert (
            'Não encontrei fontes suficientes no banco de conhecimento para responder com segurança.'
            not in response
        )
        assert 'Posso ajudar' in response
        assert 'orientação geral' in response
        assert 'fonte validada' in response

    def test_prompt_allows_friendly_answer_when_no_sources_are_retrieved(self):
        from knowledge.services import build_prompt, build_system_prompt

        system_prompt = build_system_prompt()
        user_prompt = build_prompt('Como devo validar um sistema legado?', [])

        assert 'responda de forma amigável' in system_prompt
        assert 'não invente legislação' in system_prompt
        assert 'Nenhuma fonte recuperada' in user_prompt
        assert 'orientação geral' in user_prompt
        assert 'não cite fontes inexistentes' in user_prompt


@pytest.mark.legacy_api_permissions
class KnowledgeApiTests(TestCase):
    @override_settings(OPENCODE_API_KEY='')
    def test_chat_endpoint_is_authenticated_global_and_returns_sources(self):
        user = create_user('rag.api@example.com')
        _source, document = create_source_and_document()
        _other_source, other_document = create_source_and_document(
            title='Documento sem relação com CAPA', code='ANVISA-RDC-658-2022-OUTRO'
        )
        document.replace_chunks(
            [
                {
                    'content': 'CAPA deve possuir causa raiz, plano de acao, eficacia e evidencia objetiva.'
                }
            ]
        )
        other_document.replace_chunks(
            [{'content': 'Conteudo regulatorio sem relação com a pergunta principal.'}]
        )

        client = APIClient()
        unauthenticated = client.post(
            '/api/knowledge/chat/',
            {'question': 'Como estruturar CAPA?'},
            format='json',
        )
        client.force_authenticate(user)
        response = client.post(
            '/api/knowledge/chat/',
            {'question': 'Como estruturar CAPA?'},
            format='json',
        )

        assert unauthenticated.status_code in {401, 403}
        assert response.status_code == 200
        payload = response.json()
        assert payload['answer']
        assert payload['citations']
        assert payload['citations'][0]['title'] == document.title

    @override_settings(OPENCODE_API_KEY='')
    def test_chat_endpoint_accepts_null_session_id_from_widget_first_message(self):
        user = create_user('rag.widget@example.com')
        _source, document = create_source_and_document()
        document.replace_chunks(
            [{'content': 'BPF exige registros completos, íntegros e rastreáveis.'}]
        )

        client = APIClient()
        client.force_authenticate(user)
        response = client.post(
            '/api/knowledge/chat/',
            {'question': 'O que a BPF exige sobre registros?', 'session_id': None},
            format='json',
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload['session_id']
        assert payload['answer']
