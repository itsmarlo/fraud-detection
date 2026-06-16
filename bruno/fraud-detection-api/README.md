# Bruno environments

Open this directory as a Bruno collection and select one of these environments:

- `local`: direct Uvicorn server at `http://localhost:8000`
- `btp`: deployed Cloud Foundry application route
- `ai-core`: SAP AI Core deployment management/inference calls

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

## AI Core Deployment Calls

Select the `ai-core` environment and set:

- `AICORE_BASE_URL`
- `AICORE_TOKEN_URL`
- `AICORE_CLIENT_ID`
- `AICORE_CLIENT_SECRET`
- `AICORE_RESOURCE_GROUP`
- `AICORE_SCENARIO_ID`
- `AICORE_EXECUTABLE_ID`
- `AICORE_CONFIGURATION_NAME`
- `AICORE_DEPLOYMENT_ID`

Request order:

1. `AI Core - Get Token`
2. `AI Core - List Scenarios`
3. `AI Core - List Executables`
4. `AI Core - Create Configuration`
5. `AI Core - Create Deployment`
6. `AI Core - Get Deployment`
7. `AI Core - Invoke Fraud Assessment`

`AI Core - Get Token` stores `AICORE_TOKEN` as a non-persistent environment
variable for the active Bruno session.

`AI Core - Create Configuration` stores `AICORE_CONFIGURATION_ID`, and
`AI Core - Create Deployment` stores `AICORE_DEPLOYMENT_ID`.
