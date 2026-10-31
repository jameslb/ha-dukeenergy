# Duke Energy Custom Integration

A custom component to sync historical electric and gas usage for Duke Energy customers.

## Why?

In November 2025, Duke Energy migrated its API authentication to Auth0, which broke the existing core integration. This custom integration uses Duke Energy's browser login and a manual callback handoff while retaining OAuth PKCE and refresh-token authentication.

## Install

1. Add this repository to HACS and install the integration.
2. Restart Home Assistant.
3. Add Duke Energy from **Settings > Devices & services**. Existing entries will prompt for reauthentication when needed.
4. Select the Duke Energy login link shown by Home Assistant and sign in.
5. After a successful login, Duke Energy redirects to its mobile callback URL. A 404 page can appear; success requires `code` and `state` in the URL.
6. Copy the complete callback URL from the browser address bar and paste it into Home Assistant. If using the [OAuth helper](https://github.com/jameslb/aiodukeenergy/tree/main/chrome-extension), select **Copy complete callback URL**, rather than the code-only button.

Some desktop browser logins now return `error=access_denied` even when the normal Duke website or app works. This is a rejected authorization, not the expected callback. The optional OAuth helper includes the workaround reported in [upstream PR 23](https://github.com/hunterjm/aiodukeenergy/pull/23): sending an iOS Safari User-Agent only to Duke's login domain. Review its permissions and instructions before installing it. Start a fresh Home Assistant sign-in after enabling the helper; an error URL cannot be exchanged for tokens.

Keep callback URLs private and use them promptly in the same Home Assistant setup flow. State, nonce, PKCE, and token-signature validation remain enabled. Home Assistant stores the resulting OAuth tokens and refreshes them automatically until Duke Energy invalidates the refresh token.

See the [fork review](docs/fork-review-2026-10-30.md) for adopted fixes and proposed follow-ups.

## Updates and diagnostics

Duke publishes historical usage on a delayed schedule. The integration polls around three daytime windows (9 AM, 2 PM, and 7 PM) with a stable per-installation offset of up to two hours. This spreads API traffic across installations while checking when new data is most likely to be available.

Each meter device also provides disabled-by-default diagnostic entities for:

- Last successful update
- Last newly received usage row
- Next scheduled update
- Current update status

Enable these entities from the meter device page when troubleshooting. Temporary Duke CDN blocks, rate limits, and service outages are retried without discarding valid credentials; genuine token rejection still starts reauthentication.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jameslb&repository=ha-dukeenergy&category=integration)
