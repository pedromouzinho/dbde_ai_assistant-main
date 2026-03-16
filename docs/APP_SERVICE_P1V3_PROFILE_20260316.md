# App Service P1v3 Production Profile

State applied in Azure on 2026-03-16 for `millennium-ai-assistant`:

- Reproducible Azure CLI script: `scripts/apply_p1v3_safe_profile.sh`

- Main web app startup command: `bash /home/site/wwwroot/startup.sh`
- Main web app:
  - `STARTUP_FAIL_FAST=false`
  - `DEVOPS_INDEX=millennium-story-devops-index`
  - `OMNI_INDEX=millennium-story-knowledge-index`
  - `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED=true`
- App Service autoscale profile (`plan-dbde-v2-autoscale`):
  - minimum `2`
  - default `2`
  - maximum `3`
- Dedicated worker app in the same plan:
  - app name: `millennium-ai-assistant-worker`
  - startup command: `bash /home/site/wwwroot/startup_worker.sh`
  - `WORKER_MODE=both`
  - `STARTUP_FAIL_FAST=false`
  - `UPLOAD_INLINE_WORKER_RUNTIME_ENABLED=false`
  - current operational state: `Stopped` until dedicated-worker cutover is validated end to end

Rationale:

- Keep two warm instances to reduce cold-start and restart blast radius.
- Point production to the populated story indexes instead of relying on runtime fallback.
- Avoid full app unavailability when a startup dependency is transiently unhealthy.
- Prepare a clean worker-app split without risking a regression in live async upload/export flows.
