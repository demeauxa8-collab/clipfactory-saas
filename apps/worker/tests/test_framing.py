from app.pipeline.ffmpeg import (
    _framing_vf,
    _vertical_face_crop_vf,
    _vertical_fit_blur_vf,
)
from app.pipeline.vision import _coerce_face_center_x, _parse_vision


def test_face_crop_builds_full_height_9_16_window() -> None:
    vf = _vertical_face_crop_vf(0.5)
    # Full-height crop, even 9:16 width, then scale to the vertical canvas.
    assert vf.startswith("crop=floor(ih*9/16/2)*2:ih:")
    assert vf.endswith(",scale=1080:1920,setsar=1")
    # Commas inside min/max stay escaped so the filtergraph parser keeps one filter.
    assert "max(0\\,min(iw-ow\\,0.5000*iw-ow/2)):0" in vf


def test_face_crop_clamps_center_x() -> None:
    assert "1.0000*iw-ow/2" in _vertical_face_crop_vf(9.0)
    assert "0.0000*iw-ow/2" in _vertical_face_crop_vf(-3.0)


def test_face_crop_appends_subtitles_last() -> None:
    vf = _vertical_face_crop_vf(0.5, subtitles_path="/tmp/a:b/clip.ass")
    assert vf.rstrip().endswith("clip.ass'")
    # Same escaping as the fit+blur builder (colon escaped for the subtitles path).
    assert "subtitles='/tmp/a\\:b/clip.ass'" in vf


def test_framing_vf_defaults_to_fit_blur() -> None:
    assert _framing_vf(None) == _vertical_fit_blur_vf()
    assert _framing_vf(("fit_blur", 0.5)) == _vertical_fit_blur_vf()


def test_framing_vf_selects_face_crop() -> None:
    assert _framing_vf(("face_crop", 0.3)) == _vertical_face_crop_vf(0.3)


def test_coerce_face_center_x_clamps_and_tolerates_garbage() -> None:
    assert _coerce_face_center_x(0.42) == 0.42
    assert _coerce_face_center_x(2.0) == 1.0
    assert _coerce_face_center_x(-1.0) == 0.0
    assert _coerce_face_center_x(None) is None
    assert _coerce_face_center_x("nope") is None


def test_parse_vision_reads_new_fields() -> None:
    v = _parse_vision(
        {
            "decor": "studio",
            "person_visible": True,
            "energy": 80,
            "action": "talking head",
            "visual_score": 75,
            "face_center_x": 0.6,
            "burned_captions": True,
        }
    )
    assert v is not None
    assert v.face_center_x == 0.6
    assert v.burned_captions is True


def test_parse_vision_defaults_new_fields_when_absent() -> None:
    v = _parse_vision({"decor": "car", "visual_score": 50})
    assert v is not None
    assert v.face_center_x is None
    assert v.burned_captions is False
