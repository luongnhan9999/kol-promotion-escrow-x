# KOLPromotionEscrowX — Performance-Driven Influencer Marketing & Social Bounty Protocol

> **Track:** Agentic Commerce Infrastructure / Future of Work  
> **Network:** GenLayer studionet (Chain ID: `61999` / `0xF1EF`)  
> **Contract Address:** `0x9A48C21b58FE331E627a696417A6305a415D4Ec3`  
> **Target Environment:** [GenLayer Studio](https://studio.genlayer.com)  
> **Execution Engine:** GenVM / Optimistic Democracy Subjective Consensus  
> **Package / SDK:** `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`  
> **Test Suite:** 13 unit tests passing (`gltest` / `pytest`)

---

## 1. Deployment & Studionet Overview

The `KOLPromotionEscrowX` Intelligent Contract is designed and configured for deployment on **GenLayer studionet**:

- **Contract Source:** [`contracts/kol_promotion_escrow_x.py`](contracts/kol_promotion_escrow_x.py)
- **Target Network:** `studionet` (Chain ID: `61999` / `0xF1EF`)
- **Deployment Platform:** [GenLayer Studio](https://studio.genlayer.com)
- **RPC Endpoint:** `https://studio.genlayer.com/api`

### Studionet Quick Deployment Steps:
1. Open [GenLayer Studio](https://studio.genlayer.com).
2. Create a new contract file: `kol_promotion_escrow_x.py` and paste the contents of `contracts/kol_promotion_escrow_x.py`.
3. Verify that line 1 contains the exact pragma comment:
   ```python
   # { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
   ```
4. Compile and deploy via the **Run & Debug** panel.
5. Fund the sponsor address using the Studio **Accounts** panel native faucet.

---

## 2. Executive Summary & Problem Statement

In the rapidly expanding global creator and influencer marketing economy ($24B+ market size), brand sponsorships and paid social promotions face severe counterparty risks and qualitative enforcement challenges:

1. **Premature Post Deletion**: Influencers receive upfront payment or milestone releases, only to archive or delete promotional posts shortly afterward to keep their personal profiles clean.
2. **Defective or Diluted Deliverables**: Posts omit mandatory campaign hashtags, exclude tracking links, spell sponsor brands incorrectly, or surround endorsements with satirical or disparaging commentary.
3. **The Traditional Smart Contract Blindspot**: Solidity and EVM contracts are fundamentally isolated from the open web. They cannot inspect social media pages without relying on centralized, custodial API scrapers or manual multisig arbiters—introducing single points of compromise, high operational overhead, and extortion risks.

### The GenLayer Solution
**KOLPromotionEscrowX** solves this by establishing a decentralized, autonomous escrow and adjudication engine directly on GenLayer:
- **Trustless Funding Escrow**: Sponsors lock bounty funds into intelligent escrow with immutable rules (brand name, mandatory hashtags/keywords, post identifier, and minimum retention deadline).
- **Direct Web Scraping On-Chain**: GenLayer validators scrape live social pages directly (`gl.nondet.web.render`) without intermediary oracles.
- **Subjective LLM Consensus**: Independent validator LLMs inspect the observed social media content and vote on semantic compliance (`gl.vm.run_nondet`).
- **Cryptographic & Economic Determinism**: 100% discrete consensus releases payment to the KOL upon fulfilled retention, or triggers automated refunds to the sponsor if terms are breached or posts deleted.

---

## 3. Protocol Architecture & Operational Flow

```
+-------------------------------------------------------------------------------------------------------+
|                                      KOLPromotionEscrowX Workflow                                     |
+-------------------------------------------------------------------------------------------------------+

   [Sponsor / Brand]                            [KOL / Influencer]                    [GenLayer Validators]
           |                                             |                                      |
           | 1. create_campaign()                        |                                      |
           |    (Locks GEN Escrow: Brand, Keywords,      |                                      |
           |     Post ID, Retention Duration)            |                                      |
           +-------------------------------------------->|                                      |
           |                                             |                                      |
           |                                             | 2. submit_post()                     |
           |                                             |    (Canonical URL: X, YouTube, etc.) |
           |                                             +------------------------------------->|
           |                                                                                    |
           |                                3. [Wait for Retention Duration to Mature]          |
           |                                                                                    |
           |                                4. adjudicate_campaign()                            |
           |                                   - Scrapes live social post via web.render        |
           |                                   - LLM Jury evaluates Keywords & Post Integrity   |
           |                                   - Discrete Consensus on Verdict                  |
           |<-----------------------------------------------------------------------------------+
           |
   [Settlement Outcomes]
   * CAMPAIGN_FULFILLED      : 100% Escrow disbursed to KOL. Status becomes SETTLED.
   * TERMS_BREACHED          : 100% Escrow refunded to Sponsor. Status becomes CANCELLED.
   * POST_DELETED_OR_MISSING : 100% Escrow refunded to Sponsor. Status becomes CANCELLED.
   * SAFE RECOVERY (EXPIRED) : If KOL misses submission deadline, Sponsor calls cancel_expired_campaign()
                               for a 100% refund.
```

### Why GenLayer is Mandatory ("Without GenLayer, the project fails")
- **No Web3 Equivalent**: Solidity contracts cannot fetch dynamic social web content or comprehend text context without centralized web2 oracles.
- **Subjective Qualitative Evaluation**: Deciding whether an influencer post satisfies promotional guidelines while rejecting subtle malicious mocking or hashtag omission requires natural language understanding at the consensus layer.
- **Validator Equivalence & Sandboxing**: `gl.vm.run_nondet` enables independent validator nodes to execute autonomous web extraction and LLM inference while enforcing discrete consensus on categorical verdicts (`CAMPAIGN_FULFILLED`, `TERMS_BREACHED`, `POST_DELETED_OR_MISSING`).

---

## 4. Security Pillars & Economic Determinism

### A. Canonical Social Domain Whitelisting
To prevent spoofing attacks, phishing links, and arbitrary URL submissions, the contract strictly verifies that submitted URLs belong to recognized, reputable content platforms:
- **Default Supported Platforms**:
  - `x.com`, `twitter.com`
  - `youtube.com`
  - `linkedin.com`
  - `medium.com`
  - `mirror.xyz`
  - `warpcast.com`
  - `mock-social.genlayer.com` (Simulated testnet staging)
- **Extensible Registry**: The contract owner can whitelist additional creator platforms via `add_allowed_social_domain()`.

### B. Post Identifier URL Binding
The protocol validates that the registered post identifier (e.g., tweet status ID, video handle) is canonically contained within the submitted URL:
```python
if camp.post_identifier.lower() not in clean_url.lower():
    raise gl.UserError(f"Post URL must canonically contain the specified identifier '{camp.post_identifier}'.")
```
This guarantees an influencer cannot submit a link to another user's post or an unrelated campaign update.

### C. Enforced Retention Duration & Anti-Premature Settlement
A core vector in influencer fraud is deleting content shortly after claiming payment. `KOLPromotionEscrowX` enforces an immutable retention period:
```python
now_ts = self._get_current_timestamp()
if now_ts > bigint(0) and now_ts < camp.min_retention_deadline:
    raise gl.UserError("Minimum retention duration has not elapsed yet; cannot adjudicate premature post.")
```
Adjudication can only proceed after the agreed duration has matured, guaranteeing that the post has remained accessible to the audience for the entire contracted window.

### D. Safe Sponsor Recovery Path
If an influencer fails to publish or submit a post within the agreed campaign window, the sponsor is never permanently locked out of their funds:
```python
@gl.public.write
def cancel_expired_campaign(self, campaign_id: str) -> None:
    # Allows 100% refund to sponsor once retention deadline elapses without post submission
```

### E. Discrete Semantic Equivalence Consensus
Rather than forcing validators to agree on identical word-for-word explanations, `validator_fn` compares the normalized categorical verdict:
```python
def validator_fn(leader_res) -> bool:
    # Verifies leader output and ensures 100% discrete consensus on verdict outcome
    mine = leader_fn()
    return leader.get("verdict") == mine.get("verdict")
```
This guarantees high Byzantine fault tolerance while eliminating spurious consensus failures caused by stylistic LLM output variations.

---

## 5. State Machine & Consensus Verdicts

| Status | Verdict | Trigger Condition | Financial Settlement |
|---|---|---|---|
| `CREATED` | `PENDING` | Sponsor creates campaign and deposits GEN | Escrow locked in contract |
| `SUBMITTED` | `PENDING` | KOL submits valid social post URL | Escrow retained pending maturity |
| `SETTLED` | `CAMPAIGN_FULFILLED` | Post is live, keyword criteria met, duration passed | **100% disbursed to KOL** |
| `CANCELLED` | `TERMS_BREACHED` | Post is missing keywords or violates campaign terms | **100% refunded to Sponsor** |
| `CANCELLED` | `POST_DELETED_OR_MISSING` | Post was deleted, inaccessible, or returns 404 | **100% refunded to Sponsor** |
| `CANCELLED` | `POST_DELETED_OR_MISSING` | Sponsor cancels after KOL missed submission window | **100% refunded to Sponsor** |

---

## 6. Contract API Reference

### Write Methods
- `create_campaign(kol: Address, brand_name: str, required_keywords: str, post_identifier: str, retention_duration_sec: int) -> str`
  - *Payable*: Locks native GEN in escrow for the campaign.
  - Validates minimum string lengths, duration ($\ge 3600$s), and non-self designation.
- `submit_post(campaign_id: str, post_url: str) -> None`
  - Executed by the designated KOL to submit live publication URL.
  - Validates domain against whitelist and checks post identifier presence.
- `cancel_expired_campaign(campaign_id: str) -> None`
  - Executed by sponsor if KOL fails to submit before retention deadline.
  - Issues 100% escrow refund to sponsor.
- `adjudicate_campaign(campaign_id: str) -> None`
  - Triggers GenLayer decentralized validator jury to scrape the URL and evaluate compliance.
  - Disburses funds to KOL on fulfillment or refunds sponsor on breach/deletion.
- `add_allowed_social_domain(domain: str) -> None`
  - Owner-restricted function to add newly supported platforms (e.g. `threads.net`, `bluesky.app`).

### View Methods
- `get_campaign(campaign_id: str) -> str`: Returns full campaign state and verdict metadata as a serialized JSON string.
- `is_social_domain_allowed(domain: str) -> bool`: Returns whether a given domain is whitelisted.
- `get_current_time() -> int`: Returns current execution timestamp.
- `get_campaign_count() -> int`: Returns total count of created campaigns.
- `get_owner() -> str`: Returns contract deployer address.

---

## 7. Testing & Verification

The test suite covers end-to-end functionality including state transitions, input boundary checks, role permissions, web mocking, LLM consensus outcomes, and time-travel retention enforcement using `gltest`.

### Running Unit Tests
```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run full pytest suite
pytest -v
```

### Test Coverage Highlights:
- ✅ `test_initial_state`: Validates deployment state and default whitelisted domains.
- ✅ `test_create_campaign_success`: Verifies escrow locking and campaign metadata storage.
- ✅ `test_create_campaign_validations`: Enforces zero-deposit prevention, minimum length constraints, and anti-self-sponsorship.
- ✅ `test_allowed_domain_management`: Verifies owner controls over whitelist additions and non-owner rejections.
- ✅ `test_submit_post_success_and_validations`: Validates protocol schemes, domain checks, identifier binding, and KOL authentication.
- ✅ `test_cancel_expired_campaign_safe_recovery`: Tests time warping, deadline enforcement, and 100% sponsor refunds.
- ✅ `test_cannot_cancel_submitted_campaign`: Guards against malicious sponsor cancellation once content is submitted.
- ✅ `test_adjudicate_campaign_premature_rejection`: Prevents premature review before retention window matures.
- ✅ `test_adjudicate_campaign_fulfilled_payout`: Simulates successful live post review and 100% payout to KOL.
- ✅ `test_adjudicate_campaign_terms_breached`: Simulates missing keyword detection and 100% refund to sponsor.
- ✅ `test_adjudicate_post_deleted_or_missing`: Simulates 404/deleted tweet detection and automated sponsor refund.
- ✅ `test_llm_markdown_json_resilience`: Verifies robust parsing of markdown-wrapped JSON LLM responses.
- ✅ `test_views_and_helpers`: Confirms view method accuracy.

---

## 8. Frontend Integration (`genlayer-js`)

To interact with the deployed contract in a web dApp, connect via `genlayer-js` using `studionet`:

```javascript
import { createClient } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

// Initialize client with connected browser wallet
const client = createClient({
  chain: studionet,
  account: userAddress
});

const CONTRACT_ADDRESS = "0x9A48C21b58FE331E627a696417A6305a415D4Ec3";

// 1. Create a campaign with escrow deposit
async function createCampaign(kolAddress, brand, keywords, postId, retentionSec, genAmount) {
  const tx = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "create_campaign",
    args: [kolAddress, brand, keywords, postId, retentionSec],
    value: genAmount // in wei
  });
  return tx;
}

// 2. KOL submits published post link
async function submitPost(campaignId, postUrl) {
  const tx = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "submit_post",
    args: [campaignId, postUrl]
  });
  return tx;
}

// 3. Adjudicate campaign after retention maturity
async function adjudicateCampaign(campaignId) {
  const tx = await client.writeContract({
    address: CONTRACT_ADDRESS,
    functionName: "adjudicate_campaign",
    args: [campaignId]
  });
  return tx;
}
```

---

## 9. License

This repository is distributed under the MIT Open Source License.
