from rest_framework import serializers

from accounts.models import User


class CurrentUserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'avatar_url',
            'is_staff',
        )
        read_only_fields = fields
