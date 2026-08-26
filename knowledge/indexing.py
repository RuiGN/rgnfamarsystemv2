import hashlib
import json
import logging
import secrets
import uuid

from django.conf import settings
from django.db import transaction
from redis.exceptions import RedisError, ResponseError

from knowledge.eligibility import is_document_eligible
from knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIndexGeneration,
    KnowledgeSource,
)
from knowledge.openai_gateway import OpenAIGateway
from knowledge.redis_client import get_knowledge_redis
from knowledge.redis_index import RedisKnowledgeIndex


logger = logging.getLogger(__name__)
EMBEDDING_BATCH_SIZE = 64
PUBLICATION_LOCK_TTL_SECONDS = 120

RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

REFRESH_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class RedisPublicationLock:
    def __init__(self, client, key, *, ttl_seconds=PUBLICATION_LOCK_TTL_SECONDS):
        self.client = client
        self.key = key
        self.ttl_seconds = int(ttl_seconds)
        self.token = secrets.token_hex(32)

    def acquire(self):
        return bool(self.client.set(self.key, self.token, nx=True, ex=self.ttl_seconds))

    def release(self):
        return bool(self.client.eval(RELEASE_LOCK_SCRIPT, 1, self.key, self.token))

    def refresh(self):
        return bool(
            self.client.eval(
                REFRESH_LOCK_SCRIPT,
                1,
                self.key,
                self.token,
                self.ttl_seconds,
            )
        )

    def require_ownership(self):
        if not self.refresh():
            raise RedisError('Ownership do lock de publicação foi perdida.')


def _eligible_chunks():
    candidates = list(
        KnowledgeChunk.objects.filter(
            document__status=KnowledgeDocument.Status.INGESTED,
            source__is_active=True,
            source__chat_eligible=True,
            source__source_type=KnowledgeSource.SourceType.SYSTEM_MANUAL,
        )
        .select_related('source', 'document')
        .order_by('pk')
    )
    return [chunk for chunk in candidates if is_document_eligible(chunk.document)]


def reconcile_active_alias(*, redis_index=None, publication_lock=None):
    redis_index = redis_index or RedisKnowledgeIndex(
        get_knowledge_redis(), prefix=settings.KNOWLEDGE_REDIS_PREFIX
    )
    owns_lock = publication_lock is None
    publication_lock = publication_lock or RedisPublicationLock(
        redis_index.client,
        f'{settings.KNOWLEDGE_REDIS_PREFIX}:publication-lock',
    )
    if owns_lock and not publication_lock.acquire():
        raise RedisError('Outra publicação do índice está em andamento.')
    alias = f'idx:{settings.KNOWLEDGE_REDIS_PREFIX}:active'
    try:
        publication_lock.require_ownership()
        active = KnowledgeIndexGeneration.objects.filter(
            status=KnowledgeIndexGeneration.Status.ACTIVE
        ).first()
        publication_lock.require_ownership()
        if active is None:
            try:
                redis_index.delete_alias(alias)
            except ResponseError:
                pass
            return None
        redis_index.publish(active.redis_index_name, alias)
        return active
    finally:
        if owns_lock:
            publication_lock.release()


def _manifest_hash(chunks, *, embedding_model, dimensions):
    payload = {
        'embedding_model': embedding_model,
        'dimensions': dimensions,
        'chunks': [
            {'id': chunk.pk, 'content_hash': chunk.content_hash, 'document_id': chunk.document_id}
            for chunk in chunks
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _embedding_vectors(gateway, chunks):
    vectors = []
    resolved_model = settings.OPENAI_EMBEDDING_MODEL
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch_chunks = chunks[start : start + EMBEDDING_BATCH_SIZE]
        batch = gateway.embed_texts([chunk.content for chunk in batch_chunks])
        vectors.extend(batch.vectors)
        resolved_model = batch.model
    return vectors, resolved_model


def _redis_row(chunk, embedding):
    metadata = chunk.metadata or {}
    return {
        'chunk_id': chunk.pk,
        'document_id': chunk.document_id,
        'source_id': chunk.source_id,
        'title': chunk.title,
        'section_reference': chunk.section_reference,
        'page_number': chunk.page_number,
        'content': chunk.content,
        'embedding': embedding,
        'jurisdiction': chunk.source.jurisdiction,
        'language': metadata.get('language', ''),
        'product_domain': metadata.get('product_domain', ''),
        'source_type': chunk.source.source_type,
        'effective_from': 0,
        'effective_to': 0,
        'source_url': chunk.document.source_url or chunk.source.url,
    }


def build_index_generation(*, gateway=None, redis_index=None, generation_id=None):
    generation_id = str(generation_id or uuid.uuid4().hex).strip()
    if not generation_id or len(generation_id) > 64:
        raise ValueError('A identificação da geração deve conter entre 1 e 64 caracteres.')
    redis_index_name = f'idx:{settings.KNOWLEDGE_REDIS_PREFIX}:{generation_id}'
    gateway = gateway or OpenAIGateway()
    redis_index = redis_index or RedisKnowledgeIndex(
        get_knowledge_redis(), prefix=settings.KNOWLEDGE_REDIS_PREFIX
    )
    generation, created = KnowledgeIndexGeneration.objects.get_or_create(
        generation_id=generation_id,
        defaults={
            'redis_index_name': redis_index_name,
            'embedding_model': settings.OPENAI_EMBEDDING_MODEL,
            'embedding_dimensions': settings.OPENAI_EMBEDDING_DIMENSIONS,
        },
    )
    if generation.status == KnowledgeIndexGeneration.Status.ACTIVE:
        reconcile_active_alias(redis_index=redis_index)
        return generation
    if generation.status == KnowledgeIndexGeneration.Status.RETIRED:
        return reconcile_active_alias(redis_index=redis_index) or generation
    resume_ready = not created and generation.status == KnowledgeIndexGeneration.Status.READY
    if not created and not resume_ready:
        try:
            redis_index.drop(generation.redis_index_name, delete_documents=True)
        except Exception:
            logger.info(
                'Geração interrompida não possuía índice reutilizável. generation_id=%s',
                generation.generation_id,
            )
        generation.status = KnowledgeIndexGeneration.Status.BUILDING
        generation.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        generation.embedding_dimensions = settings.OPENAI_EMBEDDING_DIMENSIONS
        generation.chunk_count = 0
        generation.manifest_hash = ''
        generation.activated_at = None
        generation.error_message = ''
        generation.save(
            update_fields=[
                'status',
                'embedding_model',
                'embedding_dimensions',
                'chunk_count',
                'manifest_hash',
                'activated_at',
                'error_message',
                'updated_at',
            ]
        )
    index_created = False
    publication_lock = None
    try:
        if not resume_ready:
            chunks = _eligible_chunks()
            vectors, resolved_model = _embedding_vectors(gateway, chunks)
            redis_index.create(
                generation.redis_index_name,
                dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            )
            index_created = True
            rows = [
                _redis_row(chunk, vector) for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            redis_index.write_chunks(generation.generation_id, rows)
            manifest_hash = _manifest_hash(
                chunks,
                embedding_model=resolved_model,
                dimensions=settings.OPENAI_EMBEDDING_DIMENSIONS,
            )
            redis_index.write_manifest(
                generation.generation_id,
                {
                    'chunk_count': len(rows),
                    'manifest_hash': manifest_hash,
                    'metadata': {'embedding_model': resolved_model},
                },
            )
            generation.embedding_model = resolved_model
            generation.chunk_count = len(rows)
            generation.manifest_hash = manifest_hash
            generation.status = KnowledgeIndexGeneration.Status.READY
            generation.save(
                update_fields=[
                    'embedding_model',
                    'chunk_count',
                    'manifest_hash',
                    'status',
                    'updated_at',
                ]
            )
        else:
            index_created = True
        publication_lock = RedisPublicationLock(
            redis_index.client,
            f'{settings.KNOWLEDGE_REDIS_PREFIX}:publication-lock',
        )
        if not publication_lock.acquire():
            raise RedisError('Outra publicação do índice está em andamento.')
        publication_lock.require_ownership()
        with transaction.atomic(durable=True):
            KnowledgeIndexGeneration.objects.select_for_update().filter(
                status=KnowledgeIndexGeneration.Status.ACTIVE
            ).first()
            generation.activate()
        reconcile_active_alias(
            redis_index=redis_index,
            publication_lock=publication_lock,
        )
        return generation
    except Exception as exc:
        generation.refresh_from_db()
        database_committed = generation.status == KnowledgeIndexGeneration.Status.ACTIVE
        if not database_committed:
            generation.status = KnowledgeIndexGeneration.Status.FAILED
            generation.error_message = f'Falha ao construir índice ({type(exc).__name__}).'
            generation.save(update_fields=['status', 'error_message', 'updated_at'])
        if index_created and not database_committed:
            try:
                redis_index.drop(generation.redis_index_name, delete_documents=True)
            except Exception:
                logger.exception(
                    'Falha ao remover índice incompleto. generation_id=%s',
                    generation.generation_id,
                )
        raise
    finally:
        if publication_lock is not None:
            try:
                publication_lock.release()
            except Exception:
                logger.exception('Falha ao liberar lock de publicação do índice.')
