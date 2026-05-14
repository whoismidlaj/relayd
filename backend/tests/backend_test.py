"""Relayd backend integration tests — full suite.

Covers: auth (register/login/me/logout + brute force), domains (CRUD + DNS +
verify), mailboxes, aliases, relays, send/test, logs, stats, deliverability,
and multi-tenant isolation.
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin123"


# ---------- Fixtures ----------
def _new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_client():
    s = _new_session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def user_a():
    """Fresh user A — registers a brand-new user and returns logged-in session."""
    s = _new_session()
    email = f"test_a_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "name": "User A"})
    assert r.status_code == 200, r.text
    s.email = email  # type: ignore
    return s


@pytest.fixture(scope="session")
def user_b():
    s = _new_session()
    email = f"test_b_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!", "name": "User B"})
    assert r.status_code == 200, r.text
    s.email = email  # type: ignore
    return s


# ---------- Health ----------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Relayd"
        assert body["status"] == "ok"

    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json()["ok"] is True


# ---------- Auth ----------
class TestAuth:
    def test_register_creates_user_and_sets_cookies(self):
        s = _new_session()
        email = f"test_reg_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == email
        assert data["role"] == "user"
        assert "id" in data
        assert "access_token" in s.cookies
        assert "refresh_token" in s.cookies

    def test_register_duplicate(self):
        s = _new_session()
        email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        assert s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!"}).status_code == 200
        r = s.post(f"{API}/auth/register", json={"email": email, "password": "Passw0rd!"})
        assert r.status_code == 400

    def test_login_admin_sets_cookies(self):
        s = _new_session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "access_token" in s.cookies

    def test_me_with_cookie(self, admin_client):
        r = admin_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_cookie_401(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout_clears_cookies(self):
        s = _new_session()
        assert s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 200
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # After logout, /me should 401
        s2 = _new_session()
        # Re-issue with same cookies cleared
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 401

    def test_brute_force_lockout(self):
        s = _new_session()
        email = f"test_bf_{uuid.uuid4().hex[:8]}@example.com"
        # Register first
        s.post(f"{API}/auth/register", json={"email": email, "password": "RightPass!"})
        s2 = _new_session()
        last_status = None
        for i in range(6):
            r = s2.post(f"{API}/auth/login", json={"email": email, "password": "wrong"})
            last_status = r.status_code
        # After 5 failed attempts, expect 429
        assert last_status == 429, f"Expected 429 on 6th attempt, got {last_status}"


# ---------- Domains ----------
class TestDomains:
    def test_create_and_list_domain(self, user_a):
        name = f"test-{uuid.uuid4().hex[:8]}.example.com"
        r = user_a.post(f"{API}/domains", json={"name": name})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == name
        assert data["dkim_public_key"]
        assert "id" in data
        user_a.domain_id = data["id"]  # type: ignore
        user_a.domain_name = name  # type: ignore

        # List
        r2 = user_a.get(f"{API}/domains")
        assert r2.status_code == 200
        ids = [d["id"] for d in r2.json()]
        assert data["id"] in ids

    def test_dns_records(self, user_a):
        r = user_a.get(f"{API}/domains/{user_a.domain_id}/dns")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["domain"] == user_a.domain_name
        assert body["selector"] == "mail"
        rec_names = {x["type"] if isinstance(x, dict) and "type" in x else None for x in body["records"]} if isinstance(body["records"], list) else set(body["records"].keys())
        # Accept either dict-keyed or list with type field; ensure all 4 logical record kinds present
        rec_text = str(body["records"]).lower()
        for kind in ["spf", "dkim", "dmarc", "mx"]:
            assert kind in rec_text, f"Missing {kind} record"

    def test_verify_domain(self, user_a):
        r = user_a.post(f"{API}/domains/{user_a.domain_id}/verify")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "checks" in body
        assert "score" in body
        assert isinstance(body["score"], int)
        assert 0 <= body["score"] <= 100
        for k in ["spf", "dkim", "dmarc", "mx"]:
            assert k in body["checks"]

    def test_verify_against_real_domain_structure(self, user_a):
        # Create a domain pointing to a real DNS-resolvable name to validate structure
        name = "google.com"
        # Use a unique selector/mail_host since user_a may already have google.com? Use try/except.
        r = user_a.post(f"{API}/domains", json={"name": name, "dkim_selector": "google", "mail_host": "smtp"})
        if r.status_code == 400:
            pytest.skip("google.com already exists for this user")
        assert r.status_code == 200
        did = r.json()["id"]
        v = user_a.post(f"{API}/domains/{did}/verify")
        assert v.status_code == 200
        body = v.json()
        assert isinstance(body["score"], int) and 0 <= body["score"] <= 100
        # SPF for google.com should be valid in real DNS
        spf = body["checks"]["spf"]
        assert isinstance(spf, dict)
        # cleanup
        user_a.delete(f"{API}/domains/{did}")

    def test_delete_domain_cascades(self, user_a):
        # Create a fresh domain with mailbox + alias
        name = f"casc-{uuid.uuid4().hex[:8]}.example.com"
        d = user_a.post(f"{API}/domains", json={"name": name}).json()
        mb = user_a.post(f"{API}/mailboxes", json={
            "local_part": "u1", "domain_id": d["id"], "password": "pw123456"
        })
        assert mb.status_code == 200, mb.text
        al = user_a.post(f"{API}/aliases", json={
            "local_part": "info", "domain_id": d["id"], "destinations": ["x@example.org"]
        })
        assert al.status_code == 200, al.text

        # Delete domain
        r = user_a.delete(f"{API}/domains/{d['id']}")
        assert r.status_code == 200
        # Verify cascade
        mailboxes = user_a.get(f"{API}/mailboxes").json()
        aliases = user_a.get(f"{API}/aliases").json()
        assert not any(m["domain_id"] == d["id"] for m in mailboxes)
        assert not any(a["domain_id"] == d["id"] for a in aliases)


# ---------- Mailboxes ----------
class TestMailboxes:
    def test_create_update_delete(self, user_a):
        # Use the domain created in TestDomains
        d_list = user_a.get(f"{API}/domains").json()
        assert d_list, "User A should have at least one domain"
        did = d_list[0]["id"]

        local = f"u{uuid.uuid4().hex[:6]}"
        r = user_a.post(f"{API}/mailboxes", json={
            "local_part": local, "domain_id": did, "password": "secret123"
        })
        assert r.status_code == 200, r.text
        mb = r.json()
        assert "@" in mb["address"]
        assert mb["local_part"] == local
        assert "password_hash" not in mb
        mid = mb["id"]

        # Duplicate
        dup = user_a.post(f"{API}/mailboxes", json={
            "local_part": local, "domain_id": did, "password": "secret123"
        })
        assert dup.status_code == 400

        # Update
        up = user_a.patch(f"{API}/mailboxes/{mid}", json={"display_name": "New Name", "quota_mb": 2048})
        assert up.status_code == 200
        assert up.json()["display_name"] == "New Name"
        assert up.json()["quota_mb"] == 2048

        # Delete
        rd = user_a.delete(f"{API}/mailboxes/{mid}")
        assert rd.status_code == 200

    def test_mailbox_requires_own_domain(self, user_a, user_b):
        d_a = user_a.get(f"{API}/domains").json()[0]["id"]
        # user_b tries to create mailbox on user_a's domain
        r = user_b.post(f"{API}/mailboxes", json={
            "local_part": "x", "domain_id": d_a, "password": "x12345"
        })
        assert r.status_code == 404


# ---------- Aliases ----------
class TestAliases:
    def test_alias_crud_and_catchall(self, user_a):
        did = user_a.get(f"{API}/domains").json()[0]["id"]
        # catch-all
        r = user_a.post(f"{API}/aliases", json={
            "local_part": "*", "domain_id": did, "destinations": ["dest@x.com"]
        })
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["catch_all"] is True
        assert a["enabled"] is True

        # list
        lst = user_a.get(f"{API}/aliases").json()
        assert any(x["id"] == a["id"] for x in lst)

        # delete
        rd = user_a.delete(f"{API}/aliases/{a['id']}")
        assert rd.status_code == 200


# ---------- Relays ----------
class TestRelays:
    def test_create_relay_and_default_exclusivity(self, user_a):
        r1 = user_a.post(f"{API}/relays", json={
            "name": "Resend-1", "type": "resend",
            "config": {"api_key": "re_invalid_xxxxxxxxxxxxxxxxxxxxxx", "from_default": "no-reply@example.com"},
            "is_default": True,
        })
        assert r1.status_code == 200, r1.text
        relay1 = r1.json()
        assert relay1["is_default"] is True
        # api_key should be masked
        assert "••" in relay1["config"]["api_key"]
        user_a.relay1_id = relay1["id"]  # type: ignore

        r2 = user_a.post(f"{API}/relays", json={
            "name": "SMTP-Backup", "type": "smtp",
            "config": {"host": "smtp.example.com", "port": 587, "username": "u", "password": "p"},
            "is_default": True,
        })
        assert r2.status_code == 200
        # Now r1 should no longer be default
        lst = user_a.get(f"{API}/relays").json()
        defaults = [x for x in lst if x["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == r2.json()["id"]

        # password masked
        smtp_relay = next(x for x in lst if x["id"] == r2.json()["id"])
        assert "••" in smtp_relay["config"]["password"]

        # PATCH change default back exclusively
        up = user_a.patch(f"{API}/relays/{user_a.relay1_id}", json={"is_default": True})
        assert up.status_code == 200
        lst2 = user_a.get(f"{API}/relays").json()
        defaults2 = [x for x in lst2 if x["is_default"]]
        assert len(defaults2) == 1
        assert defaults2[0]["id"] == user_a.relay1_id


# ---------- Send Test ----------
class TestSendAndLogs:
    def test_send_with_invalid_relay_creates_failed_log(self, user_a):
        # Use the resend relay (invalid api_key) — expect failed but log row created
        relay_id = user_a.relay1_id  # type: ignore
        r = user_a.post(f"{API}/send/test", json={
            "from_email": "no-reply@example.com",
            "to": "recipient@example.com",
            "subject": "Test",
            "body": "Hello",
            "relay_id": relay_id,
            "use_failover": False,
        })
        assert r.status_code == 200, r.text
        log = r.json()
        assert log["status"] == "failed"
        assert log["error"]
        assert log["provider_id"] is None or log["provider_id"] == relay_id

        # verify log persisted via /logs
        logs = user_a.get(f"{API}/logs").json()
        assert any(x.get("subject") == "Test" and x["status"] == "failed" for x in logs)
        user_a.last_log_id = next(x["id"] for x in logs if x.get("subject") == "Test")  # type: ignore

    def test_send_without_relay_uses_default(self, user_a):
        r = user_a.post(f"{API}/send/test", json={
            "from_email": "no-reply@example.com",
            "to": "recipient@example.com",
            "subject": "DefaultRoute",
            "body": "Hi",
        })
        assert r.status_code == 200
        # status is failed (invalid keys) but request is accepted
        assert r.json()["status"] in ("sent", "failed")

    def test_retry_log(self, user_a):
        lid = user_a.last_log_id  # type: ignore
        r = user_a.post(f"{API}/logs/{lid}/retry")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_delete_log(self, user_a):
        lid = user_a.last_log_id  # type: ignore
        r = user_a.delete(f"{API}/logs/{lid}")
        assert r.status_code == 200


# ---------- Stats + Deliverability ----------
class TestStats:
    def test_stats(self, user_a):
        r = user_a.get(f"{API}/stats")
        assert r.status_code == 200
        data = r.json()
        for k in ["domains", "mailboxes", "aliases", "relays", "sent", "failed"]:
            assert k in data, f"Missing {k} in stats"
            assert isinstance(data[k], int)

    def test_deliverability(self, user_a):
        r = user_a.get(f"{API}/deliverability")
        assert r.status_code == 200
        body = r.json()
        assert "domains" in body
        for d in body["domains"]:
            assert "score" in d and isinstance(d["score"], int)
            assert "checks" in d


# ---------- Multi-tenant isolation ----------
class TestIsolation:
    def test_user_b_cannot_see_user_a_resources(self, user_a, user_b):
        # user_b's domain list should NOT include user_a's domain ids
        a_domains = {d["id"] for d in user_a.get(f"{API}/domains").json()}
        b_domains = {d["id"] for d in user_b.get(f"{API}/domains").json()}
        assert a_domains.isdisjoint(b_domains)

        # user_b cannot fetch user_a's domain by id
        if a_domains:
            sample = next(iter(a_domains))
            r = user_b.get(f"{API}/domains/{sample}")
            assert r.status_code == 404

        # relays / logs / aliases / mailboxes isolation
        a_relays = {r["id"] for r in user_a.get(f"{API}/relays").json()}
        b_relays = {r["id"] for r in user_b.get(f"{API}/relays").json()}
        assert a_relays.isdisjoint(b_relays)

        a_logs = {l["id"] for l in user_a.get(f"{API}/logs").json()}
        b_logs = {l["id"] for l in user_b.get(f"{API}/logs").json()}
        assert a_logs.isdisjoint(b_logs)

    def test_user_b_cannot_modify_user_a_relay(self, user_a, user_b):
        a_relays = user_a.get(f"{API}/relays").json()
        if not a_relays:
            pytest.skip("no relays for user A")
        rid = a_relays[0]["id"]
        r = user_b.patch(f"{API}/relays/{rid}", json={"name": "hacked"})
        assert r.status_code == 404
        r2 = user_b.delete(f"{API}/relays/{rid}")
        assert r2.status_code == 404
