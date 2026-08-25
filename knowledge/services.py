import io
import time
from decimal import Decimal

import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from pypdf import PdfReader

from knowledge.models import (
    KnowledgeDocument,
    KnowledgeIngestionLog,
    KnowledgeSource,
    RAGChatMessage,
    RAGChatSession,
    RAGCitation,
    content_hash,
    deterministic_embedding,
)


OPENCODE_LEGACY_BASE_URL = 'https://api.opencode.ai'
OPENCODE_ZEN_BASE_URL = 'https://opencode.ai/zen'
OPENCODE_GO_BASE_URL = 'https://opencode.ai/zen/go'


def normalize_text(value):
    return ' '.join(str(value or '').replace('\x00', ' ').split())


def chunk_text(text, *, max_words=240, overlap=40):
    words = normalize_text(text).split()
    if not words:
        return []
    chunks = []
    step = max(max_words - overlap, 1)
    for start in range(0, len(words), step):
        part = words[start : start + max_words]
        if not part:
            continue
        chunks.append({'content': ' '.join(part), 'section_reference': f'chunk {len(chunks) + 1}'})
        if start + max_words >= len(words):
            break
    return chunks


def source_from_entry(entry):
    values = {
        'title': entry['title'],
        'source_type': entry['source_type'],
        'publisher': entry['publisher'],
        'jurisdiction': entry.get('jurisdiction', ''),
        'version': entry.get('version', ''),
        'url': entry.get('url', ''),
        'license_note': entry.get('license_note', ''),
        'is_official': bool(entry.get('is_official', False)),
        'is_active': True,
        'metadata': entry.get('metadata') or {},
    }
    source, _created = KnowledgeSource.objects.update_or_create(
        code=entry['code'],
        defaults=values,
    )
    return source


def ingest_source(entry, *, max_chunks=None, timeout=30):
    source = source_from_entry(entry)
    log = KnowledgeIngestionLog.objects.create(source=source)
    if source.source_type == KnowledgeSource.SourceType.BOOK_REFERENCE or (
        source.metadata or {}
    ).get('metadata_only'):
        log.finish(
            KnowledgeIngestionLog.Status.SKIPPED,
            details={'reason': 'metadata_only', 'url': source.url},
        )
        return {'source': source, 'document': None, 'chunks_created': 0, 'status': log.status}

    try:
        fetched = fetch_source_text(source.url, timeout=timeout)
        text = normalize_text(fetched['text'])
        if not text:
            raise ValueError('A fonte não retornou texto extraível.')
        document_hash = content_hash(text)
        document, _created = KnowledgeDocument.objects.update_or_create(
            source=source,
            content_hash=document_hash,
            defaults={
                'title': source.title,
                'document_type': fetched['document_type'],
                'source_url': source.url,
                'version_label': source.version,
                'retrieved_at': timezone.now(),
                'status': KnowledgeDocument.Status.PENDING,
                'extracted_text': text,
                'metadata': {'content_type': fetched.get('content_type', '')},
            },
        )
        chunks = chunk_text(text)
        if max_chunks is not None:
            chunks = chunks[:max_chunks]
        created_chunks = document.replace_chunks(chunks)
        log.finish(
            KnowledgeIngestionLog.Status.SUCCEEDED,
            document=document,
            chunks_created=len(created_chunks),
            details={'url': source.url, 'content_type': fetched.get('content_type', '')},
        )
        return {
            'source': source,
            'document': document,
            'chunks_created': len(created_chunks),
            'status': log.status,
        }
    except Exception as error:
        log.finish(
            KnowledgeIngestionLog.Status.FAILED,
            error_message=str(error),
            details={'url': source.url},
        )
        raise


def fetch_source_text(url, *, timeout=30):
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={'User-Agent': 'RGNFarmaSystemRAG/1.0'},
    )
    response.raise_for_status()
    content_type = response.headers.get('content-type', '').lower()
    if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
        return {
            'text': extract_pdf_text(response.content),
            'document_type': KnowledgeDocument.DocumentType.PDF,
            'content_type': content_type,
        }
    return {
        'text': extract_html_text(response.text),
        'document_type': KnowledgeDocument.DocumentType.HTML,
        'content_type': content_type,
    }


def extract_pdf_text(content):
    reader = PdfReader(io.BytesIO(content))
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def extract_html_text(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    main = soup.find('main') or soup.find('article') or soup.body or soup
    return main.get_text(' ', strip=True)


def retrieve_context(question, limit=5):
    query_vector = deterministic_embedding(question)
    scored = []
    queryset = (
        KnowledgeDocument.objects.filter(status=KnowledgeDocument.Status.INGESTED)
        .select_related('source')
        .prefetch_related('chunks')
    )
    for document in queryset:
        for chunk in document.chunks.all():
            lexical = chunk.match_score(question)
            vector = _cosine_similarity(query_vector, chunk.embedding_vector or [])
            score = (lexical * 0.75) + (vector * 0.25)
            if score <= 0:
                continue
            scored.append(_context_payload(chunk, score))
    scored.sort(key=lambda item: item['score'], reverse=True)
    return scored[:limit]


@transaction.atomic
def answer_question(user, question, *, session_id=None, limit=5):
    started = time.monotonic()
    session = _get_or_create_session(user, question, session_id=session_id)
    session.add_user_message(question)
    context = retrieve_context(question, limit=limit)
    provider_payload: dict[str, object]
    if getattr(settings, 'RAG_CHAT_LOCAL_ONLY', True):
        answer = local_answer(question, context)
        provider_payload = {'provider': 'local', 'reason': 'local_mode'}
        status = RAGChatMessage.Status.SUCCEEDED
        error_message = ''
    else:
        try:
            answer, provider_payload = invoke_opencode(question, context)
            status = RAGChatMessage.Status.SUCCEEDED
            error_message = ''
        except Exception as error:
            answer = local_answer(question, context, warning=str(error))
            provider_payload = {'provider': 'local', 'fallback': True, 'error': str(error)}
            status = RAGChatMessage.Status.SUCCEEDED
            error_message = ''
    latency_ms = int((time.monotonic() - started) * 1000)
    assistant_message = RAGChatMessage.objects.create(
        session=session,
        role=RAGChatMessage.Role.ASSISTANT,
        content=answer,
        model_name=getattr(settings, 'OPENCODE_MODEL', ''),
        status=status,
        latency_ms=latency_ms,
        retrieved_context=context,
        error_message=error_message,
        created_by=user,
    )
    citations = create_citations(assistant_message, context)
    return {
        'session_id': session.id,
        'message_id': assistant_message.id,
        'answer': answer,
        'citations': citations,
        'model_name': assistant_message.model_name,
        'latency_ms': latency_ms,
        'provider_payload': provider_payload,
    }


def invoke_gemini(question, context):
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        return local_answer(question, context), {'fallback': True, 'reason': 'missing_api_key'}

    from google import genai

    client = genai.Client(api_key=api_key)

    user_prompt = build_prompt(question, context)
    system_prompt = build_system_prompt()
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-pro')

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[user_prompt],
            config={
                'system_instruction': system_prompt,
                'temperature': 0.0,
                'max_output_tokens': 1200,
            },
        )
        return response.text, {'provider': 'gemini'}
    except Exception as error:
        raise ValueError(f'Erro na chamada ao Gemini: {error}')


def invoke_opencode(question, context):
    api_key = getattr(settings, 'OPENCODE_API_KEY', '')
    if not api_key:
        return local_answer(question, context), {'fallback': True, 'reason': 'missing_api_key'}

    provider, model_id = _normalize_opencode_model(
        getattr(settings, 'OPENCODE_MODEL', 'opencode-go/qwen3.7-max')
    )
    base_url = _normalize_opencode_base_url(
        getattr(settings, 'OPENCODE_BASE_URL', OPENCODE_GO_BASE_URL), provider
    )
    response = httpx.post(
        _opencode_messages_url(base_url),
        json={
            'model': model_id,
            'max_tokens': 1200,
            'temperature': 0,
            'system': build_system_prompt(),
            'messages': [{'role': 'user', 'content': build_prompt(question, context)}],
        },
        timeout=getattr(settings, 'OPENCODE_TIMEOUT_SECONDS', 120),
        headers={
            'x-api-key': api_key,
            'authorization': f'Bearer {api_key}',
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
    )
    response.raise_for_status()
    data = _opencode_json_response(response)
    answer = _extract_message_text(data)
    if not answer:
        raise ValueError('Resposta do provedor sem conteúdo textual.')
    return answer, {'provider': 'opencode', 'response_id': data.get('id', '')}


def _normalize_opencode_model(model_name):
    value = normalize_text(model_name or 'opencode-go/qwen3.7-max')
    provider, separator, model_id = value.partition('/')
    if separator and provider in {'opencode-go', 'opencode'} and model_id:
        return provider, model_id
    return '', value


def _normalize_opencode_base_url(base_url, provider):
    value = (base_url or '').strip().rstrip('/')
    legacy_values = {'', OPENCODE_LEGACY_BASE_URL, OPENCODE_ZEN_BASE_URL, 'https://opencode.ai'}
    if provider == 'opencode-go' and value in legacy_values:
        return OPENCODE_GO_BASE_URL
    if value in {'', OPENCODE_LEGACY_BASE_URL}:
        return OPENCODE_ZEN_BASE_URL
    return value


def _opencode_messages_url(base_url):
    value = base_url.rstrip('/')
    if value.endswith('/v1/messages'):
        return value
    if value.endswith('/v1'):
        return f'{value}/messages'
    return f'{value}/v1/messages'


def _opencode_json_response(response):
    try:
        return response.json()
    except ValueError as error:
        content_type = response.headers.get('content-type', '')
        preview = normalize_text(getattr(response, 'text', '')[:300])
        raise ValueError(
            'Resposta não JSON do provedor OpenCode. '
            f'content-type={content_type or "desconhecido"}; corpo={preview or "vazio"}'
        ) from error


def build_system_prompt():
    return (
        'Você é o assistente regulatório do RGN Farma System. Responda em português, '
        'com tom cordial, claro e profissional; responda de forma amigável mesmo quando '
        'o banco RAG não trouxer fontes suficientes. Quando houver fontes recuperadas, '
        'separe fatos de inferências e cite as fontes fornecidas. Quando não houver fonte '
        'recuperada ou a fonte não cobrir a pergunta, explique essa limitação sem encerrar '
        'a conversa, ofereça orientação geral prudente e peça os dados necessários para uma '
        'resposta validada; não invente legislação, artigos, prazos, requisitos ou citações.'
    )


def build_prompt(question, context):
    sources = []
    for index, item in enumerate(context, start=1):
        sources.append(
            f'[{index}] {item["title"]} | {item["section_reference"]} | {item["source_url"]}\n{item["content"]}'
        )
    context_text = '\n\n'.join(sources)
    if not context_text:
        return (
            f'Pergunta do usuário:\n{question}\n\n'
            'Fontes recuperadas:\nNenhuma fonte recuperada.\n\n'
            'Instruções: responda de forma amigável e útil. Informe que não há fonte validada '
            'no RAG para sustentar uma conclusão regulatória, mas ofereça orientação geral '
            'prudente, perguntas de esclarecimento e próximos passos; não cite fontes inexistentes, '
            'não atribua exigências a normas específicas sem fonte e não invente legislação.'
        )
    return (
        f'Pergunta do usuário:\n{question}\n\n'
        f'Fontes recuperadas:\n{context_text}\n\n'
        'Instruções: responda apenas com base nas fontes recuperadas. '
        'Quando a fonte não cobrir a pergunta, diga isso explicitamente. '
        'Inclua uma seção curta "Fontes" com os números usados.'
    )


def local_answer(question, context, warning=''):
    if not context:
        lines = [
            'Posso ajudar, mas no momento não encontrei fonte validada no banco de conhecimento para essa pergunta.',
            'Sem uma fonte recuperada, considere a resposta como orientação geral, não como conclusão regulatória validada.',
            'Para avançar com mais segurança, informe o processo, produto, área, país/órgão regulador e norma de referência, ou ingira o documento regulatório relacionado ao tema.',
            'Também posso ajudar a transformar sua pergunta em uma busca mais específica no RAG.',
        ]
        if warning:
            lines.append(
                'Observação técnica: resposta local usada porque o provedor externo falhou.'
            )
        return '\n'.join(lines)
    lines = [
        'Com base no banco de conhecimento, estes são os pontos relevantes:',
    ]
    for index, item in enumerate(context[:3], start=1):
        excerpt = item['content']
        if len(excerpt) > 360:
            excerpt = f'{excerpt[:357]}...'
        lines.append(f'{index}. {excerpt}')
    lines.append(
        'Fontes: '
        + ', '.join(f'[{i}] {item["title"]}' for i, item in enumerate(context[:3], start=1))
    )
    if warning:
        lines.append('Observação técnica: resposta local usada porque o provedor externo falhou.')
    return '\n'.join(lines)


def create_citations(message, context):
    citations = []
    for item in context:
        citation = RAGCitation.objects.create(
            message=message,
            source_id=item['source_id'],
            document_id=item['document_id'],
            chunk_id=item['chunk_id'],
            title=item['title'],
            source_url=item['source_url'],
            section_reference=item['section_reference'],
            excerpt=item['content'][:1000],
            relevance_score=Decimal(str(round(item['score'], 4))),
        )
        citations.append(
            {
                'id': citation.id,
                'title': citation.title,
                'source_url': citation.source_url,
                'section_reference': citation.section_reference,
                'excerpt': citation.excerpt,
                'relevance_score': str(citation.relevance_score),
            }
        )
    return citations


def _get_or_create_session(user, question, *, session_id=None):
    if session_id:
        session = RAGChatSession.objects.get(created_by=user, pk=session_id)
        return session
    title = normalize_text(question)[:120] or 'Pergunta RAG'
    return RAGChatSession.objects.create(created_by=user, title=title)


def _context_payload(chunk, score):
    document = chunk.document
    source = chunk.source
    return {
        'chunk_id': chunk.id,
        'document_id': document.id,
        'source_id': source.id,
        'title': document.title,
        'source_title': source.title,
        'source_url': document.source_url or source.url,
        'section_reference': chunk.section_reference,
        'page_number': chunk.page_number,
        'content': chunk.content,
        'score': round(float(score), 6),
    }


def _cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right))


def _extract_message_text(data):
    content = data.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text' and item.get('text'):
                    parts.append(item['text'])
                elif item.get('content'):
                    parts.append(str(item['content']))
        return '\n'.join(parts)
    if data.get('output_text'):
        return data['output_text']
    return ''
