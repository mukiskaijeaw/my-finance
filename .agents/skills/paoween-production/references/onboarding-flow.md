# First-run onboarding flow

The root `index.html` routes a fresh browser to `/settings/new-user/`. After the user presses the dashboard action, `app.js` stores a completion flag in localStorage and routes to `/dashboard.html`. A later visit to `/` opens the dashboard. Add `?force=1` to the onboarding URL to rerun it.

The onboarding asks for monthly take-home salary and optionally lets the user choose a slip image. Salary and a boolean pass through same-tab `sessionStorage`; `dashboard-handoff.js` consumes and clears that payload. A selected JPG/PNG is staged locally in IndexedDB, then moved into the dashboard’s normal attachment tray and deleted from IndexedDB. It is still not sent for analysis until the user presses Send, and no transaction is saved without a separate review and confirmation. Never describe it as processed or saved before that happens.

The Three.js loader is served from `/assets/vendor/`; onboarding and dashboard GLBs are in `/assets/paoween/`. Preserve the absolute paths so the nested onboarding route can load the same local assets.
