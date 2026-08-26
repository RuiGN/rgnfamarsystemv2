from django.urls import path
from rest_framework.routers import DefaultRouter

from knowledge.views import (
    KnowledgeChunkViewSet,
    KnowledgeDocumentViewSet,
    KnowledgeIngestionLogViewSet,
    KnowledgeSourceViewSet,
    RAGChatAPIView,
    RAGChatMessageViewSet,
    RAGChatSessionViewSet,
)


app_name = 'knowledge'

router = DefaultRouter()
router.register('sources', KnowledgeSourceViewSet, basename='source')
router.register('documents', KnowledgeDocumentViewSet, basename='document')
router.register('chunks', KnowledgeChunkViewSet, basename='chunk')
router.register('sessions', RAGChatSessionViewSet, basename='session')
router.register('messages', RAGChatMessageViewSet, basename='message')
router.register('ingestion-logs', KnowledgeIngestionLogViewSet, basename='ingestion-log')

urlpatterns = [
    path('chat/', RAGChatAPIView.as_view(), name='chat'),
] + router.urls
