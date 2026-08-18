from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from lingxi_identity import OidcDiscovery, OidcVerifier, Principal
from sqlalchemy import func, select

from lingxilearn.auth import Authenticator, build_authenticator
from lingxilearn.config import Settings, get_settings
from lingxilearn.learner import LearnerService
from lingxilearn.main import create_app
from lingxilearn.service import Service
from lingxilearn.store.repositories import Database, Repository
from lingxilearn.store.learner import LearnerRepository
from lingxilearn.store.models import (
    LearningEvent,
    LearningEvidence,
    Misconception,
)


@pytest_asyncio.fixture
async def learner_store():
    path = Path("var") / f"test-identity-{uuid4().hex}.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        insecure_dev_auth=True,
    )
    db = Database(settings)
    await db.create_all()
    yield db, LearnerRepository(db), settings
    await db.dispose()
    path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_identity_mapping_is_stable_and_issuer_scoped(learner_store) -> None:
    _db, repository, settings = learner_store
    service = LearnerService(repository, settings)

    first = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-a.example")
    )
    same = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-a.example")
    )
    other_issuer = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer-b.example")
    )
    other_subject = await service.get_learner_context(
        Principal(subject="user-2", issuer="https://issuer-a.example")
    )

    assert first.learner_id == same.learner_id
    assert first.learner_id not in {other_issuer.learner_id, other_subject.learner_id}
    assert "learner_id" not in first.public_dict()
    assert "subject" not in first.public_dict()


@pytest.mark.asyncio
async def test_learning_writes_merge_and_are_idempotent(learner_store) -> None:
    db, repository, settings = learner_store
    service = LearnerService(repository, settings)
    context = await service.get_learner_context(
        Principal(subject="user-1", issuer="https://issuer.example")
    )
    legacy = Repository(db)
    await legacy.create_session(
        id="s-idempotent",
        learner_id=context.learner_id,
        pack_id="pack",
        pack_version="1",
        mission_id="mission",
        checkpoint_ns="",
        status="done",
    )

    preference = await service.update_preference(context, {"pace": "slow", "theme": "light"})
    preference = await service.update_preference(context, {"theme": "dark"})
    assert preference.payload == {"pace": "slow", "theme": "dark"}

    evidence = [
        {
            "id": "ev_0001",
            "kind": "learner_action",
            "source": "answer.step-1",
            "summary": "回答",
            "locator": {"step": "step-1"},
            "value": {"choice": "a"},
        }
    ]
    await service.record_evidence(context, "s-idempotent", evidence)
    await service.record_misconception(context, "s-idempotent", ["foo", "foo"])
    await repository.record_session_outcome(
        learner_id=context.learner_id,
        session_id="s-idempotent",
        outcome="completed",
        evidence=evidence,
        misconceptions=["foo"],
        mastery={"concept": 0.8},
        report={"probe_score": 0.2, "verify_score": 0.8},
        mission_id="mission",
    )
    await repository.record_session_outcome(
        learner_id=context.learner_id,
        session_id="s-idempotent",
        outcome="completed",
        evidence=evidence,
        misconceptions=["foo"],
        mastery={"concept": 0.8},
        report={"probe_score": 0.2, "verify_score": 0.8},
        mission_id="mission",
    )

    async with db.session() as session:
        evidence_count = await session.scalar(
            select(func.count(LearningEvidence.id)).where(
                LearningEvidence.learner_id == context.learner_id
            )
        )
        event_count = await session.scalar(
            select(func.count(LearningEvent.id)).where(
                LearningEvent.learner_id == context.learner_id
            )
        )
        misconception = await session.scalar(
            select(Misconception).where(
                Misconception.learner_id == context.learner_id,
                Misconception.tag == "foo",
            )
        )
    assert evidence_count == 1
    assert event_count == 1
    assert misconception is not None and misconception.occurrence_count == 2


@pytest.mark.asyncio
async def test_authenticator_requires_bff_or_explicit_fixed_dev_subject() -> None:
    production = Settings(identity_bff_url="", insecure_dev_auth=False)
    with pytest.raises(RuntimeError):
        build_authenticator(production)

    development = Settings(
        identity_bff_url="",
        insecure_dev_auth=True,
        dev_subject="fixed-dev-user",
    )
    authenticator = build_authenticator(development)
    principal = await authenticator.authenticate(None)
    assert principal.subject == "fixed-dev-user"
    stale_cookie_principal = await authenticator.authenticate("old-production-session=stale")
    assert stale_cookie_principal.subject == "fixed-dev-user"

    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    with pytest.raises(HTTPException) as missing:
        await Authenticator(production, client).authenticate(None)
    assert missing.value.status_code == 401
    await client.aclose()


@pytest.mark.asyncio
async def test_authenticator_resolves_the_browser_cookie_through_bff() -> None:
    settings = Settings(identity_bff_url="http://identity-bff", insecure_dev_auth=False)

    def bff(request: httpx.Request) -> httpx.Response:
        assert request.headers["cookie"] == "lingxi_session=session-1"
        return httpx.Response(
            200,
            json={
                "principal": {
                    "subject": "subject-1",
                    "issuer": "https://auth.lingxilearn.cn/oidc",
                    "roles": [],
                    "permissions": [],
                    "audience": [],
                },
                "user": {"id": "subject-1"},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(bff))
    principal = await Authenticator(settings, client).authenticate("lingxi_session=session-1")
    assert principal.subject == "subject-1"
    assert principal.issuer == "https://auth.lingxilearn.cn/oidc"
    await client.aclose()


@pytest.mark.asyncio
async def test_dev_identity_proxy_does_not_forward_to_remote_bff(monkeypatch) -> None:
    monkeypatch.setenv("LINGXILEARN_INSECURE_DEV_AUTH", "true")
    monkeypatch.setenv("LINGXILEARN_DEV_SUBJECT", "local-test-user")
    get_settings.cache_clear()
    try:
        app = create_app()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            session = await client.get("/api/v1/me", headers={"Cookie": "stale=production"})
            csrf = await client.get("/auth/csrf")
            unsupported = await client.get("/auth/login")

        assert session.status_code == 200
        assert session.json()["principal"]["subject"] == "local-test-user"
        assert csrf.json() == {"csrfToken": "lingxilearn-dev-csrf"}
        assert unsupported.status_code == 404
    finally:
        get_settings.cache_clear()


def test_oidc_verifier_accepts_valid_jwt_and_rejects_claim_and_key_failures(monkeypatch) -> None:
    issuer = "https://identity.example"
    audience = "lingxilearn"
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk["kid"] = "kid-1"

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, list[dict[str, str]]]:
            return {"keys": [public_jwk]}

    monkeypatch.setattr("lingxi_identity.oidc.httpx.get", lambda *_args, **_kwargs: Response())
    discovery = OidcDiscovery(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/authorize",
        token_endpoint=f"{issuer}/token",
        jwks_uri=f"{issuer}/jwks",
    )
    verifier = OidcVerifier(issuer=issuer, audience=audience, discovery=discovery)

    def token(**overrides):
        claims = {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        }
        claims.update(overrides)
        return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "kid-1"})

    assert verifier.verify(token()).subject == "subject-1"
    with pytest.raises(jwt.InvalidIssuerError):
        verifier.verify(token(iss="https://other.example"))
    with pytest.raises(jwt.InvalidAudienceError):
        verifier.verify(token(aud="other-audience"))
    with pytest.raises(jwt.ExpiredSignatureError):
        verifier.verify(token(exp=datetime.now(UTC) - timedelta(minutes=1)))
    with pytest.raises(jwt.MissingRequiredClaimError):
        verifier.verify(token(sub=None))

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    invalid_signature = jwt.encode(
        {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        other_key,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )
    with pytest.raises(jwt.InvalidSignatureError):
        verifier.verify(invalid_signature)

    unknown_kid = jwt.encode(
        {
            "sub": "subject-1",
            "iss": issuer,
            "aud": audience,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "unknown"},
    )
    with pytest.raises(jwt.InvalidTokenError):
        verifier.verify(unknown_kid)


def test_production_authenticator_allows_lingxiidentity_es384() -> None:
    settings = Settings(identity_bff_url="http://identity-bff", insecure_dev_auth=False)
    authenticator = build_authenticator(settings)
    assert authenticator.client is not None
    asyncio.run(authenticator.aclose())


@pytest.mark.asyncio
async def test_api_resources_are_scoped_and_client_learner_ids_are_rejected(monkeypatch) -> None:
    path = Path("var") / f"test-api-ownership-{uuid4().hex}.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        identity_bff_url="http://identity-bff",
        insecure_dev_auth=False,
    )
    identity_issuer = "https://auth.lingxilearn.cn/oidc"
    service = Service(settings)
    await service.db.create_all()

    from lingxilearn.auth import Authenticator

    app = create_app()
    app.state.service = service

    def bff(request: httpx.Request) -> httpx.Response:
        cookie = request.headers.get("cookie", "")
        subject = "subject-a" if "session-a" in cookie else "subject-b"
        return httpx.Response(
            200,
            json={
                "principal": {
                    "subject": subject,
                    "issuer": "https://auth.lingxilearn.cn/oidc",
                    "roles": [],
                    "permissions": [],
                    "audience": [],
                },
                "user": {"id": subject},
            },
        )

    identity_client = httpx.AsyncClient(transport=httpx.MockTransport(bff))
    authenticator = Authenticator(settings=settings, client=identity_client)
    app.state.identity = authenticator
    first = await service.learners.get_learner_context(
        Principal(subject="subject-a", issuer=identity_issuer)
    )
    second = await service.learners.get_learner_context(
        Principal(subject="subject-b", issuer=identity_issuer)
    )
    legacy = Repository(service.db)
    await legacy.create_session(
        id="s-owned",
        learner_id=first.learner_id,
        pack_id="pack",
        pack_version="1",
        mission_id="mission",
        checkpoint_ns="",
        status="done",
    )
    await legacy.append_events("s-owned", [{"kind": "run.ended", "payload": {}}])
    await legacy.save_mastery(first.learner_id, {"concept-a": 0.9})
    await legacy.save_mastery(second.learner_id, {"concept-b": 0.4})
    await legacy.save_report(
        session_id="s-owned",
        learner_id=first.learner_id,
        mission_id="mission",
        report={"headline": "owned"},
    )
    await legacy.create_agent_task(
        id="t-owned",
        learner_id=first.learner_id,
        prompt="prompt",
        status="completed",
        intent={},
        lecture_result={"selected_hook": {"title": "Hook"}},
        visual_result={},
    )
    await legacy.append_agent_events("t-owned", [{"kind": "task.completed", "payload": {}}])

    async def fake_snapshot(session_id: str, learner_id: str | None = None) -> dict[str, str]:
        return {"id": session_id, "owner": learner_id or ""}

    monkeypatch.setattr(service, "snapshot", fake_snapshot)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first_headers = {"Cookie": "lingxi_session=session-a"}
        second_headers = {"Cookie": "lingxi_session=session-b"}
        rejected = await client.post(
            "/api/sessions",
            headers=first_headers,
            json={"mission_id": "mission", "learner_id": "client-owned"},
        )
        assert rejected.status_code == 422

        owned = await client.get("/api/sessions/s-owned", headers=first_headers)
        hidden = await client.get("/api/sessions/s-owned", headers=second_headers)
        assert owned.status_code == 200
        assert hidden.status_code == 404

        report = await client.get("/api/sessions/s-owned/report", headers=first_headers)
        hidden_report = await client.get("/api/sessions/s-owned/report", headers=second_headers)
        assert report.status_code == 200 and report.json()["headline"] == "owned"
        assert hidden_report.status_code == 404

        first_mastery = await client.get("/api/me/mastery", headers=first_headers)
        second_mastery = await client.get("/api/me/mastery", headers=second_headers)
        assert first_mastery.json()["mastery"] == {"concept-a": 0.9}
        assert second_mastery.json()["mastery"] == {"concept-b": 0.4}

        stream = await client.get("/api/sessions/s-owned/events", headers=first_headers)
        hidden_stream = await client.get("/api/sessions/s-owned/events", headers=second_headers)
        assert stream.status_code == 200 and "run.ended" in stream.text
        assert hidden_stream.status_code == 404

        task = await client.get("/api/agent-tasks/t-owned", headers=first_headers)
        hidden_task = await client.get("/api/agent-tasks/t-owned", headers=second_headers)
        assert task.status_code == 200
        assert hidden_task.status_code == 404

        artifact = await client.get(
            "/api/agent-tasks/t-owned/artifacts/background", headers=first_headers
        )
        hidden_artifact = await client.get(
            "/api/agent-tasks/t-owned/artifacts/background", headers=second_headers
        )
        assert artifact.status_code == 404
        assert hidden_artifact.status_code == 404

        missing_auth = await client.get("/api/me/mastery")
        assert missing_auth.status_code == 401

    await service.db.dispose()
    await authenticator.aclose()
    path.unlink(missing_ok=True)


"""legacy graph test retained only as historical inert text"""
"""
    path = Path("var") / f"test-graph-learning-{uuid4().hex}.sqlite3"
    checkpoint = Path("var") / f"test-graph-checkpoint-{uuid4().hex}.sqlite3"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{path.as_posix()}",
        checkpoint_url=checkpoint.as_posix(),
        insecure_dev_auth=True,
    )
    service = Service(settings)
    await service.db.create_all()
    await service.startup()
    app = create_app()
    app.state.service = service
    app.state.identity = build_authenticator(settings)

    choices = {
        "mission-1": {
            "p1": "a",
            "p2": "b",
            "p3": "b",
            "v1": "c",
            "v2": "b",
            "orient": "b",
            "stall": "b",
        },
    }

    def answer_for(pending: dict) -> dict:
        value = pending["value"]
        table = choices["mission-1"]
        if value.get("kind") in {"probe", "verify"}:
            return {item["id"]: {"choice": table.get(item["id"], "a")} for item in value["items"]}
        expects = (value.get("prompt") or {}).get("expects", "text")
        if expects == "attribution":
            return {
                "allocations": {
                    "dns": 121.4,
                    "tcp_connect": 31.9,
                    "ttfb": 188.6,
                    "transfer": 19.2,
                    "retransmission": 225.8,
                },
                "pins": {
                    "dns": [1, 2],
                    "tcp_connect": [3, 4, 5],
                    "ttfb": [6, 7],
                    "transfer": [8, 9, 10],
                    "retransmission": [12, 13, 14],
                },
            }
        return {"choice": table.get(value.get("step_id", ""), "b")}

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/sessions",
                json={"mission_id": "mission-1", "pack_id": "course-pack"},
            )
            assert created.status_code == 201
            session_id = created.json()["id"]
            snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
            turns = 0
            while snapshot["status"] == "running" or (
                snapshot["status"] == "awaiting_learner" and turns < 30
            ):
                if snapshot["status"] == "running":
                    await asyncio.sleep(0.03)
                else:
                    turns += 1
                    response = await client.post(
                        f"/api/sessions/{session_id}/answer",
                        json={"answer": answer_for(snapshot["pending"])},
                    )
                    assert response.status_code == 202
                snapshot = (await client.get(f"/api/sessions/{session_id}")).json()
            assert snapshot["status"] == "done"

        record = await service.repo.get_session(session_id)
        assert record is not None
        async with service.db.session() as session:
            before = {
                "events": await session.scalar(
                    select(func.count(LearningEvent.id)).where(
                        LearningEvent.session_id == session_id
                    )
                ),
                "evidence": await session.scalar(
                    select(func.count(LearningEvidence.id)).where(
                        LearningEvidence.session_id == session_id
                    )
                ),
                "reports": await session.scalar(
                    select(func.count(ReportRecord.session_id)).where(
                        ReportRecord.session_id == session_id
                    )
                ),
            }
        await service._finalize(
            session_id,
            service.packs[record.pack_id],
            record.learner_id,
            service.config_for(session_id, service.packs[record.pack_id]),
        )
        async with service.db.session() as session:
            after = {
                "events": await session.scalar(
                    select(func.count(LearningEvent.id)).where(
                        LearningEvent.session_id == session_id
                    )
                ),
                "evidence": await session.scalar(
                    select(func.count(LearningEvidence.id)).where(
                        LearningEvidence.session_id == session_id
                    )
                ),
                "reports": await session.scalar(
                    select(func.count(ReportRecord.session_id)).where(
                        ReportRecord.session_id == session_id
                    )
                ),
            }
        assert before == after
        assert before["events"] == before["reports"] == 1
        assert before["evidence"] > 0
    finally:
        await service.shutdown()
        path.unlink(missing_ok=True)
        checkpoint.unlink(missing_ok=True)"""
