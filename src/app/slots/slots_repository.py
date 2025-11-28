"""Slot repository backed by SQLAlchemy."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Iterable

from sqlalchemy import delete
from sqlalchemy.orm import Session, selectinload

from ..db.db_models import SlotModel, SlotTemplateMediaModel
from .slots_models import Slot, SlotTemplateMedia
from .template_media import merge_template_media


class SlotRepository:
    """Provide access to slot configuration stored in the database."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def list_slots(self) -> Sequence[Slot]:
        with self._session_factory() as session:
            rows = (
                session.query(SlotModel)
                .options(selectinload(SlotModel.template_media))
                .order_by(SlotModel.id)
                .all()
            )
            return [self._to_domain(row) for row in rows]

    def get_slot(self, slot_id: str) -> Slot:
        with self._session_factory() as session:
            row = (
                session.query(SlotModel)
                .options(selectinload(SlotModel.template_media))
                .filter(SlotModel.id == slot_id)
                .one_or_none()
            )
            if row is None:
                raise KeyError(f"Slot '{slot_id}' not found")
            return self._to_domain(row)

    def list_template_media(self, slot_id: str) -> Sequence[SlotTemplateMedia]:
        with self._session_factory() as session:
            rows = (
                session.query(SlotTemplateMediaModel)
                .filter(SlotTemplateMediaModel.slot_id == slot_id)
                .order_by(SlotTemplateMediaModel.media_kind, SlotTemplateMediaModel.id)
                .all()
            )
            return [self._to_template_domain(row) for row in rows]

    def update_slot(
        self,
        slot_id: str,
        *,
        display_name: str,
        provider: str,
        operation: str,
        is_active: bool,
        size_limit_mb: int,
        settings: dict,
        template_media: Iterable[dict[str, str]],
        updated_by: str | None = None,
    ) -> Slot:
        """Persist slot configuration and return updated domain object."""
        with self._session_factory() as session:
            row = (
                session.query(SlotModel)
                .options(selectinload(SlotModel.template_media))
                .filter(SlotModel.id == slot_id)
                .one_or_none()
            )
            if row is None:
                raise KeyError(f"Slot '{slot_id}' not found")

            current_settings: dict = {}
            try:
                if row.settings_json:
                    current_settings = json.loads(row.settings_json)
            except json.JSONDecodeError:
                current_settings = {}

            merged_settings = dict(current_settings)
            merged_settings.update(settings or {})
            base_template = current_settings.get("template_media") or []
            merged_template_media = merge_template_media(
                base_template, template_media, default_role="template"
            )
            merged_settings["template_media"] = merged_template_media

            row.display_name = display_name
            row.provider = provider
            row.operation = operation
            row.is_active = is_active
            row.size_limit_mb = size_limit_mb
            row.settings_json = json.dumps(merged_settings)
            row.updated_by = updated_by
            row.version += 1
            row.updated_at = datetime.utcnow()

            session.execute(
                delete(SlotTemplateMediaModel).where(
                    SlotTemplateMediaModel.slot_id == slot_id
                )
            )
            for binding in merged_template_media:
                session.add(
                    SlotTemplateMediaModel(
                        slot_id=slot_id,
                        media_kind=binding["media_kind"],
                        media_object_id=binding["media_object_id"],
                    )
                )
            session.commit()
            session.refresh(row)
            return self._to_domain(row)

    @staticmethod
    def _to_domain(model: SlotModel) -> Slot:
        settings = {}
        try:
            if model.settings_json:
                settings = json.loads(model.settings_json)
        except json.JSONDecodeError:
            settings = {}
        role_by_kind: dict[str, str | None] = {}
        for entry in settings.get("template_media") or []:
            if not isinstance(entry, dict):
                continue
            media_kind = entry.get("media_kind")
            role = entry.get("role")
            if media_kind:
                role_by_kind[str(media_kind)] = role or "template"
        return Slot(
            id=model.id,
            provider=model.provider,
            operation=model.operation,
            display_name=model.display_name or model.id,
            settings=settings,
            size_limit_mb=model.size_limit_mb,
            is_active=model.is_active,
            version=model.version,
            updated_by=model.updated_by,
            template_media=[
                SlotRepository._to_template_domain(
                    media, role=role_by_kind.get(media.media_kind)
                )
                for media in model.template_media
            ],
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_template_domain(
        model: SlotTemplateMediaModel, *, role: str | None = None
    ) -> SlotTemplateMedia:
        return SlotTemplateMedia(
            id=model.id,
            slot_id=model.slot_id,
            media_kind=model.media_kind,
            media_object_id=model.media_object_id,
            role=role or "template",
        )
