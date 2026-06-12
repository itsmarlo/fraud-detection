# Bruno environments

Open this directory as a Bruno collection and select one of these environments:

- `local`: direct Uvicorn server at `http://localhost:8000`
- `btp`: deployed Cloud Foundry application route

Before using either environment, edit these variables in Bruno:

- `DAMAGE_PHOTO_PATH`: absolute path to a JPEG, PNG, or WebP file
- `BASE_URL`: required for `btp`; use the route shown by `cf app`
- `CLAIM_ID`: optional claim identifier shared by collection requests

Recommended request order:

1. `Health`
2. `Score Claim`
3. `Upload Files`
4. `Analyze File`
5. `Predict With Files`
6. `List Files`

`Upload Files` automatically stores the returned file ID in the active
environment as `FILE_ID`, so `Analyze File` can run immediately afterward.

The API currently has no application authentication. Do not store SAP AI Core
credentials, OpenAI keys, Cloud Foundry passwords, or service keys in Bruno.
Those are server-side deployment settings and are not required by these API
requests.
