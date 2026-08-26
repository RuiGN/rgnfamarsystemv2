from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, serializers, status, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from base.permissions import SingleInstanceDjangoModelPermissions
from knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionLog,
    KnowledgeSource,
    RAGChatMessage,
    RAGChatSession,
)
from knowledge.serializers import (
    KnowledgeChunkSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeIngestionLogSerializer,
    KnowledgeSourceSerializer,
    RAGChatMessageSerializer,
    RAGChatRequestSerializer,
    RAGChatSessionSerializer,
)
from knowledge.services import InvalidChatSession, answer_question


class SingleInstanceKnowledgeReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (SingleInstanceDjangoModelPermissions,)
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    ordering: tuple[str, ...] = ('-created_at',)

    def get_queryset(self):
        return self.queryset.all()


class KnowledgeSourceViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = KnowledgeSource.objects.all()
    serializer_class = KnowledgeSourceSerializer
    filterset_fields = ('source_type', 'publisher', 'jurisdiction', 'is_official', 'is_active')
    search_fields = ('code', 'title', 'publisher', 'url')
    ordering = ('publisher', 'code')


class KnowledgeDocumentViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = KnowledgeDocument.objects.select_related('source')
    serializer_class = KnowledgeDocumentSerializer
    filterset_fields = ('source', 'document_type', 'status', 'version_label')
    search_fields = ('title', 'source__title', 'source_url', 'extracted_text')
    ordering = ('source__publisher', 'title')


class KnowledgeChunkViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = KnowledgeChunk.objects.select_related('source', 'document')
    serializer_class = KnowledgeChunkSerializer
    filterset_fields = ('source', 'document', 'page_number')
    search_fields = ('title', 'section_reference', 'content', 'document__title', 'source__title')
    ordering = ('document', 'chunk_index')


class RAGChatSessionViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = RAGChatSession.objects.none()
    serializer_class = RAGChatSessionSerializer
    filterset_fields = ('status',)
    search_fields = ('title',)
    ordering = ('-updated_at',)

    def get_queryset(self):
        return RAGChatSession.objects.filter(created_by=self.request.user)


class RAGChatMessageViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = RAGChatMessage.objects.none()
    serializer_class = RAGChatMessageSerializer
    filterset_fields = ('session', 'role', 'status')
    search_fields = ('content', 'model_name')
    ordering = ('-created_at',)

    def get_queryset(self):
        return (
            RAGChatMessage.objects.filter(session__created_by=self.request.user)
            .select_related('session', 'created_by')
            .prefetch_related('citations')
        )


class KnowledgeIngestionLogViewSet(SingleInstanceKnowledgeReadOnlyViewSet):
    queryset = KnowledgeIngestionLog.objects.select_related('source', 'document')
    serializer_class = KnowledgeIngestionLogSerializer
    filterset_fields = ('source', 'document', 'status')
    search_fields = ('source__code', 'source__title', 'error_message')
    ordering = ('-started_at',)


class CanUseRAGChat(BasePermission):
    message = 'Você não tem permissão para utilizar o assistente RAG.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm('knowledge.view_ragchatsession')
        )


class RAGChatAPIView(APIView):
    permission_classes = (IsAuthenticated, CanUseRAGChat)
    serializer_class = RAGChatRequestSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = answer_question(
                request.user,
                serializer.validated_data['question'],
                session_id=serializer.validated_data.get('session_id'),
            )
        except InvalidChatSession as error:
            raise serializers.ValidationError({'session_id': [str(error)]}) from error
        return Response(payload, status=status.HTTP_200_OK)
