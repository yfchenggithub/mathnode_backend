import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.request_context import get_request_id
from app.data.mock_data import MOCK_USERS
from app.models.user import User
from app.repositories.user_auth_identity_repo import UserAuthIdentityRepository
from app.repositories.user_repo import UserRepository

LOGGER = logging.getLogger(__name__)


@dataclass
class WechatSessionData:
    openid: str
    session_key: str
    unionid: str | None = None


class AuthService:
    WECHAT_PROVIDER = "wechat_mini_program"
    WECHAT_PLATFORM = "wechat_miniapp"
    WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"
    WECHAT_CONNECT_TIMEOUT_SECONDS = 10.0
    WECHAT_READ_TIMEOUT_SECONDS = 15.0
    WECHAT_WRITE_TIMEOUT_SECONDS = 15.0
    WECHAT_POOL_TIMEOUT_SECONDS = 15.0
    TOKEN_TYPE = "Bearer"

    @staticmethod
    def login(code: str) -> dict:
        normalized_code = code.strip() if code else ""
        LOGGER.info(
            "login request received | request_id=%s platform=mock code=%s",
            get_request_id(),
            AuthService._mask_sensitive(normalized_code),
        )
        if not normalized_code:
            LOGGER.warning(
                "login rejected | request_id=%s reason=empty_code",
                get_request_id(),
            )
            raise BizException(code=4010, message="login failed: code is required")

        user = MOCK_USERS.get(normalized_code)
        if not user:
            LOGGER.warning(
                "login rejected | request_id=%s reason=invalid_code code=%s",
                get_request_id(),
                AuthService._mask_sensitive(normalized_code),
            )
            raise BizException(code=4010, message="login failed: code is invalid")

        LOGGER.info(
            "login success | request_id=%s platform=mock user_id=%s",
            get_request_id(),
            str(user.get("user_id", "")),
        )
        return AuthService._build_login_response(
            user_id=str(user.get("user_id", "")),
            nickname=str(user.get("nickname", "")),
            avatar_url=user.get("avatar_url"),
            token=str(user.get("token", "")),
            expires_in=settings.JWT_EXPIRE_SECONDS,
            platform="miniapp",
            auth_provider="mock",
        )

    @staticmethod
    def exchange_code_for_session(code: str) -> WechatSessionData:
        normalized_code = code.strip() if code else ""
        request_id = get_request_id()

        if not normalized_code:
            raise BizException(code=4012, message="login failed: code is required")

        appid, secret = AuthService._get_wechat_credentials()
        masked_code = AuthService._mask_sensitive(normalized_code)
        start_time = time.perf_counter()

        LOGGER.info(
            (
                "wechat code exchange start | request_id=%s url=%s code=%s "
                "connect_timeout=%ss read_timeout=%ss"
            ),
            request_id,
            AuthService.WECHAT_CODE2SESSION_URL,
            masked_code,
            AuthService.WECHAT_CONNECT_TIMEOUT_SECONDS,
            AuthService.WECHAT_READ_TIMEOUT_SECONDS,
        )

        try:
            with httpx.Client(
                timeout=AuthService._build_wechat_http_timeout(),
                trust_env=False,
                follow_redirects=False,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "math-search-backend/1.0",
                },
            ) as client:
                response = client.get(
                    AuthService.WECHAT_CODE2SESSION_URL,
                    params={
                        "appid": appid,
                        "secret": secret,
                        "js_code": normalized_code,
                        "grant_type": "authorization_code",
                    },
                )
        except httpx.ConnectTimeout:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            LOGGER.warning(
                (
                    "wechat code exchange connect timeout | request_id=%s "
                    "elapsed_ms=%s code=%s"
                ),
                request_id,
                elapsed_ms,
                masked_code,
            )
            raise BizException(code=5021, message="wechat login timeout")
        except httpx.ReadTimeout:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            LOGGER.warning(
                "wechat code exchange read timeout | request_id=%s elapsed_ms=%s code=%s",
                request_id,
                elapsed_ms,
                masked_code,
            )
            raise BizException(code=5021, message="wechat login timeout")
        except httpx.ConnectError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            LOGGER.exception(
                (
                    "wechat code exchange connect error | request_id=%s "
                    "elapsed_ms=%s code=%s"
                ),
                request_id,
                elapsed_ms,
                masked_code,
            )
            raise BizException(code=5022, message="wechat login service unavailable")
        except httpx.HTTPError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            LOGGER.exception(
                (
                    "wechat code exchange http error | request_id=%s "
                    "elapsed_ms=%s code=%s"
                ),
                request_id,
                elapsed_ms,
                masked_code,
            )
            raise BizException(code=5022, message="wechat login service unavailable")

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        LOGGER.info(
            "wechat code exchange response | request_id=%s status=%s elapsed_ms=%s",
            request_id,
            response.status_code,
            elapsed_ms,
        )

        if response.status_code != 200:
            response_preview = response.text[:200].replace("\n", " ").replace("\r", " ")
            LOGGER.error(
                (
                    "wechat code exchange non-200 response | request_id=%s status=%s "
                    "elapsed_ms=%s body=%s"
                ),
                request_id,
                response.status_code,
                elapsed_ms,
                response_preview,
            )
            raise BizException(code=5020, message="wechat login response invalid")

        try:
            payload = response.json()
        except ValueError:
            LOGGER.error(
                (
                    "wechat code exchange invalid json | request_id=%s status=%s "
                    "elapsed_ms=%s"
                ),
                request_id,
                response.status_code,
                elapsed_ms,
            )
            raise BizException(code=5020, message="wechat login response invalid")

        errcode = payload.get("errcode")
        if errcode not in (None, 0, "0"):
            errmsg = str(payload.get("errmsg", ""))
            LOGGER.warning(
                (
                    "wechat code exchange failed | request_id=%s errcode=%s "
                    "errmsg=%s code=%s elapsed_ms=%s"
                ),
                request_id,
                errcode,
                errmsg,
                masked_code,
                elapsed_ms,
            )
            if str(errcode) in {"40029", "40163"}:
                raise BizException(
                    code=4013,
                    message="login failed: wechat code is invalid or already used",
                )
            raise BizException(code=5020, message="wechat login failed")

        openid = str(payload.get("openid", "")).strip()
        if not openid:
            LOGGER.error(
                "wechat code exchange openid missing | request_id=%s elapsed_ms=%s",
                request_id,
                elapsed_ms,
            )
            raise BizException(code=5023, message="wechat login failed: openid missing")

        session_key = str(payload.get("session_key", "")).strip()
        if not session_key:
            LOGGER.error(
                (
                    "wechat code exchange session_key missing | request_id=%s "
                    "openid=%s elapsed_ms=%s"
                ),
                request_id,
                AuthService._mask_sensitive(openid),
                elapsed_ms,
            )
            raise BizException(
                code=5024,
                message="wechat login failed: session key missing",
            )

        raw_unionid = payload.get("unionid")
        unionid = str(raw_unionid).strip() if raw_unionid else None

        LOGGER.info(
            (
                "wechat code exchange success | request_id=%s openid=%s "
                "unionid_present=%s elapsed_ms=%s"
            ),
            request_id,
            AuthService._mask_sensitive(openid),
            str(bool(unionid)).lower(),
            elapsed_ms,
        )

        return WechatSessionData(
            openid=openid, session_key=session_key, unionid=unionid
        )

    @staticmethod
    def get_or_create_user_by_wechat_openid(
        db: Session,
        openid: str,
        session_key: str,
        unionid: str | None = None,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> tuple[User, bool]:
        normalized_nickname = AuthService._normalize_nickname(nickname)
        normalized_avatar_url = AuthService._normalize_avatar_url(avatar_url)

        try:
            identity = UserAuthIdentityRepository.get_identity_by_provider_and_provider_user_id(
                db=db,
                provider=AuthService.WECHAT_PROVIDER,
                provider_user_id=openid,
            )
        except SQLAlchemyError:
            db.rollback()
            LOGGER.exception(
                "database read failed when finding identity, openid=%s",
                AuthService._mask_sensitive(openid),
            )
            raise BizException(code=5010, message="database transaction failed")

        if identity is None:
            user_nickname = normalized_nickname or AuthService._build_default_nickname(
                openid
            )

            try:
                user = UserRepository.create_user(
                    db=db,
                    nickname=user_nickname,
                    avatar_url=normalized_avatar_url,
                    commit=False,
                )
            except SQLAlchemyError:
                db.rollback()
                LOGGER.exception(
                    "database write failed when creating user, openid=%s",
                    AuthService._mask_sensitive(openid),
                )
                raise BizException(code=5007, message="create user failed")

            try:
                UserAuthIdentityRepository.create_identity(
                    db=db,
                    user_id=user.id,
                    provider=AuthService.WECHAT_PROVIDER,
                    provider_user_id=openid,
                    unionid=unionid,
                    session_key=session_key,
                    commit=False,
                )
            except SQLAlchemyError:
                db.rollback()
                LOGGER.exception(
                    "database write failed when creating identity, openid=%s user_id=%s",
                    AuthService._mask_sensitive(openid),
                    user.id,
                )
                raise BizException(code=5008, message="create auth identity failed")

            try:
                db.commit()
                db.refresh(user)
            except SQLAlchemyError:
                db.rollback()
                LOGGER.exception(
                    "database transaction failed when saving new user, openid=%s",
                    AuthService._mask_sensitive(openid),
                )
                raise BizException(code=5010, message="database transaction failed")

            LOGGER.info(
                "new user registered, user_id=%s openid=%s",
                user.id,
                AuthService._mask_sensitive(openid),
            )
            return user, True

        user = UserRepository.get_user_by_id(db=db, user_id=identity.user_id)
        if user is None:
            LOGGER.error(
                "identity exists but user missing, identity_id=%s openid=%s",
                identity.id,
                AuthService._mask_sensitive(openid),
            )
            raise BizException(code=5011, message="user not found")

        try:
            UserAuthIdentityRepository.update_identity_session(
                db=db,
                identity=identity,
                session_key=session_key,
                unionid=unionid,
                commit=False,
            )
            UserRepository.touch_last_login(
                db=db,
                user=user,
                nickname=normalized_nickname,
                avatar_url=normalized_avatar_url,
                commit=False,
            )
            db.commit()
            db.refresh(user)
        except SQLAlchemyError:
            db.rollback()
            LOGGER.exception(
                "database transaction failed when updating login info, user_id=%s openid=%s",
                user.id,
                AuthService._mask_sensitive(openid),
            )
            raise BizException(code=5010, message="database transaction failed")

        LOGGER.info(
            "existing user login success, user_id=%s openid=%s",
            user.id,
            AuthService._mask_sensitive(openid),
        )
        return user, False

    @staticmethod
    def create_access_token(user_id: str) -> str:
        expires_in = AuthService.get_token_expire_seconds()
        now = int(time.time())
        LOGGER.debug(
            "token generation start | request_id=%s user_id=%s expires_in=%s",
            get_request_id(),
            user_id,
            expires_in,
        )
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + expires_in,
            # reserved for future refresh-token / token-version strategy.
            "type": "access",
        }

        try:
            token = AuthService._encode_jwt(payload=payload)
        except BizException:
            raise
        except Exception:
            LOGGER.exception("token generation failed, user_id=%s", user_id)
            raise BizException(code=5009, message="token generation failed")

        LOGGER.info(
            "token issued | request_id=%s user_id=%s token=%s",
            get_request_id(),
            user_id,
            AuthService._mask_sensitive(token),
        )
        return token

    @staticmethod
    def parse_access_token(token: str) -> str:
        normalized_token = token.strip() if token else ""
        if not normalized_token:
            LOGGER.warning(
                "token parse rejected | request_id=%s reason=empty_token",
                get_request_id(),
            )
            raise BizException(code=4011, message="unauthorized")

        try:
            payload = AuthService._decode_jwt(normalized_token)
        except BizException:
            LOGGER.warning(
                "token parse rejected | request_id=%s token=%s",
                get_request_id(),
                AuthService._mask_sensitive(normalized_token),
            )
            raise
        except Exception:
            LOGGER.exception(
                "token parse failed unexpectedly | request_id=%s token=%s",
                get_request_id(),
                AuthService._mask_sensitive(normalized_token),
            )
            raise BizException(code=4011, message="unauthorized")

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub.strip():
            LOGGER.warning(
                "token parse rejected | request_id=%s reason=missing_sub token=%s",
                get_request_id(),
                AuthService._mask_sensitive(normalized_token),
            )
            raise BizException(code=4011, message="unauthorized")
        LOGGER.debug(
            "token parse success | request_id=%s user_id=%s token=%s",
            get_request_id(),
            sub,
            AuthService._mask_sensitive(normalized_token),
        )
        return sub

    @staticmethod
    def login_by_wechat_miniapp_code(
        db: Session,
        code: str,
        nickname: str | None = None,
        avatar_url: str | None = None,
    ) -> dict:
        normalized_code = code.strip() if code else ""
        if not normalized_code:
            LOGGER.warning(
                "wechat miniapp login rejected | request_id=%s reason=empty_code",
                get_request_id(),
            )
            raise BizException(code=4012, message="login failed: code is required")

        LOGGER.info(
            (
                "wechat miniapp login request received | request_id=%s platform=%s "
                "provider=%s code=%s nickname_present=%s avatar_present=%s"
            ),
            get_request_id(),
            AuthService.WECHAT_PLATFORM,
            AuthService.WECHAT_PROVIDER,
            AuthService._mask_sensitive(normalized_code),
            str(bool(nickname)).lower(),
            str(bool(avatar_url)).lower(),
        )

        session_data = AuthService.exchange_code_for_session(normalized_code)
        user, is_new_user = AuthService.get_or_create_user_by_wechat_openid(
            db=db,
            openid=session_data.openid,
            session_key=session_data.session_key,
            unionid=session_data.unionid,
            nickname=nickname,
            avatar_url=avatar_url,
        )

        token = AuthService.create_access_token(user_id=user.id)
        LOGGER.info(
            "wechat miniapp login success | request_id=%s user_id=%s is_new_user=%s",
            get_request_id(),
            user.id,
            str(is_new_user).lower(),
        )

        return AuthService._build_login_response(
            user_id=user.id,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            token=token,
            expires_in=AuthService.get_token_expire_seconds(),
            platform=AuthService.WECHAT_PLATFORM,
            auth_provider=AuthService.WECHAT_PROVIDER,
        )

    @staticmethod
    def get_token_expire_seconds() -> int:
        return settings.JWT_EXPIRE_SECONDS if settings.JWT_EXPIRE_SECONDS > 0 else 86400

    @staticmethod
    def _build_wechat_http_timeout() -> httpx.Timeout:
        return httpx.Timeout(
            connect=AuthService.WECHAT_CONNECT_TIMEOUT_SECONDS,
            read=AuthService.WECHAT_READ_TIMEOUT_SECONDS,
            write=AuthService.WECHAT_WRITE_TIMEOUT_SECONDS,
            pool=AuthService.WECHAT_POOL_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _encode_jwt(payload: dict[str, Any]) -> str:
        secret = AuthService._get_jwt_secret().encode("utf-8")
        header = {"alg": "HS256", "typ": "JWT"}
        header_part = AuthService._base64url_encode(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        payload_part = AuthService._base64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )

        signing_input = f"{header_part}.{payload_part}".encode("utf-8")
        signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
        signature_part = AuthService._base64url_encode(signature)
        return f"{header_part}.{payload_part}.{signature_part}"

    @staticmethod
    def _decode_jwt(token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) != 3:
            raise BizException(code=4011, message="unauthorized")

        header_part, payload_part, signature_part = parts

        try:
            header = json.loads(
                AuthService._base64url_decode(header_part).decode("utf-8")
            )
            payload = json.loads(
                AuthService._base64url_decode(payload_part).decode("utf-8")
            )
        except (ValueError, json.JSONDecodeError):
            raise BizException(code=4011, message="unauthorized")

        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise BizException(code=4011, message="unauthorized")

        secret = AuthService._get_jwt_secret().encode("utf-8")
        signing_input = f"{header_part}.{payload_part}".encode("utf-8")
        expected_signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
        expected_signature_part = AuthService._base64url_encode(expected_signature)

        if not hmac.compare_digest(expected_signature_part, signature_part):
            raise BizException(code=4011, message="unauthorized")

        exp = payload.get("exp")
        if not isinstance(exp, int):
            raise BizException(code=4011, message="unauthorized")
        if exp <= int(time.time()):
            raise BizException(code=4011, message="unauthorized")

        iat = payload.get("iat")
        if not isinstance(iat, int):
            raise BizException(code=4011, message="unauthorized")

        return payload

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _base64url_decode(data: str) -> bytes:
        padding = "=" * ((4 - len(data) % 4) % 4)
        return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))

    @staticmethod
    def _get_jwt_secret() -> str:
        secret = settings.JWT_SECRET.strip()
        if not secret:
            raise BizException(code=5006, message="JWT_SECRET is not configured")
        return secret

    @staticmethod
    def _get_wechat_credentials() -> tuple[str, str]:
        appid = settings.WECHAT_MINIAPP_APPID.strip()
        secret = settings.WECHAT_MINIAPP_SECRET.strip()
        if not appid or not secret:
            raise BizException(
                code=5006,
                message="WECHAT_MINIAPP_APPID/WECHAT_MINIAPP_SECRET is not configured",
            )
        return appid, secret

    @staticmethod
    def _normalize_nickname(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _normalize_avatar_url(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _build_default_nickname(openid: str) -> str:
        suffix = openid[-6:] if len(openid) >= 6 else openid
        return f"wx_{suffix}"

    @staticmethod
    def _build_login_response(
        user_id: str,
        nickname: str,
        avatar_url: str | None,
        token: str,
        expires_in: int,
        platform: str,
        auth_provider: str,
    ) -> dict:
        return {
            "user_id": user_id,
            "nickname": nickname,
            "avatar_url": avatar_url,
            "token": token,
            "token_type": AuthService.TOKEN_TYPE,
            "expires_in": expires_in,
            "platform": platform,
            "auth_provider": auth_provider,
        }

    @staticmethod
    def _mask_sensitive(value: str | None, left: int = 3, right: int = 2) -> str:
        if not value:
            return ""
        raw = value.strip()
        if len(raw) <= left + right:
            return "***"
        return f"{raw[:left]}***{raw[-right:]}"
