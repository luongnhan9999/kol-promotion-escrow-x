# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json


def _addr_str(addr: Address) -> str:
    """Safely format an Address instance into a lowercase hex string."""
    try:
        return addr.as_hex.lower()
    except Exception:
        return str(addr).lower()


def _get_sender() -> Address:
    """Safely obtain transaction sender across GenVM runtime versions."""
    try:
        return gl.message.sender
    except Exception:
        try:
            return gl.message.sender_address
        except Exception:
            raise gl.UserError("Cannot resolve sender address.")


def _safe_transfer(recipient: Address, amount: bigint) -> None:
    """Safely disburse native GEN to an address using official GenLayer SDK pattern."""
    if amount <= bigint(0):
        return
    gl.get_contract_at(recipient).emit_transfer(value=u256(int(amount)))


DEFAULT_SOCIAL_DOMAINS = (
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "youtube.com",
    "www.youtube.com",
    "linkedin.com",
    "www.linkedin.com",
    "medium.com",
    "www.medium.com",
    "mirror.xyz",
    "warpcast.com",
    "mock-social.genlayer.com",
)


def _parse_url_host(raw_url: str) -> str:
    """Extract and validate normalized hostname from URL."""
    clean = raw_url.strip()
    if "?" in clean:
        clean = clean.split("?")[0]
    if "#" in clean:
        clean = clean.split("#")[0]
    clean = clean.strip()

    if clean.startswith("https://"):
        rest = clean[8:]
    elif clean.startswith("http://"):
        rest = clean[7:]
    else:
        raise gl.UserError("URL must begin with http:// or https://")

    host = rest.split("/", 1)[0].strip().lower()
    if ":" in host:
        host = host.split(":")[0].strip()
    if not host:
        raise gl.UserError("Invalid URL: missing host")
    return host


@allow_storage
@dataclass
class PromotionCampaign:
    campaign_id: str
    sponsor: Address
    kol: Address
    brand_name: str
    required_keywords: str       # Comma-separated mandatory keywords/hashtags
    post_identifier: str         # Target post/tweet id or video handle
    post_url: str                # Public URL of the publication
    escrow_amount: bigint        # Total payout locked in escrow
    status: str                  # "CREATED", "SUBMITTED", "SETTLED", "CANCELLED"
    verdict: str                 # "PENDING", "CAMPAIGN_FULFILLED", "TERMS_BREACHED", "POST_DELETED_OR_MISSING"
    reason: str                  # Consensus explanation
    min_retention_deadline: bigint # Must remain live until this timestamp
    created_at: bigint
    resolved_at: bigint


class Contract(gl.Contract):
    """
    KOLPromotionEscrowX: Performance-Driven Influencer Marketing & Social Bounty Protocol
    Track: Agentic Commerce Infrastructure / Future of Work
    """
    owner: Address
    campaign_count: bigint
    campaigns: TreeMap[str, PromotionCampaign]
    custom_allowed_domains: TreeMap[str, bool]

    def __init__(self):
        # GenVM automatically initializes TreeMap storage fields to empty.
        self.owner = _get_sender()
        self.campaign_count = bigint(0)

    def _get_current_timestamp(self) -> bigint:
        """Derive trusted deterministic execution timestamp from GenLayer transaction context."""
        try:
            from datetime import datetime
            dt_raw = getattr(gl.message, "datetime", None)
            if dt_raw is None and hasattr(gl, "message_raw") and isinstance(gl.message_raw, dict):
                dt_raw = gl.message_raw.get("datetime")
            if dt_raw:
                dt_str = str(dt_raw).strip().replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str)
                ts = int(dt.timestamp())
                if ts > 0:
                    return bigint(ts)
        except Exception:
            pass

        try:
            if hasattr(gl, "block") and hasattr(gl.block, "timestamp"):
                ts = int(gl.block.timestamp)
                if ts > 0:
                    return bigint(ts)
        except Exception:
            pass

        return bigint(0)

    def _parse_llm_json(self, text: str) -> dict:
        """Safely parse LLM responses, stripping markdown wrappers if present."""
        try:
            cleaned = str(text).strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            return json.loads(cleaned.strip())
        except Exception as e:
            return {
                "verdict": "POST_DELETED_OR_MISSING",
                "confidence": 0,
                "reason": f"Failed to parse LLM JSON: {str(e)[:100]}"
            }

    @gl.public.write
    def add_allowed_social_domain(self, domain: str) -> None:
        """Owner can add trusted social platform domains."""
        if _addr_str(_get_sender()) != _addr_str(self.owner):
            raise gl.UserError("Only owner can add allowed domains.")
        clean = domain.strip().lower()
        if len(clean) < 3:
            raise gl.UserError("Invalid domain name.")
        self.custom_allowed_domains[clean] = True

    @gl.public.view
    def is_social_domain_allowed(self, domain: str) -> bool:
        """Check if social platform domain is whitelisted."""
        clean = domain.strip().lower()
        if clean in DEFAULT_SOCIAL_DOMAINS:
            return True
        try:
            return bool(self.custom_allowed_domains[clean])
        except Exception:
            return False

    @gl.public.write.payable
    def create_campaign(
        self,
        kol: Address,
        brand_name: str,
        required_keywords: str,
        post_identifier: str,
        retention_duration_sec: int
    ) -> str:
        """
        Sponsor locks campaign funding in escrow for a designated KOL.
        """
        deposit = bigint(gl.message.value)
        if deposit <= bigint(0):
            raise gl.UserError("Campaign funding must be greater than 0 GEN.")

        clean_brand = brand_name.strip()
        clean_kw = required_keywords.strip()
        clean_id = post_identifier.strip()

        if len(clean_brand) < 2:
            raise gl.UserError("brand_name must be at least 2 characters.")
        if len(clean_kw) < 3:
            raise gl.UserError("required_keywords must specify at least one keyword/tag.")
        if len(clean_id) < 3:
            raise gl.UserError("post_identifier must be a valid post ID or handle.")

        if _addr_str(_get_sender()) == _addr_str(kol):
            raise gl.UserError("Sponsor cannot designate self as KOL.")

        duration = bigint(retention_duration_sec if retention_duration_sec >= 3600 else 3600)
        now_ts = self._get_current_timestamp()
        deadline = now_ts + duration if now_ts > bigint(0) else bigint(86400 * 3)

        self.campaign_count += bigint(1)
        cid = str(self.campaign_count)

        self.campaigns[cid] = PromotionCampaign(
            campaign_id=cid,
            sponsor=_get_sender(),
            kol=kol,
            brand_name=clean_brand,
            required_keywords=clean_kw,
            post_identifier=clean_id,
            post_url="",
            escrow_amount=deposit,
            status="CREATED",
            verdict="PENDING",
            reason="Campaign active. Awaiting published post submission by KOL.",
            min_retention_deadline=deadline,
            created_at=self.campaign_count,
            resolved_at=bigint(0)
        )

        return cid

    @gl.public.write
    def submit_post(self, campaign_id: str, post_url: str) -> None:
        """
        KOL submits published content URL before or during active campaign.
        """
        if campaign_id not in self.campaigns:
            raise gl.UserError("Campaign not found.")

        camp = self.campaigns[campaign_id]
        if _addr_str(_get_sender()) != _addr_str(camp.kol):
            raise gl.UserError("Only designated KOL can submit post URL.")

        if camp.status == "SETTLED":
            raise gl.UserError("Campaign already settled.")
        if camp.status == "CANCELLED":
            raise gl.UserError("Campaign is cancelled.")

        clean_url = post_url.strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            raise gl.UserError("post_url must start with http:// or https://")

        # Canonical Domain Whitelist
        host = _parse_url_host(clean_url)
        is_allowed = host in DEFAULT_SOCIAL_DOMAINS
        if not is_allowed:
            try:
                is_allowed = bool(self.custom_allowed_domains[host])
            except Exception:
                is_allowed = False

        if not is_allowed:
            raise gl.UserError(f"Social host '{host}' is not in the allowed platform whitelist.")

        # Post Identifier Binding (Ensure URL matches designated post)
        if camp.post_identifier.lower() not in clean_url.lower():
            raise gl.UserError(f"Post URL must canonically contain the specified identifier '{camp.post_identifier}'.")

        camp.post_url = clean_url
        camp.status = "SUBMITTED"
        camp.reason = "Post submitted. Awaiting retention period maturity for adjudication."
        self.campaigns[campaign_id] = camp

    @gl.public.write
    def cancel_expired_campaign(self, campaign_id: str) -> None:
        """
        Safe Sponsor Recovery Path:
        If KOL never submits post URL before the campaign retention deadline, sponsor recovers 100% refund.
        """
        if campaign_id not in self.campaigns:
            raise gl.UserError("Campaign not found.")

        camp = self.campaigns[campaign_id]
        if _addr_str(_get_sender()) != _addr_str(camp.sponsor):
            raise gl.UserError("Only sponsor can cancel expired campaign.")

        if camp.status == "SETTLED":
            raise gl.UserError("Campaign already settled.")
        if camp.status == "CANCELLED":
            raise gl.UserError("Campaign already cancelled.")
        if camp.status == "SUBMITTED":
            raise gl.UserError("Cannot cancel campaign once post has been submitted.")

        now_ts = self._get_current_timestamp()
        if now_ts > bigint(0) and now_ts <= camp.min_retention_deadline:
            raise gl.UserError("Campaign retention deadline has not elapsed yet.")

        refund_amt = camp.escrow_amount
        camp.status = "CANCELLED"
        camp.verdict = "POST_DELETED_OR_MISSING"
        camp.reason = "Campaign cancelled by sponsor after KOL missed submission window."
        camp.resolved_at = self.campaign_count
        self.campaigns[campaign_id] = camp

        if refund_amt > bigint(0):
            _safe_transfer(camp.sponsor, refund_amt)

    @gl.public.write
    def adjudicate_campaign(self, campaign_id: str) -> None:
        """
        Validators inspect the live post URL after the minimum retention duration,
        verifying that the post is still live and fulfills all keyword/brand criteria.
        """
        if campaign_id not in self.campaigns:
            raise gl.UserError("Campaign not found.")

        camp = self.campaigns[campaign_id]
        if camp.status != "SUBMITTED":
            raise gl.UserError("Campaign must be in SUBMITTED state to adjudicate.")

        now_ts = self._get_current_timestamp()
        if now_ts > bigint(0) and now_ts < camp.min_retention_deadline:
            raise gl.UserError("Minimum retention duration has not elapsed yet; cannot adjudicate premature post.")

        brand_local = str(camp.brand_name)
        kw_local = str(camp.required_keywords)
        url_local = str(camp.post_url)
        post_id_local = str(camp.post_identifier)

        def leader_fn():
            web_content = ""
            try:
                res = gl.nondet.web.render(url_local, mode="text")
                if hasattr(res, "content"):
                    web_content = res.content
                elif isinstance(res, dict) and "body" in res:
                    web_content = res["body"]
                else:
                    web_content = str(res)
            except Exception:
                web_content = ""

            lower_web = web_content[:500].lower() if web_content else ""
            if len(web_content.strip()) < 15 or "404 not found" in lower_web or "page doesn't exist" in lower_web or "this tweet was deleted" in lower_web:
                return {
                    "verdict": "POST_DELETED_OR_MISSING",
                    "confidence": 100,
                    "reason": "Post is deleted, offline, or inaccessible."
                }

            snippet = web_content[:4000]

            prompt = f"""You are an Objective Social Media Sponsorship & Influencer Marketing Auditor on GenLayer.
Verify whether the following published social media post satisfies the agreed sponsorship campaign criteria.

CAMPAIGN PARAMETERS:
- BRAND NAME: {brand_local}
- REQUIRED KEYWORDS / HASHTAGS: {kw_local}
- TARGET IDENTIFIER: {post_id_local}
- TARGET URL: {url_local}

OBSERVED SOCIAL POST CONTENT:
\"\"\"
{snippet}
\"\"\"

AUDIT VERIFICATION RULES:
Classify into strictly ONE of the following outcomes:
- "CAMPAIGN_FULFILLED": The post is live, visibly promotes '{brand_local}', and includes the required hashtags/keywords ({kw_local}) in a positive or compliant promotional context.
- "TERMS_BREACHED": The post is live, but it omits the required keywords, attacks/disparages the brand, or violates explicit campaign terms.
- "POST_DELETED_OR_MISSING": The post was deleted, hidden, restricted, or returns empty/unrelated content.

OUTPUT FORMAT:
Respond ONLY with a VALID JSON object (no markdown, no backticks):
{{
  "verdict": "CAMPAIGN_FULFILLED" | "TERMS_BREACHED" | "POST_DELETED_OR_MISSING",
  "confidence": <integer from 0 to 100>,
  "reason": "<concise explanation max 220 characters>"
}}"""

            try:
                raw_res = gl.nondet.exec_prompt(prompt, response_format="json")
                parsed = None
                if isinstance(raw_res, dict):
                    parsed = raw_res
                elif hasattr(raw_res, "content") and isinstance(raw_res.content, dict):
                    parsed = raw_res.content
                else:
                    text = raw_res.content if hasattr(raw_res, "content") else str(raw_res)
                    cleaned = str(text).strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    elif cleaned.startswith("```"):
                        cleaned = cleaned[3:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    parsed = json.loads(cleaned.strip())

                verdict_candidate = str(parsed.get("verdict", "POST_DELETED_OR_MISSING")).strip().upper()
                valid_verdicts = ("CAMPAIGN_FULFILLED", "TERMS_BREACHED", "POST_DELETED_OR_MISSING")
                if verdict_candidate not in valid_verdicts:
                    verdict_candidate = "POST_DELETED_OR_MISSING"

                try:
                    conf = int(parsed.get("confidence", 0))
                    conf = max(0, min(100, conf))
                except Exception:
                    conf = 50

                reason_str = str(parsed.get("reason", "Audited by autonomous social jury."))[:220]

                return {
                    "verdict": verdict_candidate,
                    "confidence": conf,
                    "reason": reason_str
                }
            except Exception as e:
                return {
                    "verdict": "POST_DELETED_OR_MISSING",
                    "confidence": 0,
                    "reason": f"Evaluation fault: {str(e)[:100]}"
                }

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            leader = leader_res.calldata
            if not isinstance(leader, dict) or "verdict" not in leader:
                return False

            valid_verdicts = ("CAMPAIGN_FULFILLED", "TERMS_BREACHED", "POST_DELETED_OR_MISSING")
            l_verdict = str(leader.get("verdict", "")).strip().upper()
            if l_verdict not in valid_verdicts:
                return False

            mine = leader_fn()
            m_verdict = str(mine.get("verdict", "")).strip().upper()

            # DISCRETE EQUIVALENCE: 100% agreement on exact promotion outcome
            return l_verdict == m_verdict

        adjudication_res = gl.vm.run_nondet(leader_fn, validator_fn)
        if isinstance(adjudication_res, dict):
            final_res = adjudication_res
        else:
            final_res = self._parse_llm_json(str(adjudication_res))

        verdict = str(final_res.get("verdict", "POST_DELETED_OR_MISSING")).strip().upper()
        valid_verdicts = ("CAMPAIGN_FULFILLED", "TERMS_BREACHED", "POST_DELETED_OR_MISSING")
        if verdict not in valid_verdicts:
            verdict = "POST_DELETED_OR_MISSING"

        reason = str(final_res.get("reason", "Consensus concluded."))

        camp.verdict = verdict
        camp.reason = reason
        camp.resolved_at = self.campaign_count

        payout = camp.escrow_amount

        if verdict == "CAMPAIGN_FULFILLED":
            # Successful campaign: Disburse payment to KOL
            camp.status = "SETTLED"
            self.campaigns[campaign_id] = camp
            _safe_transfer(camp.kol, payout)

        else:
            # Breach or deleted post: Refund escrow to sponsor
            camp.status = "CANCELLED"
            self.campaigns[campaign_id] = camp
            _safe_transfer(camp.sponsor, payout)

    @gl.public.view
    def get_campaign(self, campaign_id: str) -> str:
        """Retrieve details of a promotion campaign as a JSON string."""
        if campaign_id not in self.campaigns:
            raise gl.UserError("Campaign not found.")
        c = self.campaigns[campaign_id]
        return json.dumps({
            "campaign_id": c.campaign_id,
            "sponsor": _addr_str(c.sponsor),
            "kol": _addr_str(c.kol),
            "brand_name": c.brand_name,
            "required_keywords": c.required_keywords,
            "post_identifier": c.post_identifier,
            "post_url": c.post_url,
            "escrow_amount": str(c.escrow_amount),
            "status": c.status,
            "verdict": c.verdict,
            "reason": c.reason,
            "min_retention_deadline": str(c.min_retention_deadline),
            "created_at": str(c.created_at),
            "resolved_at": str(c.resolved_at)
        })

    @gl.public.view
    def get_current_time(self) -> int:
        """Retrieve current contract execution timestamp."""
        return int(str(self._get_current_timestamp()))

    @gl.public.view
    def get_campaign_count(self) -> int:
        return int(self.campaign_count)

    @gl.public.view
    def get_owner(self) -> str:
        return _addr_str(self.owner)
