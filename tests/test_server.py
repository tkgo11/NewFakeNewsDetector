import asyncio

import httpx

from newfakenewsdetector.server import create_app


def test_web_assets_and_api(monkeypatch):
    monkeypatch.delenv("GOOGLE_FACTCHECK_API_KEY", raising=False)
    app = create_app()

    async def check():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://127.0.0.1"
            ) as client,
        ):
            home = await client.get("/")
            assert home.status_code == 200
            assert "검증할 주장" in home.text
            assert (await client.get("/assets/app.js")).status_code == 200
            config = await client.get("/api/v1/config")
            assert config.json() == {"online_available": False}
            response = await client.post("/api/v1/check", json={"claim": "달은 스스로 빛을 낸다."})
            assert response.status_code == 200
            assert response.json()["verdict"] == "refuted"
            assert response.headers["cache-control"] == "no-store"
            assert "frame-ancestors 'none'" in home.headers["content-security-policy"]
            assert (await client.get("/openapi.json")).status_code == 200

    asyncio.run(check())


def test_reject_invalid_requests_and_nonlocal_host():
    app = create_app()

    async def check():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://127.0.0.1"
            ) as client,
        ):
            invalid = await client.post("/api/v1/check", json={"claim": "??"})
            assert invalid.status_code == 422
            invalid_opt_in = await client.post(
                "/api/v1/check", json={"claim": "The Moon reflects sunlight.", "online": "true"}
            )
            assert invalid_opt_in.status_code == 422
            plain = await client.post(
                "/api/v1/check",
                content='{"claim": "test claim"}',
                headers={"Content-Type": "text/plain"},
            )
            assert plain.status_code == 415
            other_host = await client.get("/", headers={"Host": "example.org"})
            assert other_host.status_code == 400

    asyncio.run(check())
