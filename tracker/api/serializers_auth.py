from django.contrib.auth.models import User
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers


class UserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    role = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.STR)
    def get_role(self, user):
        from tracker.services.roles import is_physio

        return "physio" if is_physio(user) else "client"


class UserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        user = self.context["request"].user
        email_exists = User.objects.exclude(pk=user.pk).filter(email__iexact=value).exists()

        if email_exists:
            raise serializers.ValidationError("This email address is already in use.")

        return value

    def update(self, instance, validated_data):
        instance.email = validated_data["email"]
        instance.save(update_fields=["email"])
        return instance
