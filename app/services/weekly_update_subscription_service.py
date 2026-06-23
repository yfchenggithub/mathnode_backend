from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BizException
from app.core.logging_helpers import mask_sensitive
from app.core.request_context import get_request_id
from app.models.weekly_update_subscription import WeeklyUpdateSubscription
from app.repositories.user_auth_identity_repo import UserAuthIdentityRepository
from app.repositories.weekly_update_subscription_repo import (
    WeeklyUpdateSubscriptionRepository,
)
from app.schemas.weekly_update_subscription import (
    WeeklyUpdateAuthorizationRequest,
    WeeklyUpdateNotificationSendRequest,
)
from app.services.auth_service import AuthService

LOGGER = logging.getLogger(__name__)


class WeeklyUpdateSubscriptionService:
    ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
    SUBSCRIBE_MESSAGE_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
    WECHAT_TIMEOUT_SECONDS = 15.0
    _access_token: str = ""
    _access_token_expires_at: float = 0.0

    @staticmethod
    def get_template_id(raw_template_id: str | None = None) -> str:
        template_id = (raw_template_id or settings.WECHAT_WEEKLY_UPDATE_TEMPLATE_ID).strip()
        if not template_id:
            raise BizException(code=5030, message="weekly update template is not configured")
        return template_id

    @staticmethod
    def get_status(
        db: Session,
        *,
        user_id: str,
        template_id: str | None = None,
    ) -> dict:
        resolved_template_id = WeeklyUpdateSubscriptionService.get_template_id(template_id)
        record = WeeklyUpdateSubscriptionRepository.get_by_user_and_template(
            db=db,
            user_id=user_id,
            template_id=resolved_template_id,
        )
        return WeeklyUpdateSubscriptionService._to_status_payload(
            record,
            template_id=resolved_template_id,
        )

    @staticmethod
    def record_authorization_result(
        db: Session,
        *,
        user_id: str,
        payload: WeeklyUpdateAuthorizationRequest,
    ) -> dict:
        template_id = WeeklyUpdateSubscriptionService.get_template_id(payload.template_id)
        prompt_source = WeeklyUpdateSubscriptionService._normalize_prompt_source(
            payload.source
        )
        record = WeeklyUpdateSubscriptionRepository.get_or_create_by_user_and_template(
            db=db,
            user_id=user_id,
            template_id=template_id,
        )
        record = WeeklyUpdateSubscriptionRepository.apply_authorization_result(
            db=db,
            record=record,
            result=payload.result,
            prompt_source=prompt_source,
        )
        LOGGER.info(
            (
                "weekly update subscription authorization saved | request_id=%s "
                "user_id=%s template_id=%s result=%s source=%s available_count=%s"
            ),
            get_request_id(),
            mask_sensitive(user_id, left=2, right=2),
            mask_sensitive(template_id, left=4, right=4),
            payload.result,
            prompt_source or "-",
            record.available_count,
        )
        return WeeklyUpdateSubscriptionService._to_status_payload(
            record,
            template_id=template_id,
        )

    @staticmethod
    def deactivate(
        db: Session,
        *,
        user_id: str,
        template_id: str | None = None,
    ) -> dict:
        resolved_template_id = WeeklyUpdateSubscriptionService.get_template_id(template_id)
        record = WeeklyUpdateSubscriptionRepository.get_or_create_by_user_and_template(
            db=db,
            user_id=user_id,
            template_id=resolved_template_id,
        )
        record = WeeklyUpdateSubscriptionRepository.deactivate(db=db, record=record)
        return WeeklyUpdateSubscriptionService._to_status_payload(
            record,
            template_id=resolved_template_id,
        )

    @staticmethod
    def send_weekly_update_to_subscribers(
        db: Session,
        *,
        payload: WeeklyUpdateNotificationSendRequest,
    ) -> dict:
        template_id = WeeklyUpdateSubscriptionService.get_template_id()
        candidates = WeeklyUpdateSubscriptionRepository.list_send_candidates(
            db=db,
            template_id=template_id,
            limit=payload.limit,
        )

        sent_count = 0
        failed_count = 0
        skipped_missing_openid_count = 0
        failures: list[dict[str, Any]] = []

        for record in candidates:
            identity = UserAuthIdentityRepository.get_identity_by_user_id_and_provider(
                db=db,
                user_id=record.user_id,
                provider=AuthService.WECHAT_PROVIDER,
            )
            openid = str(identity.provider_user_id if identity else "").strip()
            if not openid:
                skipped_missing_openid_count += 1
                continue

            try:
                WeeklyUpdateSubscriptionService.send_subscribe_message(
                    openid=openid,
                    template_id=template_id,
                    project_name=payload.project_name,
                    project_progress=payload.project_progress,
                    updated_at=payload.updated_at
                    or WeeklyUpdateSubscriptionService._format_beijing_now(),
                    page=payload.page or settings.WECHAT_WEEKLY_UPDATE_PAGE,
                )
            except Exception as exc:
                failed_count += 1
                if len(failures) < 20:
                    failures.append(
                        {
                            "user_id": record.user_id,
                            "message": str(exc),
                        }
                    )
                LOGGER.warning(
                    (
                        "weekly update notification send failed | request_id=%s "
                        "user_id=%s template_id=%s error=%s"
                    ),
                    get_request_id(),
                    mask_sensitive(record.user_id, left=2, right=2),
                    mask_sensitive(template_id, left=4, right=4),
                    exc,
                )
                continue

            WeeklyUpdateSubscriptionRepository.consume_one_send(db=db, record=record)
            sent_count += 1

        return {
            "template_id": template_id,
            "candidate_count": len(candidates),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "skipped_missing_openid_count": skipped_missing_openid_count,
            "failures": failures,
        }

    @staticmethod
    def send_subscribe_message(
        *,
        openid: str,
        template_id: str,
        project_name: str,
        project_progress: str,
        updated_at: str,
        page: str,
    ) -> dict:
        access_token = WeeklyUpdateSubscriptionService.get_access_token()
        request_payload = {
            "touser": openid,
            "template_id": template_id,
            "page": page,
            "miniprogram_state": "formal",
            "lang": "zh_CN",
            "data": {
                settings.WECHAT_WEEKLY_UPDATE_PROJECT_FIELD: {
                    "value": project_name,
                },
                settings.WECHAT_WEEKLY_UPDATE_PROGRESS_FIELD: {
                    "value": project_progress,
                },
                settings.WECHAT_WEEKLY_UPDATE_TIME_FIELD: {
                    "value": updated_at,
                },
            },
        }
        with httpx.Client(timeout=WeeklyUpdateSubscriptionService.WECHAT_TIMEOUT_SECONDS) as client:
            response = client.post(
                WeeklyUpdateSubscriptionService.SUBSCRIBE_MESSAGE_SEND_URL,
                params={"access_token": access_token},
                json=request_payload,
            )
        response.raise_for_status()
        response_payload = response.json()
        errcode = response_payload.get("errcode")
        if errcode not in (None, 0, "0"):
            errmsg = str(response_payload.get("errmsg", ""))
            raise RuntimeError(f"wechat subscribe message failed: {errcode} {errmsg}")
        return response_payload

    @staticmethod
    def get_access_token() -> str:
        now = time.time()
        if (
            WeeklyUpdateSubscriptionService._access_token
            and WeeklyUpdateSubscriptionService._access_token_expires_at - now > 60
        ):
            return WeeklyUpdateSubscriptionService._access_token

        appid, secret = AuthService._get_wechat_credentials()
        with httpx.Client(timeout=WeeklyUpdateSubscriptionService.WECHAT_TIMEOUT_SECONDS) as client:
            response = client.get(
                WeeklyUpdateSubscriptionService.ACCESS_TOKEN_URL,
                params={
                    "grant_type": "client_credential",
                    "appid": appid,
                    "secret": secret,
                },
            )
        response.raise_for_status()
        payload = response.json()
        errcode = payload.get("errcode")
        if errcode not in (None, 0, "0"):
            errmsg = str(payload.get("errmsg", ""))
            raise RuntimeError(f"wechat access token failed: {errcode} {errmsg}")

        token = str(payload.get("access_token", "")).strip()
        expires_in = int(payload.get("expires_in", 7200) or 7200)
        if not token:
            raise RuntimeError("wechat access token missing")

        WeeklyUpdateSubscriptionService._access_token = token
        WeeklyUpdateSubscriptionService._access_token_expires_at = now + max(60, expires_in)
        return token

    @staticmethod
    def _to_status_payload(
        record: WeeklyUpdateSubscription | None,
        *,
        template_id: str,
    ) -> dict:
        status = record.status if record else WeeklyUpdateSubscription.STATUS_INACTIVE
        available_count = max(0, int(record.available_count or 0)) if record else 0
        is_following = status == WeeklyUpdateSubscription.STATUS_ACTIVE
        return {
            "template_id": template_id,
            "status": status,
            "is_following": is_following,
            "available_count": available_count,
            "needs_resubscribe": is_following and available_count <= 0,
            "last_request_result": record.last_request_result if record else None,
            "last_prompt_source": record.last_prompt_source if record else None,
            "last_authorized_at": (
                record.last_authorized_at.isoformat() if record and record.last_authorized_at else None
            ),
            "last_sent_at": record.last_sent_at.isoformat() if record and record.last_sent_at else None,
            "total_accept_count": int(record.total_accept_count or 0) if record else 0,
            "total_reject_count": int(record.total_reject_count or 0) if record else 0,
            "total_sent_count": int(record.total_sent_count or 0) if record else 0,
        }

    @staticmethod
    def _normalize_prompt_source(value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _format_beijing_now() -> str:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        return now.strftime("%Y年%m月%d日 %H:%M")
