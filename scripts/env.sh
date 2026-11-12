#!/usr/bin/env bash
# Source shared stack outputs into environment variables

_ENV_SH_SELF="${BASH_SOURCE:-$0}"
_ENV_SH_PROJECT_ROOT="$(cd "$(dirname "${_ENV_SH_SELF}")/.." && pwd)"
_ENV_SH_TF_DIR="${_ENV_SH_PROJECT_ROOT}/infra"

_env_sh_fail() {
  echo "scripts/env.sh: $*" >&2
  unset _ENV_SH_SELF _ENV_SH_PROJECT_ROOT _ENV_SH_TF_DIR
  return 1 2>/dev/null || exit 1
}

_env_sh_load() {
  # _env_sh_load <variable-name> <terraform-output-name>
  local __value
  __value="$(terraform -chdir="${_ENV_SH_TF_DIR}" output -raw "$2" 2>/dev/null)"
  if [[ -z "${__value}" || "${__value}" == "null" ]]; then
    _env_sh_fail "Terraform output '$2' is unavailable. Is the stack deployed? Run 'make deploy' first."
  fi
  eval "$1=\$__value"
}

command -v terraform >/dev/null 2>&1 ||
  _env_sh_fail "terraform CLI not found on PATH. Install Terraform 1.x first."

_env_sh_load AWS_REGION aws_region
_env_sh_load RAW_BUCKET raw_bucket_name
_env_sh_load OUTPUT_BUCKET curated_bucket_name
_env_sh_load CURATED_PREFIX_URI curated_prefix_uri
_env_sh_load JOB_QUEUE batch_job_queue_name
_env_sh_load JOB_DEFINITION batch_job_definition_name
_env_sh_load EVENT_JOB_DEFINITION batch_event_job_definition_name
_env_sh_load CLOUDWATCH_LOG_GROUP_NAME cloudwatch_log_group_name
_env_sh_load ATHENA_WORKGROUP athena_workgroup_name
_env_sh_load GLUE_DATABASE glue_database_name
_env_sh_load GLUE_TABLE glue_table_name
_env_sh_load ECR_REPOSITORY_URL ecr_repository_url
_env_sh_load S3_TRIGGER_ENABLED s3_trigger_enabled

# Null when the S3 trigger is disabled (s3_trigger_enabled = false).
EVENTBRIDGE_RULE_NAME="$(terraform -chdir="${_ENV_SH_TF_DIR}" output -raw eventbridge_rule_name 2>/dev/null || true)"
[[ "${EVENTBRIDGE_RULE_NAME}" == "null" ]] && EVENTBRIDGE_RULE_NAME=""

export AWS_REGION RAW_BUCKET OUTPUT_BUCKET CURATED_PREFIX_URI JOB_QUEUE \
  JOB_DEFINITION EVENT_JOB_DEFINITION EVENTBRIDGE_RULE_NAME \
  S3_TRIGGER_ENABLED CLOUDWATCH_LOG_GROUP_NAME ATHENA_WORKGROUP \
  GLUE_DATABASE GLUE_TABLE ECR_REPOSITORY_URL

unset _ENV_SH_SELF _ENV_SH_PROJECT_ROOT _ENV_SH_TF_DIR
