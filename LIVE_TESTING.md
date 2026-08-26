# Live Testing Guide

This guide tests the memory module against a real Pinecone index from Windows
PowerShell. It uses a dedicated user id so the test data is easy to find and
remove.

## 1. Protect the API key

The example file is only a template. If a real key was ever committed or
shared, revoke it in the Pinecone console and create a replacement before
testing.

Copy the template and fill in the key locally:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set these values in `.env`:

```text
PINECONE_API_KEY=pcsk_your_real_key_here
PINECONE_INDEX_NAME=agent-memory-live-test
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
MEMORY_DATA_DIR=Memory_module/data/long_term_memory
```

Do not put quotes around the key, commit `.env`, or paste the key into source
code. `.gitignore` already excludes `.env` and local memory data.

## 2. Install and check the environment

From the repository root, create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r Memory_module/requirements.txt
```

This installs `typing-extensions`, which is required by the Pinecone SDK even
though it is not part of the demo code.

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Confirm that the key is present without printing it:

```powershell
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Pinecone key loaded:', bool(os.getenv('PINECONE_API_KEY')))"
```

The result must be `Pinecone key loaded: True`.

## 3. Run the end-to-end demo

```powershell
python -m Memory_module.demo
```

On the first run, Pinecone creates the index and may take about a minute. A
successful run shows:

```text
[health]  {'index': 'agent-memory-live-test', 'backend': 'pinecone', ...}
[process_user_input]
{'triage_topic': 'name', 'saved_notes': [...]}
[get_user_profile]
  - food: ...
  - work: ...
  - name: ...
[build_agent_prompt]
{'history': [...], 'long_term_context': '...', 'user_profile': '...'}
```

The demo uses `demo_user` and `demo_session`. It also clears that demo user's
data when it finishes, so the Pinecone namespace should be empty afterward.

## 4. Run a persistent live check

The following command keeps its data until you explicitly delete it. It checks
the Pinecone backend, writes a note, reads the local mirror, and retrieves the
note through Pinecone:

```powershell
python -c "from Memory_module import MemoryManager; m=MemoryManager(); u='live_test_user'; print(m.health_check()); note=m.save_user_preference(u, 'food', 'Prefers spicy vegetarian food'); print('saved:', note); print('profile:', m.get_user_profile(u)); print('retrieved:', m.retrieve_context(u, 'What food does the user prefer?'))"
```

Verify that `backend` is `pinecone`, `profile` contains the saved note, and
`retrieved` contains `spicy vegetarian food`.

## 5. Clean up

After the persistent check, remove its Pinecone namespace and local JSON file:

```powershell
python -c "from Memory_module import MemoryManager; m=MemoryManager(); m.delete_user_memory('live_test_user'); print('live test data deleted')"
```

For a full reset, delete the test index from the Pinecone console. Do not
delete a shared production index.

## Troubleshooting

- `PINECONE_API_KEY environment variable is missing`: confirm `.env` is in the
  repository root and the key-loaded check returns `True`.
- `401` or `403`: revoke the exposed key if applicable and create a new key
  with access to the project containing the index.
- Index creation errors: check the cloud and region, and choose a new index
  name if `agent-memory-live-test` already exists with incompatible settings.
- `Vector dimension 1536 does not match the dimension of the index 1024`:
  update the code, then rerun. The module now reads an existing index's
  dimension automatically. For a fresh test, use a new index name so Pinecone
  creates it with the configured dimension.
- `backend: local`: the key was not loaded, so the test did not contact
  Pinecone. Stop and fix configuration before treating the test as live.
- Local-only regression check: `python -m unittest discover -s tests -v`.