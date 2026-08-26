from rest_framework import serializers

from knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionLog,
    KnowledgeSource,
    RAGChatMessage,
    RAGChatSession,
    RAGCitation,
)


class KnowledgeSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeSource
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    source_title = serializers.CharField(source='source.title', read_only=True)

    class Meta:
        model = KnowledgeDocument
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document.title', read_only=True)
    source_title = serializers.CharField(source='source.title', read_only=True)

    class Meta:
        model = KnowledgeChunk
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class RAGCitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RAGCitation
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class RAGChatMessageSerializer(serializers.ModelSerializer):
    citations = RAGCitationSerializer(many=True, read_only=True)

    class Meta:
        model = RAGChatMessage
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class RAGChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RAGChatSession
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class KnowledgeIngestionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeIngestionLog
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class RAGChatRequestSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=4000, trim_whitespace=True)
    session_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_question(self, value):
        question = ' '.join(value.split())
        if not question:
            raise serializers.ValidationError('Informe uma pergunta.')
        return question
