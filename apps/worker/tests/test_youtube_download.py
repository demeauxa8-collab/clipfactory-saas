from types import SimpleNamespace

import pytest

from app.pipeline import ffmpeg


@pytest.mark.asyncio
async def test_download_retries_with_another_format_after_403(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ffmpeg,
        "get_settings",
        lambda: SimpleNamespace(yt_dlp_bin="yt-dlp", yt_dlp_cookies_from_browser=""),
    )
    (tmp_path / "source.mp4.part").write_bytes(b"unfinished")
    commands = []

    async def fake_run(cmd):
        commands.append(cmd)
        if len(commands) == 1:
            (tmp_path / "source.f136.mp4").write_bytes(b"partial video")
            return 1, "", "HTTP Error 403: Forbidden"
        (tmp_path / "source.mp4").write_bytes(b"finished video")
        return 0, "", ""

    monkeypatch.setattr(ffmpeg, "_run", fake_run)
    path = await ffmpeg.yt_dlp_download("https://www.youtube.com/watch?v=example", str(tmp_path))

    assert path == str((tmp_path / "source.mp4").resolve())
    assert len(commands) == 2
    assert "vcodec^=avc1" in commands[0][2]
    assert "vcodec^=avc1" not in commands[1][2]
    assert not (tmp_path / "source.mp4.part").exists()
    assert not (tmp_path / "source.f136.mp4").exists()
