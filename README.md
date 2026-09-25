# Duke Energy Custom Integration

A custom component to sync historical electric and gas usage for Duke Energy customers.

## Why?

In November 2025, Duke Energy migrated its API authentication to Auth0, which broke the existing core integration. This custom integration uses Duke Energy's browser login and a manual callback handoff while retaining OAuth PKCE and refresh-token authentication.

## Install

1. Add this repository to HACS and install the integration.
2. Restart Home Assistant.
3. Add Duke Energy from **Settings > Devices & services**. Existing entries will prompt for reauthentication when needed.
4. Select the Duke Energy login link shown by Home Assistant and sign in using a normal browser.
5. After a successful login, Duke Energy redirects to a 404 page. This is expected.
6. Copy the complete URL from that page's browser address bar and paste it into Home Assistant.

No Chrome extension is required. Home Assistant stores the resulting OAuth tokens and refreshes them automatically until Duke Energy invalidates the refresh token.

## Updates and diagnostics

Duke publishes historical usage on a delayed schedule. The integration polls around three daytime windows (9 AM, 2 PM, and 7 PM) with a stable per-installation offset of up to two hours. This spreads API traffic across installations while checking when new data is most likely to be available.

Each meter device also provides disabled-by-default diagnostic entities for:

- Last successful update
- Last newly received usage row
- Next scheduled update
- Current update status

Enable these entities from the meter device page when troubleshooting. Temporary Duke CDN blocks, rate limits, and service outages are retried without discarding valid credentials; genuine token rejection still starts reauthentication.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hunterjm&repository=ha-dukeenergy&category=integration)
