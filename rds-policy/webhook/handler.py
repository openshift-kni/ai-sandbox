"""GitLab MR webhook handler for RDS Policy AgenticRun feedback loop.

Receives GitLab Note (comment) webhook events on merge requests and
patches the corresponding AgenticRun's revisionFeedback field to
trigger re-analysis by the operator.

Environment variables:
  GITLAB_WEBHOOK_SECRET  — shared secret for X-Gitlab-Token verification
  NAMESPACE              — Kubernetes namespace for AgenticRun lookup (default: openshift-lightspeed)
  KUBECONFIG             — optional, for out-of-cluster access
"""

import logging
import os

from fastapi import FastAPI, Header, HTTPException, Request
from kubernetes import client, config

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mr-webhook")

app = FastAPI(title="rds-mr-webhook")

WEBHOOK_SECRET = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
NAMESPACE = os.environ.get("NAMESPACE", "openshift-lightspeed")
MR_IID_ANNOTATION = "agentic.openshift.io/gitlab-mr-iid"
MR_PROJECT_ANNOTATION = "agentic.openshift.io/gitlab-project"

_k8s_initialized = False


def _init_k8s():
    global _k8s_initialized
    if _k8s_initialized:
        return
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    _k8s_initialized = True


def _find_agenticrun_by_mr(project_path: str, mr_iid: int) -> str | None:
    """Find an AgenticRun annotated with the given MR IID and project."""
    _init_k8s()
    api = client.CustomObjectsApi()
    runs = api.list_namespaced_custom_object(
        group="agentic.openshift.io",
        version="v1alpha1",
        namespace=NAMESPACE,
        plural="agenticruns",
    )
    iid_str = str(mr_iid)
    for run in runs.get("items", []):
        annotations = run.get("metadata", {}).get("annotations", {})
        if (
            annotations.get(MR_IID_ANNOTATION) == iid_str
            and annotations.get(MR_PROJECT_ANNOTATION) == project_path
        ):
            return run["metadata"]["name"]
    return None


def _patch_revision_feedback(run_name: str, feedback: str) -> None:
    """Patch spec.revisionFeedback on the named AgenticRun."""
    _init_k8s()
    api = client.CustomObjectsApi()
    api.patch_namespaced_custom_object(
        group="agentic.openshift.io",
        version="v1alpha1",
        namespace=NAMESPACE,
        plural="agenticruns",
        name=run_name,
        body={"spec": {"revisionFeedback": feedback}},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    x_gitlab_token: str | None = Header(None),
    x_gitlab_event: str | None = Header(None),
):
    if WEBHOOK_SECRET and x_gitlab_token != WEBHOOK_SECRET:
        logger.warning("Rejected: invalid X-Gitlab-Token")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    body = await request.json()
    object_kind = body.get("object_kind")

    if object_kind != "note":
        logger.info("Ignored event: object_kind=%s", object_kind)
        return {"status": "ignored", "reason": f"not a note event ({object_kind})"}

    attrs = body.get("object_attributes", {})
    noteable_type = attrs.get("noteable_type")
    if noteable_type != "MergeRequest":
        logger.info("Ignored note: noteable_type=%s", noteable_type)
        return {"status": "ignored", "reason": f"not an MR note ({noteable_type})"}

    if attrs.get("system", False):
        logger.info("Ignored system note")
        return {"status": "ignored", "reason": "system note"}

    note_body = attrs.get("note", "")
    note_author = body.get("user", {}).get("username", "unknown")
    note_url = attrs.get("url", "")

    mr = body.get("merge_request", {})
    mr_iid = mr.get("iid")
    project = body.get("project", {})
    project_path = project.get("path_with_namespace", "")

    if not mr_iid or not project_path:
        logger.warning("Missing MR IID or project path in payload")
        raise HTTPException(status_code=400, detail="Missing MR IID or project path")

    logger.info(
        "MR comment: project=%s iid=%s author=%s note=%.100s",
        project_path,
        mr_iid,
        note_author,
        note_body,
    )

    run_name = _find_agenticrun_by_mr(project_path, mr_iid)
    if not run_name:
        logger.info("No AgenticRun found for %s !%s", project_path, mr_iid)
        return {
            "status": "ignored",
            "reason": f"no AgenticRun annotated for {project_path} !{mr_iid}",
        }

    feedback = (
        f"## MR Review Comment\n"
        f"**Author:** {note_author}\n"
        f"**MR:** {project_path}!{mr_iid}\n"
        f"**URL:** {note_url}\n\n"
        f"{note_body}"
    )

    _patch_revision_feedback(run_name, feedback)
    logger.info("Patched revisionFeedback on AgenticRun/%s", run_name)

    return {
        "status": "patched",
        "agenticrun": run_name,
        "mr_iid": mr_iid,
        "author": note_author,
    }
