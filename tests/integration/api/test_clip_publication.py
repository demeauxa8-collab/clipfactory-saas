import pytest
from app.auth import CurrentUser
from app.routers import clips, jobs
from fastapi import HTTPException

pytestmark = pytest.mark.asyncio


async def test_intermediate_clips_are_hidden_until_completion_commits(
    db_pool, account, monkeypatch
):
    user = CurrentUser(str(account[0]), None, "authenticated")
    monkeypatch.setattr(clips, "get_pool", lambda: db_pool)
    monkeypatch.setattr(jobs, "get_pool", lambda: db_pool)
    monkeypatch.setattr(
        clips, "presigned_get_url", lambda *args, **kwargs: "https://example.com/clip"
    )
    monkeypatch.setattr(
        clips.analytics, "fire_and_forget", lambda coroutine: coroutine.close()
    )
    async with db_pool.acquire() as conn:
        job_id = await conn.fetchval(
            """insert into jobs (user_id, source_url, target_clip_count,
            credits_estimated, status) values ($1, 'https://youtu.be/test', 3, 1, 'rendering')
            returning id""",
            account[0],
        )
        clip_id = await conn.fetchval(
            """insert into clips (job_id, user_id, idx, start_seconds,
            end_seconds, r2_key) values ($1, $2, 0, 0, 14, 'attempt/0.mp4') returning id""",
            job_id,
            account[0],
        )
        async with conn.transaction():
            await conn.execute("set local role authenticated")
            await conn.fetchval(
                "select set_config('request.jwt.claim.sub', $1, true)", user.user_id
            )
            assert await conn.fetchval("select count(*) from clips") == 0
    assert (await jobs.get_job(str(job_id), user)).clips == []
    with pytest.raises(HTTPException) as error:
        await clips.download_clip(str(clip_id), user)
    assert error.value.status_code == 404
    async with db_pool.acquire() as conn:
        await conn.execute("update jobs set status = 'completed' where id = $1", job_id)
        async with conn.transaction():
            await conn.execute("set local role authenticated")
            await conn.fetchval(
                "select set_config('request.jwt.claim.sub', $1, true)", user.user_id
            )
            assert await conn.fetchval("select count(*) from clips") == 1
    assert len((await jobs.get_job(str(job_id), user)).clips) == 1
    assert (
        await clips.download_clip(str(clip_id), user)
    ).url == "https://example.com/clip"
