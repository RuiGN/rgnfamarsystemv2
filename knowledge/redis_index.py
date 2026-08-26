import json
import re
from collections.abc import Mapping

import numpy
from redis.commands.search.field import NumericField, TagField, TextField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query


SEARCH_PUNCTUATION = re.compile(r'([\\\-\[\]{}()<>~*:\"\'|@!])')
TAG_PUNCTUATION = re.compile(r'([\\,\.<>\{\}\[\]"\':;!@#$%^&*()\-+=~ ])')


class InvalidIndexManifest(ValueError):
    pass


class InvalidKnowledgeFilter(ValueError):
    pass


def _as_text(value):
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return '' if value is None else str(value)


def _escape_search_terms(value):
    return [SEARCH_PUNCTUATION.sub(r'\\\1', term) for term in str(value).split() if term]


def _escape_tag(value):
    return TAG_PUNCTUATION.sub(r'\\\1', str(value))


class RedisKnowledgeIndex:
    RETURN_FIELDS = (
        'chunk_id',
        'document_id',
        'source_id',
        'title',
        'section_reference',
        'page_number',
        'content',
        'jurisdiction',
        'effective_from',
        'effective_to',
        'source_url',
        'vector_score',
    )
    TAG_FILTERS = frozenset({'jurisdiction', 'language', 'product_domain', 'source_type'})
    NUMERIC_FILTERS = frozenset({'effective_from', 'effective_to'})

    def __init__(self, client, *, prefix):
        self.client = client
        self.prefix = str(prefix).rstrip(':')
        self._written_manifests = {}
        self._written_counts = {}

    def _generation_from_index(self, index_name):
        generation_id = str(index_name).rsplit(':', 1)[-1].strip()
        if not generation_id:
            raise ValueError('O nome do índice deve terminar com a identificação da geração.')
        return generation_id

    def _generation_prefix(self, generation_id):
        return f'{self.prefix}:generation:{generation_id}'

    def _chunk_prefix(self, generation_id):
        return f'{self._generation_prefix(generation_id)}:chunk:'

    def _manifest_key(self, generation_id):
        return f'{self._generation_prefix(generation_id)}:manifest'

    def _chunk_set_key(self, generation_id):
        return f'{self._generation_prefix(generation_id)}:chunks'

    def create(self, index_name, *, dimensions):
        if int(dimensions) <= 0:
            raise ValueError('A dimensão do embedding deve ser positiva.')
        generation_id = self._generation_from_index(index_name)
        schema = (
            TagField('chunk_id'),
            NumericField('document_id'),
            NumericField('source_id'),
            TextField('title', weight=2.0),
            TextField('section_reference'),
            NumericField('page_number'),
            TextField('content', weight=1.0),
            TagField('jurisdiction'),
            TagField('language'),
            TagField('product_domain'),
            TagField('source_type'),
            NumericField('effective_from'),
            NumericField('effective_to'),
            VectorField(
                'embedding',
                'HNSW',
                {
                    'TYPE': 'FLOAT32',
                    'DIM': int(dimensions),
                    'DISTANCE_METRIC': 'COSINE',
                },
            ),
        )
        self.client.ft(index_name).create_index(
            schema,
            definition=IndexDefinition(
                prefix=[self._chunk_prefix(generation_id)],
                index_type=IndexType.HASH,
                language='Portuguese',
            ),
        )

    def write_chunks(self, generation_id, chunks):
        chunk_rows = tuple(chunks)
        pipeline = self.client.pipeline(transaction=True)
        chunk_set_key = self._chunk_set_key(generation_id)
        for chunk in chunk_rows:
            chunk_id = str(chunk['chunk_id'])
            embedding = numpy.asarray(chunk['embedding'], dtype=numpy.float32)
            mapping = {
                'chunk_id': chunk_id,
                'document_id': int(chunk['document_id']),
                'source_id': int(chunk['source_id']),
                'title': str(chunk.get('title') or ''),
                'section_reference': str(chunk.get('section_reference') or ''),
                'page_number': int(chunk.get('page_number') or 0),
                'content': str(chunk.get('content') or ''),
                'jurisdiction': str(chunk.get('jurisdiction') or ''),
                'language': str(chunk.get('language') or ''),
                'product_domain': str(chunk.get('product_domain') or ''),
                'source_type': str(chunk.get('source_type') or ''),
                'effective_from': int(chunk.get('effective_from') or 0),
                'effective_to': int(chunk.get('effective_to') or 0),
                'source_url': str(chunk.get('source_url') or ''),
                'embedding': embedding.tobytes(),
            }
            pipeline.hset(f'{self._chunk_prefix(generation_id)}{chunk_id}', mapping=mapping)
            pipeline.sadd(chunk_set_key, chunk_id)
        pipeline.execute()
        self._written_counts[str(generation_id)] = len(chunk_rows)
        return len(chunk_rows)

    def write_manifest(self, generation_id, manifest):
        normalized = {
            'chunk_count': int(manifest.get('chunk_count', 0)),
            'manifest_hash': str(manifest.get('manifest_hash') or ''),
            'metadata': json.dumps(
                manifest.get('metadata') or {}, ensure_ascii=False, sort_keys=True
            ),
        }
        self.client.hset(self._manifest_key(generation_id), mapping=normalized)
        self._written_manifests[str(generation_id)] = normalized

    def _load_manifest(self, generation_id):
        cached = self._written_manifests.get(str(generation_id))
        if cached is not None:
            return cached
        raw = self.client.hgetall(self._manifest_key(generation_id))
        if not isinstance(raw, Mapping):
            return {}
        return {_as_text(key): _as_text(value) for key, value in raw.items()}

    def publish(self, index_name, alias):
        generation_id = self._generation_from_index(index_name)
        manifest = self._load_manifest(generation_id)
        try:
            expected_count = int(manifest['chunk_count'])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidIndexManifest('A geração não possui manifesto válido.') from exc
        if expected_count < 0 or not manifest.get('manifest_hash'):
            raise InvalidIndexManifest('A geração não possui manifesto válido.')

        actual_count = self._written_counts.get(str(generation_id))
        if actual_count is None:
            redis_count = self.client.scard(self._chunk_set_key(generation_id))
            if isinstance(redis_count, int):
                actual_count = redis_count
        if actual_count is not None and actual_count != expected_count:
            raise InvalidIndexManifest(
                f'O manifesto declara {expected_count} chunks, mas a geração contém {actual_count}.'
            )
        self.client.execute_command('FT.ALIASUPDATE', alias, index_name)

    def delete_alias(self, alias):
        self.client.execute_command('FT.ALIASDEL', alias)

    def _filter_query(self, filters):
        clauses = []
        for name, value in sorted((filters or {}).items()):
            if value in (None, '', []):
                continue
            if name in self.TAG_FILTERS:
                values = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
                escaped = '|'.join(_escape_tag(item) for item in values)
                clauses.append(f'@{name}:{{{escaped}}}')
                continue
            if name in self.NUMERIC_FILTERS:
                if not isinstance(value, (list, tuple)) or len(value) != 2:
                    raise InvalidKnowledgeFilter(
                        f'O filtro {name} exige intervalo inicial e final.'
                    )
                clauses.append(f'@{name}:[{int(value[0])} {int(value[1])}]')
                continue
            raise InvalidKnowledgeFilter(f'Filtro de conhecimento não permitido: {name}.')
        return ' '.join(clauses)

    def search(self, alias, *, query, vector, filters, limit, offset=0):
        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))
        vector_bytes = numpy.asarray(vector, dtype=numpy.float32).tobytes()
        filter_query = self._filter_query(filters)
        lexical_query = '|'.join(_escape_search_terms(query))
        base_query = ' '.join(part for part in (filter_query, lexical_query) if part) or '*'
        redis_query = (
            Query(f'({base_query})=>[KNN {offset + limit} @embedding $vector AS vector_score]')
            .sort_by('vector_score')
            .paging(offset, limit)
            .return_fields(*self.RETURN_FIELDS)
            .dialect(2)
        )
        response = self.client.ft(alias).search(redis_query, {'vector': vector_bytes})
        results = []
        for document in response.docs:
            distance = float(_as_text(getattr(document, 'vector_score', 1.0)) or 1.0)
            results.append(
                {
                    'chunk_id': _as_text(getattr(document, 'chunk_id', '')),
                    'document_id': int(_as_text(getattr(document, 'document_id', 0)) or 0),
                    'source_id': int(_as_text(getattr(document, 'source_id', 0)) or 0),
                    'score': max(0.0, min(1.0, 1.0 - distance)),
                    'title': _as_text(getattr(document, 'title', '')),
                    'section_reference': _as_text(getattr(document, 'section_reference', '')),
                    'page_number': int(_as_text(getattr(document, 'page_number', 0)) or 0) or None,
                    'content': _as_text(getattr(document, 'content', '')),
                    'jurisdiction': _as_text(getattr(document, 'jurisdiction', '')),
                    'effective_from': int(_as_text(getattr(document, 'effective_from', 0)) or 0),
                    'effective_to': int(_as_text(getattr(document, 'effective_to', 0)) or 0),
                    'source_url': _as_text(getattr(document, 'source_url', '')),
                }
            )
        return results

    def drop(self, index_name, *, delete_documents=True):
        self.client.ft(index_name).dropindex(delete_documents=delete_documents)
