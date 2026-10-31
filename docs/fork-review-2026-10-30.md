# Duke Energy fork review — 2026-10-30

## Scope and confidence

Reviewed the public GitHub search results for `aiodukeenergy fork:true` and `ha-dukeenergy fork:true`: 12 other client repositories and 12 other integration/related repositories, alongside the upstream and jameslb forks. Compared their default heads with hunterjm's default heads, inspected relevant changed source and documentation, and checked the open client PR branches described below. Two related repositories are outside the shared Git network. This is a snapshot, not an exhaustive review of every branch, hidden fork, or code path. Ahead/behind counts are relative to hunterjm, not jameslb, and do not establish code quality.

Local tests use synthetic data. Community reports are evidence of a workaround, not proof that this account will authenticate. Live sign-in remains necessary after installation.

## Fixes adopted in this change

| Source | Change | Validation and limits |
| --- | --- | --- |
| [aiodukeenergy PR 23](https://github.com/hunterjm/aiodukeenergy/pull/23) | Optional Chrome helper sends iOS Safari User-Agent and removes Chromium hints only on Duke's login domain. | Author reports desktop access_denied and successful mobile-style login. No extension was installed or browser settings changed during source work. |
| [aiodukeenergy PR 24](https://github.com/hunterjm/aiodukeenergy/pull/24) | Capture page shows Duke's OAuth error instead of a misleading generic missing-code message. | Errors use textContent; synthetic tests cover error text. |
| [aiodukeenergy PR 25](https://github.com/hunterjm/aiodukeenergy/pull/25) | Replace account-list with account/list and normalize missing source IDs and BP spelling. | Original author verified one NC electric account. Added mocked electric/gas multi-account tests, explicit source-ID retention, null/empty defaults, and cache preservation after refresh failure. |

Original authors and commit provenance are retained through cherry-picks. This fork also adds a complete callback URL copy action to the helper: the manual HA flow requires code AND transaction state. Code-only copy and legacy JWT-state redirects remain supported. HA's state, nonce, PKCE, and signature checks are unchanged.

## Recommended follow-ups

| Priority | Candidate | Assessment for jameslb |
| --- | --- | --- |
| High | Retry interrupted historical imports. [sam2kb coordinator](https://github.com/sam2kb/ha-dukeenergy/blob/97528fb848e4261e8132d5b8fc92eb794b9eb289/custom_components/duke_energy/coordinator.py) | Current jameslb history loop breaks on TimeoutError/ClientError. That can mistake a transient outage for the end of history. Port a targeted retry/resume fix with a regression proving that an interrupted first import does not permanently truncate older usage. Distinguish timeout, connection failure, 408/429/5xx from documented end-of-history responses; do not assume all 4xx mean no history. |
| High | Short-month DAILY date calculation. [current client source](https://github.com/jameslb/aiodukeenergy/blob/main/src/aiodukeenergy/dukeenergy.py) | Existing DAILY requests replace today's year/month before subtracting a day. On day 31, selecting February can raise ValueError before any request. The existing regression records this limitation. Investigate a valid date anchor or clamping against Duke's actual API semantics; do not silently change all daily requests to another fork's unverified date format. |
| High | Privacy-safe diagnostics and integration CI tests. [sam2kb tests and diagnostics](https://github.com/sam2kb/ha-dukeenergy/tree/97528fb848e4261e8132d5b8fc92eb794b9eb289) | Add tests for entity/statistic identity, redaction, reauthentication, reload, and multi-login removal. Check account IDs, addresses, tokens, URLs, and exception text before exposing diagnostics. Current integration workflows lint and validate but do not run its pytest suite. |
| Medium | Billing-cycle summaries and rollover correctness. [rollover fix](https://github.com/crash0verride11/ha-dukeenergy/commit/f316ba0b7979236d8b0ba3f97fde57e2d0d4b6d9) | Useful optional sensors. Preserve the completed cycle until new-cycle usage arrives and exclude the current incomplete day. Add empty-cycle, delayed-publication, and month-boundary cases before adoption. |
| Medium | Monthly usage via account/usage/comparison. [client 1.3.2](https://github.com/crash0verride11/aiodukeenergy/tree/8d00ba7ecf6fb092e87009003c768f83d4b2caff) | Potential source of billing summaries/longer history. This fixes that fork's newly added MONTHLY route; current jameslb only uses DAILY/HOURLY and does not need this endpoint for login repair. Validate electric and gas response shapes before extending the API. |
| Medium | Historical price-entity / time-of-use costs. [jojobird6](https://github.com/jojobird6/ha-dukeenergy/tree/422c8939c4cfe5cdfe902f1b4e01a62beadd780b), [related tariff integration](https://github.com/yzhu27/ha-dukeenergy-cost/tree/f8c16a37252fed8fde29146ba11c8e346923499e) | Deriving cost from stored consumption avoids extra Duke API calls. Retain jameslb's effective-date ledger and dirty-import confirmation; treat historical price coverage, gaps, DST, and tariff boundaries explicitly. Do not substitute today's price for historical periods. |
| Low | Billing/payment information, Safari helper, generic OAuth Assist provider. [crash0verride11 client](https://github.com/crash0verride11/aiodukeenergy/tree/8d00ba7ecf6fb092e87009003c768f83d4b2caff), [integration](https://github.com/crash0verride11/ha-dukeenergy/tree/d216021e81aa7c6748c9e410c9bb4696dc94d16e) | Optional expansion, larger maintenance/permission surface. Keep the focused manual callback repair for now. Billing information would be read-only; payment execution is outside scope. |

## Already present or unsuitable for wholesale adoption

- Gas support and service-specific units are already present. The 23brewert/flkns integration changes do not justify replacing the coordinator.
- Jameslb already retains statistics when unloading/reloading; it has no unload-time clear-statistics call. Review final removal across multiple logins separately before porting another fork's cleanup rules.
- Distributed daytime polling, retryable blocked/service errors, token expiry handling, and the effective-date cost ledger already exist.
- DallasEpperson's duplicate-hour work overlaps existing usage parsing. Keep DST/short-response regression coverage rather than importing an older client wholesale.
- chrisduk112's older combined client implements browser-form credential submission and lacks the current callback-state verification approach. It is behind the current authentication design and still calls account-list. Do not replace the current client with it.
- sam2kb's account normalization prefers uppercase BP fields when both spellings exist; PR 25 preserves the older spelling first. Keep PR 25 compatibility for this patch and investigate real conflicting-field evidence before changing precedence.
- crash0verride11 renamed its client package to aiodukeenergy-co. Import paths, dependency versioning, and behavior must be reviewed together; a blanket dependency swap would be a separate migration.
- Behind/identical default heads below have no unique commits relative to the checked upstream head; relevant fixes on PR branches were evaluated separately.

## Repository inventory

| Repository | Checked branch | Default-head comparison | Checked head |
| --- | --- | --- | --- |
| [babyhuey/aiodukeenergy](https://github.com/babyhuey/aiodukeenergy) | `main` | identical; +0/−0 | `ccddbe659cd5` |
| [flkns/aiodukeenergy](https://github.com/flkns/aiodukeenergy) | `main` | behind; +0/−8 | `8306a54dec71` |
| [Tmkauffman/aiodukeenergy](https://github.com/Tmkauffman/aiodukeenergy) | `main` | behind; +0/−16 | `d09a611d5792` |
| [b-v-co/aiodukeenergy](https://github.com/b-v-co/aiodukeenergy) | `main` | identical; +0/−0 | `ccddbe659cd5` |
| [jfthomps/aiodukeenergy](https://github.com/jfthomps/aiodukeenergy) | `main` | behind; +0/−16 | `d09a611d5792` |
| [Aujra/aiodukeenergy](https://github.com/Aujra/aiodukeenergy) | `main` | behind; +0/−10 | `60a96683c401` |
| [slammingprogramming/aiodukeenergy](https://github.com/slammingprogramming/aiodukeenergy) | `main` | behind; +0/−2 | `c9cf44e9b27a` |
| [DallasEpperson/aiodukeenergy](https://github.com/DallasEpperson/aiodukeenergy) | `main` | diverged; +1/−16 | `ff396456a8dc` |
| [jdobbsclt/aiodukeenergy](https://github.com/jdobbsclt/aiodukeenergy) | `main` | identical; +0/−0 | `ccddbe659cd5` |
| [mrala/aiodukeenergy](https://github.com/mrala/aiodukeenergy) | `main` | behind; +0/−16 | `d09a611d5792` |
| [chrisduk112/aiodukeenergy](https://github.com/chrisduk112/aiodukeenergy) | `main` | diverged; +4/−10 | `5227c629a6bc` |
| [crash0verride11/aiodukeenergy](https://github.com/crash0verride11/aiodukeenergy) | `aiodukeenergy-co` | diverged; +53/−2 | `8d00ba7ecf6f` |
| [sam2kb/ha-dukeenergy](https://github.com/sam2kb/ha-dukeenergy) | `main` | ahead; +94/−0 | `97528fb848e4` |
| [crash0verride11/ha-dukeenergy](https://github.com/crash0verride11/ha-dukeenergy) | `ha-dukeenergy-aio` | diverged; +90/−7 | `d216021e81aa` |
| [d4yz/dukeenergy_ha](https://github.com/d4yz/dukeenergy_ha) | `master` | Related repository; no shared comparison | `732fbcf848cf` |
| [yzhu27/ha-dukeenergy-cost](https://github.com/yzhu27/ha-dukeenergy-cost) | `main` | Related repository; no shared comparison | `f8c16a37252f` |
| [jdahmen/ha-dukeenergy](https://github.com/jdahmen/ha-dukeenergy) | `main` | behind; +0/−1 | `ede5e0fc09d6` |
| [23brewert/ha-dukeenergy](https://github.com/23brewert/ha-dukeenergy) | `main` | diverged; +1/−1 | `b8af13fb88eb` |
| [jojobird6/ha-dukeenergy](https://github.com/jojobird6/ha-dukeenergy) | `feat/cost-statistics` | diverged; +3/−1 | `422c8939c4cf` |
| [ndemarco/ha-dukeenergy](https://github.com/ndemarco/ha-dukeenergy) | `main` | behind; +0/−7 | `d24398d0cfd3` |
| [slammingprogramming/ha-dukeenergy](https://github.com/slammingprogramming/ha-dukeenergy) | `main` | behind; +0/−1 | `ede5e0fc09d6` |
| [babyhuey/ha-dukeenergy](https://github.com/babyhuey/ha-dukeenergy) | `main` | identical; +0/−0 | `3108a7193cb9` |
| [jdobbsclt/ha-dukeenergy](https://github.com/jdobbsclt/ha-dukeenergy) | `main` | identical; +0/−0 | `3108a7193cb9` |
| [flkns/ha-dukeenergy](https://github.com/flkns/ha-dukeenergy) | `main` | diverged; +3/−7 | `edc71fbca1ba` |

## Validation record

Client: 76 mocked Python tests and 10 synthetic capture-page tests passed; Ruff check/format passed. No live Duke calls were made. The test environment uses aiohttp 3.13.5 because aioresponses 0.7.9 does not mock aiohttp 3.14's changed ClientResponse constructor correctly.

Integration: guidance/translation JSON and manifest are validated separately, and Ruff 0.15.5 check/format passed. Full local HA tests could not be installed on Windows because HA 2025.12.5 pins lru-dict 1.3.0, which requires unavailable C++ build tools on Python 3.13. No production HA dependencies were changed to work around this limitation. No integration CI runs were reported for this branch; Linux validation remains outstanding.

Client CI also identified pre-existing test portability issues: Windows lacked tzdata, and Python 3.14 changed the text of the expected invalid-day exception. Added a Windows-only development dependency and made the exception assertion version-independent; this does not change DAILY request behavior. Corrected test typing and matched the repository's pinned formatting tools.

