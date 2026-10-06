import pytest
import json
from gltest import *


def _to_hex(addr) -> str:
    """Helper to convert test address to lowercase hex."""
    if hasattr(addr, "as_hex"):
        return addr.as_hex.lower()
    if isinstance(addr, bytes):
        return "0x" + addr.hex().lower()
    return str(addr).lower()


def setup_post_message_hook(direct_vm):
    """Intercept cross-contract calls / emit_transfer to track recipient balances in tests."""
    def post_message_hook(vm, request):
        if "PostMessage" in request:
            pm = request["PostMessage"]
            dest_addr = pm["address"]
            value = int(pm.get("value", 0))
            dest_bytes = vm._to_bytes(dest_addr)
            vm._balances[dest_bytes] = vm._balances.get(dest_bytes, 0) + value
            return {"ok": None}
        if "EthSend" in request:
            es = request["EthSend"]
            dest_addr = es.get("to") or es.get("address") or es.get("recipient")
            value = int(es.get("value", 0))
            dest_bytes = vm._to_bytes(dest_addr)
            vm._balances[dest_bytes] = vm._balances.get(dest_bytes, 0) + value
            return {"ok": None}
        return None

    direct_vm._gl_call_hook = post_message_hook


@pytest.fixture
def contract(direct_deploy):
    c = direct_deploy("contracts/kol_promotion_escrow_x.py")
    import sys
    for name, mod in list(sys.modules.items()):
        if name == "genlayer.gl" or name.endswith(".gl"):
            if hasattr(mod, "vm") and hasattr(mod.vm, "UserError"):
                setattr(mod, "UserError", mod.vm.UserError)
        if "genlayer" in name and hasattr(mod, "gl"):
            gl_obj = getattr(mod, "gl")
            if hasattr(gl_obj, "vm") and hasattr(gl_obj.vm, "UserError"):
                setattr(gl_obj, "UserError", gl_obj.vm.UserError)
    return c


def test_initial_state(contract, direct_vm):
    """Verify clean initial state on contract deployment."""
    assert contract.get_campaign_count() == 0
    assert contract.get_owner() == _to_hex(direct_vm.sender)
    assert contract.is_social_domain_allowed("x.com") is True
    assert contract.is_social_domain_allowed("twitter.com") is True
    assert contract.is_social_domain_allowed("youtube.com") is True
    assert contract.is_social_domain_allowed("warpcast.com") is True
    assert contract.is_social_domain_allowed("mirror.xyz") is True
    assert contract.is_social_domain_allowed("untrusted-site.xyz") is False


def test_create_campaign_success(contract, direct_vm, direct_alice, direct_bob):
    """1. Test sponsor creating campaign with 5,000 GEN locked in escrow."""
    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer, #IntelligentContracts, $GEN",
        post_identifier="status/1888200100",
        retention_duration_sec=7200
    )
    assert str(cid) == "1"
    assert contract.get_campaign_count() == 1

    camp_data = json.loads(contract.get_campaign(cid))
    assert camp_data["campaign_id"] == "1"
    assert camp_data["sponsor"] == _to_hex(direct_alice)
    assert camp_data["kol"] == _to_hex(direct_bob)
    assert camp_data["brand_name"] == "GenLayer AI"
    assert camp_data["required_keywords"] == "#GenLayer, #IntelligentContracts, $GEN"
    assert camp_data["post_identifier"] == "status/1888200100"
    assert camp_data["post_url"] == ""
    assert camp_data["escrow_amount"] == "5000"
    assert camp_data["status"] == "CREATED"
    assert camp_data["verdict"] == "PENDING"
    assert int(camp_data["min_retention_deadline"]) == contract.get_current_time() + 7200


def test_create_campaign_validations(contract, direct_vm, direct_alice, direct_bob):
    """2. Test input validations when creating a campaign."""
    direct_vm.sender = direct_alice

    # Deposit <= 0
    direct_vm.value = 0
    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            kol=direct_bob,
            brand_name="GenLayer AI",
            required_keywords="#GenLayer",
            post_identifier="status/123",
            retention_duration_sec=3600
        )
    assert "Campaign funding must be greater than 0 GEN." in str(exc.value)

    direct_vm.value = 1000

    # Brand name < 2 chars
    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            kol=direct_bob,
            brand_name="G",
            required_keywords="#GenLayer",
            post_identifier="status/123",
            retention_duration_sec=3600
        )
    assert "brand_name must be at least 2 characters." in str(exc.value)

    # Required keywords < 3 chars
    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            kol=direct_bob,
            brand_name="GenLayer",
            required_keywords="ok",
            post_identifier="status/123",
            retention_duration_sec=3600
        )
    assert "required_keywords must specify at least one keyword/tag." in str(exc.value)

    # Post identifier < 3 chars
    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            kol=direct_bob,
            brand_name="GenLayer",
            required_keywords="#GenLayer",
            post_identifier="12",
            retention_duration_sec=3600
        )
    assert "post_identifier must be a valid post ID or handle." in str(exc.value)

    # Sponsor == KOL
    with pytest.raises(Exception) as exc:
        contract.create_campaign(
            kol=direct_alice,
            brand_name="GenLayer",
            required_keywords="#GenLayer",
            post_identifier="status/12345",
            retention_duration_sec=3600
        )
    assert "Sponsor cannot designate self as KOL." in str(exc.value)


def test_allowed_domain_management(contract, direct_vm, direct_bob):
    """3. Test adding custom social platforms to whitelist."""
    from genlayer import Address
    owner_addr = Address(contract.get_owner())
    direct_vm.sender = owner_addr

    assert contract.is_social_domain_allowed("threads.net") is False
    contract.add_allowed_social_domain("threads.net")
    assert contract.is_social_domain_allowed("threads.net") is True

    # Non-owner fails
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.add_allowed_social_domain("tiktok.com")
    assert "Only owner can add allowed domains." in str(exc.value)

    # Invalid domain length
    direct_vm.sender = owner_addr
    with pytest.raises(Exception) as exc:
        contract.add_allowed_social_domain("ab")
    assert "Invalid domain name." in str(exc.value)


def test_submit_post_success_and_validations(contract, direct_vm, direct_alice, direct_bob, direct_charlie):
    """4. Test KOL submitting live post URL and security checks."""
    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    # Non-existent campaign
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.submit_post("999", "https://x.com/user/status/1888200100")
    assert "Campaign not found." in str(exc.value)

    # Non-KOL cannot submit post
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception) as exc:
        contract.submit_post(cid, "https://x.com/user/status/1888200100")
    assert "Only designated KOL can submit post URL." in str(exc.value)

    # Invalid scheme
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.submit_post(cid, "ftp://x.com/user/status/1888200100")
    assert "post_url must start with http:// or https://" in str(exc.value)

    # Untrusted social domain
    with pytest.raises(Exception) as exc:
        contract.submit_post(cid, "https://scam-social.xyz/status/1888200100")
    assert "is not in the allowed platform whitelist." in str(exc.value)

    # Missing post identifier in URL (identifier spoofing)
    with pytest.raises(Exception) as exc:
        contract.submit_post(cid, "https://x.com/user/status/9999999999")
    assert "must canonically contain the specified identifier" in str(exc.value)

    # Successful submission
    valid_url = "https://x.com/crypto_kol/status/1888200100"
    contract.submit_post(cid, valid_url)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "SUBMITTED"
    assert c_data["post_url"] == valid_url


def test_cancel_expired_campaign_safe_recovery(contract, direct_vm, direct_alice, direct_bob):
    """5. Test safe sponsor recovery path if KOL never submits before deadline."""
    setup_post_message_hook(direct_vm)

    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    # Non-sponsor cannot cancel
    direct_vm.sender = direct_bob
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_campaign(cid)
    assert "Only sponsor can cancel expired campaign." in str(exc.value)

    # Cannot cancel before retention deadline
    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_campaign(cid)
    assert "Campaign retention deadline has not elapsed yet." in str(exc.value)

    # Warp past deadline (2 hours later)
    direct_vm.warp("2026-06-01T12:00:00Z")

    contract.cancel_expired_campaign(cid)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "CANCELLED"
    assert c_data["verdict"] == "POST_DELETED_OR_MISSING"

    # Sponsor received 5,000 GEN full refund
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 5000

    # Cannot cancel again
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_campaign(cid)
    assert "Campaign already cancelled." in str(exc.value)


def test_cannot_cancel_submitted_campaign(contract, direct_vm, direct_alice, direct_bob):
    """6. Test that sponsor cannot cancel campaign once KOL has submitted post."""
    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    direct_vm.sender = direct_bob
    contract.submit_post(cid, "https://x.com/crypto_kol/status/1888200100")

    # Warp past deadline
    direct_vm.warp("2026-06-01T12:00:00Z")

    direct_vm.sender = direct_alice
    with pytest.raises(Exception) as exc:
        contract.cancel_expired_campaign(cid)
    assert "Cannot cancel campaign once post has been submitted." in str(exc.value)


def test_adjudicate_campaign_premature_rejection(contract, direct_vm, direct_alice, direct_bob):
    """7. Test rejection of premature adjudication before retention period elapses."""
    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    # Calling adjudicate when CREATED (not SUBMITTED)
    with pytest.raises(Exception) as exc:
        contract.adjudicate_campaign(cid)
    assert "Campaign must be in SUBMITTED state to adjudicate." in str(exc.value)

    direct_vm.sender = direct_bob
    contract.submit_post(cid, "https://x.com/crypto_kol/status/1888200100")

    # Calling adjudicate at 30 minutes in (before 60 min deadline)
    direct_vm.warp("2026-06-01T10:30:00Z")
    with pytest.raises(Exception) as exc:
        contract.adjudicate_campaign(cid)
    assert "Minimum retention duration has not elapsed yet; cannot adjudicate premature post." in str(exc.value)


def test_adjudicate_campaign_fulfilled_payout(contract, direct_vm, direct_alice, direct_bob):
    """
    8. Scenario CAMPAIGN_FULFILLED:
    Post remains live past retention window, promotes GenLayer AI, and contains required hashtags.
    Consensus disburses 100% escrow (5,000 GEN) to KOL.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer, #IntelligentContracts, $GEN",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    direct_vm.sender = direct_bob
    post_url = "https://x.com/crypto_kol/status/1888200100"
    contract.submit_post(cid, post_url)

    # Warp past retention duration
    direct_vm.warp("2026-06-01T11:05:00Z")

    # Mock web rendering of Twitter post
    post_content = (
        "Huge update! Check out GenLayer AI building the next generation of smart contracts! "
        "Intelligent Contracts allow subjective consensus on-chain. #GenLayer #IntelligentContracts $GEN"
    )
    direct_vm.mock_web(".*x\\.com.*", {"status": 200, "body": post_content})

    # Mock LLM verdict
    direct_vm.mock_llm(
        ".*",
        json.dumps({
            "verdict": "CAMPAIGN_FULFILLED",
            "confidence": 98,
            "reason": "Post is live, actively endorses GenLayer AI, and includes all required hashtags."
        })
    )

    contract.adjudicate_campaign(cid)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "SETTLED"
    assert c_data["verdict"] == "CAMPAIGN_FULFILLED"

    # Verify KOL received 5,000 GEN payout
    bob_bytes = direct_vm._to_bytes(direct_bob)
    assert direct_vm._balances.get(bob_bytes, 0) == 5000


def test_adjudicate_campaign_terms_breached(contract, direct_vm, direct_alice, direct_bob):
    """
    9. Scenario TERMS_BREACHED:
    Post is live but fails mandatory hashtag/keyword criteria or disparages brand.
    Consensus refunds 100% escrow (5,000 GEN) to sponsor.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer, #IntelligentContracts, $GEN",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    direct_vm.sender = direct_bob
    post_url = "https://x.com/crypto_kol/status/1888200100"
    contract.submit_post(cid, post_url)

    # Warp past retention duration
    direct_vm.warp("2026-06-01T11:05:00Z")

    # Web rendering shows post without required keywords
    post_content = "Just had coffee with friends today. Nice weather in Singapore!"
    direct_vm.mock_web(".*x\\.com.*", {"status": 200, "body": post_content})

    direct_vm.mock_llm(
        ".*",
        json.dumps({
            "verdict": "TERMS_BREACHED",
            "confidence": 95,
            "reason": "Post is live but completely omits brand name and all required campaign hashtags."
        })
    )

    contract.adjudicate_campaign(cid)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "CANCELLED"
    assert c_data["verdict"] == "TERMS_BREACHED"

    # Verify sponsor received 5,000 GEN refund
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 5000


def test_adjudicate_post_deleted_or_missing(contract, direct_vm, direct_alice, direct_bob):
    """
    10. Scenario POST_DELETED_OR_MISSING:
    KOL deleted post before retention deadline expired, or page returns 404 / 'this tweet was deleted'.
    Consensus refunds 100% escrow (5,000 GEN) to sponsor.
    """
    setup_post_message_hook(direct_vm)

    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 5000

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer, #IntelligentContracts, $GEN",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    direct_vm.sender = direct_bob
    post_url = "https://x.com/crypto_kol/status/1888200100"
    contract.submit_post(cid, post_url)

    # Warp past retention duration
    direct_vm.warp("2026-06-01T11:05:00Z")

    # Web content returns deletion indicator
    deleted_content = "Twitter Error: This tweet was deleted by the author. 404 Not Found."
    direct_vm.mock_web(".*x\\.com.*", {"status": 404, "body": deleted_content})

    contract.adjudicate_campaign(cid)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "CANCELLED"
    assert c_data["verdict"] == "POST_DELETED_OR_MISSING"

    # Verify sponsor received 5,000 GEN refund
    alice_bytes = direct_vm._to_bytes(direct_alice)
    assert direct_vm._balances.get(alice_bytes, 0) == 5000


def test_llm_markdown_json_resilience(contract, direct_vm, direct_alice, direct_bob):
    """11. Test resilience against markdown formatted JSON response (```json ... ```)."""
    setup_post_message_hook(direct_vm)

    direct_vm.warp("2026-06-01T10:00:00Z")
    direct_vm.sender = direct_alice
    direct_vm.value = 2500

    cid = contract.create_campaign(
        kol=direct_bob,
        brand_name="GenLayer AI",
        required_keywords="#GenLayer",
        post_identifier="status/1888200100",
        retention_duration_sec=3600
    )

    direct_vm.sender = direct_bob
    contract.submit_post(cid, "https://x.com/crypto_kol/status/1888200100")

    direct_vm.warp("2026-06-01T11:05:00Z")

    direct_vm.mock_web(".*x\\.com.*", {"status": 200, "body": "Great partnership with GenLayer AI! #GenLayer"})
    direct_vm.mock_llm(
        ".*",
        "```json\n"
        '{\n  "verdict": "CAMPAIGN_FULFILLED",\n  "confidence": 99,\n  "reason": "Markdown-wrapped JSON response"\n}\n'
        "```"
    )

    contract.adjudicate_campaign(cid)

    c_data = json.loads(contract.get_campaign(cid))
    assert c_data["status"] == "SETTLED"
    assert c_data["verdict"] == "CAMPAIGN_FULFILLED"


def test_views_and_helpers(contract, direct_vm):
    """12. Test read-only views and contract metadata getters."""
    assert contract.get_current_time() >= 0
    assert contract.get_campaign_count() == 0
    assert contract.get_owner() == _to_hex(direct_vm.sender)

    with pytest.raises(Exception) as exc:
        contract.get_campaign("9999")
    assert "Campaign not found." in str(exc.value)
