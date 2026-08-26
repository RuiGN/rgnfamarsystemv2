import io
import logging
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from pypdf import PdfReader

from knowledge.models import (
    KnowledgeDocument,
    KnowledgeIngestionLog,
    KnowledgeSource,
    content_hash,
)


logger = logging.getLogger(__name__)

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
    metadata = dict(entry.get('metadata') or {})
    metadata.pop('manual_content', None)
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
        'chat_eligible': bool(entry.get('chat_eligible', False)),
        'metadata': metadata,
    }
    source, _created = KnowledgeSource.objects.update_or_create(
        code=entry['code'],
        defaults=values,
    )
    return source


def ingest_source(entry, *, max_chunks=None, timeout=30):
    entry_manual_content = entry.get('manual_content')
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
        local_path = (source.metadata or {}).get('local_path')
        manual_content = entry_manual_content
        if manual_content:
            fetched = {
                'text': manual_content,
                'document_type': KnowledgeDocument.DocumentType.TEXT,
                'content_type': 'text/markdown; charset=utf-8',
            }
            selected_url = source.url
        elif local_path:
            fetched = fetch_local_source_text(local_path)
            selected_url = source.url
        else:
            urls = [source.url, *((source.metadata or {}).get('alternate_urls') or [])]
            fetched, selected_url = fetch_source_text_candidates(urls, timeout=timeout)
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
                'source_url': selected_url,
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
            details={'url': selected_url, 'content_type': fetched.get('content_type', '')},
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
        headers={
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/131.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        },
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


def fetch_source_text_candidates(urls, *, timeout=30):
    candidates = [str(url).strip() for url in urls if str(url).strip()]
    if not candidates:
        raise ValueError('A fonte não possui URL para ingestão.')
    errors = []
    for url in candidates:
        try:
            return fetch_source_text(url, timeout=timeout), url
        except Exception as error:
            errors.append(f'{url}: {error}')
    raise RuntimeError('Nenhuma URL da fonte pôde ser ingerida. ' + ' | '.join(errors))


def fetch_local_source_text(local_path):
    root = Path(settings.BASE_DIR).resolve()
    candidate = (root / str(local_path)).resolve()
    if root not in candidate.parents or not candidate.is_file():
        raise ValueError('O caminho local da fonte não é permitido ou não existe.')
    return {
        'text': candidate.read_text(encoding='utf-8'),
        'document_type': KnowledgeDocument.DocumentType.TEXT,
        'content_type': 'text/plain; charset=utf-8',
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
