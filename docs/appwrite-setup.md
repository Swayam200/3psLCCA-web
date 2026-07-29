# Appwrite Setup Guide

3psLCCA-web uses [Appwrite](https://appwrite.io) for two things:

1. **Authentication** — email/password login and Google OAuth.
2. **Cloud project sync** — signed-in users' projects are stored in an
   Appwrite database and synced across devices (offline-first: the browser's
   localStorage is always the primary copy, Appwrite syncs in the background).

Appwrite is **optional**. Without it the app runs in guest mode: login is
disabled and projects live only in the browser. Configure Appwrite when you
want real accounts and cross-device sync.

---

## 1. Create the project

1. Sign in at [cloud.appwrite.io](https://cloud.appwrite.io) (or your
   self-hosted console).
2. **Create project** — any name (e.g. `3psLCCA_Web`). Pick the region closest
   to your users and note it: the region determines your API endpoint
   (e.g. Frankfurt → `https://fra.cloud.appwrite.io/v1`).
3. From **Settings → API credentials**, copy:
   - **Project ID** → `VITE_APPWRITE_PROJECT_ID`
   - **API Endpoint** → `VITE_APPWRITE_ENDPOINT`

## 2. Register Web platforms (required — do not skip)

Appwrite rejects browser requests from unregistered origins. Register one Web
platform per hostname the app is served from.

1. Go to the project **Overview** page → scroll to **Integrations →
   Platforms** → **Add platform** → **Web**.
2. Add a platform for local development:
   - Name: `Local dev`
   - Hostname: `localhost`
3. Add another platform for every deployed hostname, e.g.:
   - Name: `Production`
   - Hostname: `app.example.com` (or `<user>.github.io` for GitHub Pages)

**Hostname rules** — the value must be a bare hostname:

| ✅ Correct | ❌ Wrong |
| --- | --- |
| `localhost` | `http://localhost:5173` |
| `myuser.github.io` | `https://myuser.github.io` |
| `app.example.com` | `myuser.github.io/3psLCCA-web` (no paths) |

> The platform wizard may offer a "clone starter kit" tutorial after you enter
> the hostname — skip it ("Skip, go to dashboard"). The platform is registered
> as soon as it appears in the Platforms list.

## 3. Enable authentication methods

Under **Auth → Settings**:

1. **Email/Password** — enable.
2. **Google OAuth** (optional):
   1. Enable the **Google** provider. Appwrite shows a redirect/callback URI —
      copy it.
   2. In [Google Cloud Console](https://console.cloud.google.com) create an
      **OAuth 2.0 Client ID** (type: Web application) and add the Appwrite
      callback URI to *Authorized redirect URIs*.
   3. Paste the Google client ID and secret back into the Appwrite provider
      form and save.

## 4. Create the database and collection

Under **Databases**:

1. **Create database** — any name (e.g. `lcca`). Copy its ID →
   `VITE_APPWRITE_DATABASE_ID`.
2. Inside it, **create collection** (e.g. `project_data`). Copy its ID →
   `VITE_APPWRITE_COLLECTION_ID`.
3. Add these attributes (the exact names matter — the app reads/writes them in
   `src/lib/projectStorageService.js`):

   | Attribute | Type | Size | Required |
   | --- | --- | --- | --- |
   | `name` | String | 256 | yes |
   | `data` | String | 1000000 | yes |
   | `userId` | String | 64 | yes |

   `data` holds the entire project as a JSON string, so give it a generous
   size limit.
4. Add an **index** on `userId` (key index) — the app filters project lists
   with `Query.equal('userId', …)`.
5. Set collection **permissions** so authenticated users can manage their own
   documents: grant **create, read, update, delete** to role **Users**.
   (Documents are always filtered by `userId` in queries; enable document
   security if you want per-document ACLs on top.)

## 5. Configure the app

Copy `.env.example` to `.env` and fill in the four values:

```bash
VITE_APPWRITE_ENDPOINT=https://fra.cloud.appwrite.io/v1
VITE_APPWRITE_PROJECT_ID=<project id>
VITE_APPWRITE_DATABASE_ID=<database id>
VITE_APPWRITE_COLLECTION_ID=<collection id>
```

Restart `npm run dev` (Vite only reads `.env` at startup). For production,
the same four variables must be present **at build time** — they are baked
into the bundle. These are public client-side identifiers, not secrets;
access control comes from the platform allow-list and collection permissions.

## 6. Verify

1. `npm run dev`, open the app → the login page should appear.
2. Sign up with email/password → you should land on the home page.
3. Create a project, then check the Appwrite console → Databases → your
   collection: a document should exist with your project's `name`, `data`,
   and `userId`.
4. If Google OAuth is configured, log out and try **Continue with Google**.

## Troubleshooting

**`Error 400 — Invalid 'success' param: Invalid URI. Register your new client
(<hostname>) as a new Web platform`**
The origin you are browsing from is not registered. Repeat step 2 for that
hostname — and double-check the hostname has no protocol, port, path, or
trailing slash. Also confirm you added it to the **right project** (compare
the Project ID in the console URL with `VITE_APPWRITE_PROJECT_ID`).

**Login/network errors mentioning CORS**
Same cause as above — register the origin's hostname as a Web platform.

**Google OAuth redirects to a 404 after sign-in**
The success URL is derived from the app's base path. If you host the app
under a subdirectory, make sure the build used the correct `VITE_BASE_PATH`.

**App works but nothing syncs (projects only local)**
You are in guest mode. Log in with a real account; also confirm all four
`VITE_APPWRITE_*` values were present when the app was built/started.

**`Collection with the requested ID could not be found`**
`VITE_APPWRITE_DATABASE_ID` / `VITE_APPWRITE_COLLECTION_ID` don't match the
console, or the collection lacks the attributes from step 4.
