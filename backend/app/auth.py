"""Authentication dependency.

Local development: server-issued anonymous browser sessions via signed cookies.
Later: Supabase anonymous Auth JWTs, ownership derived from verified identity.
"""

from fastapi import Request, Response, Depends
from itsdangerous import URLSafeSerializer

from app.config import get_settings

import uuid


def _get_serializer() -> URLSafeSerializer:
    settings = get_settings()
    return URLSafeSerializer(settings.secret_key, salt="concept-check-session")


def get_owner_id(request: Request, response: Response) -> str:
    """Extract or create an anonymous owner ID from a signed cookie.

    Every learner query is scoped by this owner_id.
    The client does NOT supply user_id — we derive it server-side.
    """
    serializer = _get_serializer()
    cookie_value = request.cookies.get("cc_session")

    owner_id = None
    if cookie_value:
        try:
            owner_id = serializer.loads(cookie_value)
        except Exception:
            owner_id = None

    if not owner_id:
        owner_id = str(uuid.uuid4())
        signed = serializer.dumps(owner_id)
        response.set_cookie(
            key="cc_session",
            value=signed,
            httponly=True,
            secure=get_settings().environment.lower() in {"production", "prod"},
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
        )

    return owner_id
