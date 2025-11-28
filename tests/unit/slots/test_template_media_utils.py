from src.app.slots.template_media import merge_template_media, template_media_map


def test_merge_preserves_role_and_optional_and_updates_ids():
    base = [
        {"media_kind": "style", "media_object_id": "old-style", "role": "template", "optional": True}
    ]
    overrides = [
        {"media_kind": "style", "media_object_id": "new-style", "role": "template"},
        {"media_kind": "photo", "media_object_id": "photo-1", "role": "photo"},
    ]

    merged = merge_template_media(base, overrides, default_role="template")

    assert len(merged) == 2
    style = next(item for item in merged if item["media_kind"] == "style")
    assert style["media_object_id"] == "new-style"
    assert style["role"] == "template"
    assert style.get("optional") is True

    photo = next(item for item in merged if item["media_kind"] == "photo")
    assert photo["role"] == "photo"

    mapping = template_media_map(merged)
    assert mapping == {"style": "new-style", "photo": "photo-1"}


def test_merge_fills_default_role_when_missing():
    base = [{"media_kind": "style", "media_object_id": "old-style"}]
    merged = merge_template_media(base, [], default_role="template")
    assert merged[0]["role"] == "template"
