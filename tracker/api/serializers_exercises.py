from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from tracker.models import Exercise


class ExerciseSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = [
            "id",
            "name",
            "description",
            "body_area",
            "difficulty",
            "image_url",
            "video_url",
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_image_url(self, obj):
        request = self.context.get("request")
        if not obj.image:
            return None
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class ExerciseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = [
            "id",
            "name",
            "description",
            "body_area",
            "difficulty",
            "image",
            "video_url",
        ]
        read_only_fields = ["id"]
