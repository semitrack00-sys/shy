# Check the current SHY runtime on Windows without replacing the installed runtime

The current release is v0.105.1. The historical temporary names below are labels,
not version checks; the HTTP verifier checks the running version.

Run these commands in PowerShell with Docker Desktop running Linux containers.
This creates a separate checkout and temporary database. It does not change the
branch or uncommitted files in `C:\SHY`, stop the installed SHY container, or use
its database. Choose another checkout path if `C:\SHY-v100` already exists.

## 1. Fetch and stage the reviewed release

```powershell
Set-Location C:\SHY
git status --short
git fetch origin main
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed' }
git worktree add --detach C:\SHY-v100 origin/main
if ($LASTEXITCODE -ne 0) { throw 'Worktree staging failed' }
Set-Location C:\SHY-v100
git rev-parse HEAD
docker build -t shy-core:v100-check .
if ($LASTEXITCODE -ne 0) { throw 'Image build failed' }
```

Select `main` explicitly: the repository's historical default branch does not
contain this release. Review the printed commit and its successful GitHub release
gate before proceeding. Git fetch updates remote references, not your local files.

## 2. Start an isolated candidate

The names below are reserved for this temporary check. If any already exists,
choose new names throughout rather than removing an unknown container/network.
The password is for the disposable test database only, never your installed SHY.

```powershell
docker network create shy-v100-check
if ($LASTEXITCODE -ne 0) { throw 'Network creation failed' }
docker run -d --name shy-v100-check-db --network shy-v100-check -e POSTGRES_DB=shy_check -e POSTGRES_USER=shy_check -e POSTGRES_PASSWORD=local-validation-only postgres:16
if ($LASTEXITCODE -ne 0) { throw 'Test database start failed' }
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    docker exec shy-v100-check-db pg_isready -U shy_check -d shy_check
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) { throw 'Test database did not become ready' }
docker run -d --name shy-v100-check-core --network shy-v100-check -p 127.0.0.1:18000:8000 -e DATABASE_URL=postgresql://shy_check:local-validation-only@shy-v100-check-db:5432/shy_check -e OLLAMA_URL=http://host.docker.internal:11434 -e SHY_LOCAL_MODEL=qwen3.5:4b shy-core:v100-check
if ($LASTEXITCODE -ne 0) { throw 'Candidate start failed' }
python scripts/verify_local_release.py --url http://127.0.0.1:18000 --wait-seconds 90 --require-model
if ($LASTEXITCODE -ne 0) { throw 'Candidate verification failed; inspect candidate health and logs' }
```

The verifier checks the running version, database connection, platform invariants,
the exact 50-capability catalog, all 50 supplied-data examples, batching, and HTTP
404/422/413 error boundaries. `--require-model` also checks that Ollama lists the
configured model. It does not send a chat request or benchmark GPU inference.
Omit `--require-model` to check packaging and utilities while Ollama is offline;
the report will still state that model availability is false.

For a failure, inspect the candidate only:

```powershell
docker logs --tail 100 shy-v100-check-core
Invoke-RestMethod http://127.0.0.1:18000/health
```

## 3. Remove only the temporary check

```powershell
docker rm -f -v shy-v100-check-core shy-v100-check-db
docker network rm shy-v100-check
```

`-v` removes the temporary PostgreSQL container's anonymous data volume. No
installed SHY volumes are attached here. Keep the staged checkout and image for
review. Replacing the installed runtime is a separate step: preserve its container
configuration, image ID, database backup, environment, and mounted volumes first.
Starting a new runtime against the installed database can initialize or migrate
tables, so this isolated check is not a database migration or rollback rehearsal.
