from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer

from tracker.api.serializers import UserSerializer, UserUpdateSerializer


login_request_serializer = inline_serializer(
    name="LoginRequest",
    fields={
        "username": serializers.CharField(),
        "password": serializers.CharField(),
    },
)

login_response_serializer = inline_serializer(
    name="LoginResponse",
    fields={
        "token": serializers.CharField(),
        "user": UserSerializer(),
    },
)


@extend_schema(request=login_request_serializer, responses={200: login_response_serializer})
@api_view(["POST"])
@permission_classes([])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")
    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        "token": token.key,
        "user": UserSerializer(user).data,
    })


@extend_schema(request=None, responses={204: None})
@api_view(["POST"])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(methods=["GET"], responses={200: UserSerializer})
@extend_schema(methods=["PATCH"], request=UserUpdateSerializer, responses={200: UserSerializer})
@api_view(["GET", "PATCH"])
def me_view(request):
    if request.method == "PATCH":
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

    return Response(UserSerializer(request.user).data)
