from pathlib import Path

INFRA = Path(__file__).resolve().parents[1] / "infra"


def _read(name: str) -> str:
    return (INFRA / name).read_text(encoding="utf-8")


def test_s3_eventbridge_notification_and_filter_are_configured():
    trigger = _read("trigger.tf")

    assert 'resource "aws_s3_bucket_notification" "raw_object_created"' in trigger
    assert "eventbridge = true" in trigger
    assert 'source        = ["aws.s3"]' in trigger
    assert '"Object Created"' in trigger
    assert 'suffix = ".osm.pbf"' in trigger
    # The trigger is gated on the s3_trigger_enabled variable.
    assert "var.s3_trigger_enabled" in trigger


def test_eventbridge_target_passes_batch_parameters_not_container_overrides():
    trigger = _read("trigger.tf")

    assert "input_transformer" in trigger
    assert "raw_key" in trigger
    assert 'input_template = "{\\"Parameters\\": {\\"raw_key\\": <raw_key>}}"' in trigger
    assert "$.detail.object.key" in trigger
    assert "batch:SubmitJob" in trigger
    assert "iam:PassRole" in trigger
    assert "events.amazonaws.com" in trigger
    assert "containerOverrides =" not in trigger
    # The trigger targets the revisionless ARN of the event job definition.
    assert 'aws_batch_job_definition.osm_job["event"].arn_prefix' in trigger
    assert 'aws_batch_job_definition.osm_job["manual"]' not in trigger


def test_eventbridge_submitjob_scope_is_limited_to_queue_and_event_definition():
    trigger = _read("trigger.tf")

    assert "aws_batch_job_queue.osm_queue.arn" in trigger
    assert 'aws_batch_job_definition.osm_job["event"].arn_prefix' in trigger
    assert '"${aws_batch_job_definition.osm_job["event"].arn_prefix}:*"' in trigger
    assert 'aws_batch_job_definition.osm_job["event"].arn,' not in trigger


def test_batch_job_definitions_split_manual_and_event_roles():
    batch = _read("batch.tf")
    locals_tf = _read("locals.tf")

    assert "for_each = local.job_definitions" in batch
    assert "manual = {" in locals_tf
    assert "event = {" in locals_tf
    assert "moved {" in batch
    assert "from = aws_batch_job_definition.osm_job" in batch
    assert 'to   = aws_batch_job_definition.osm_job["manual"]' in batch
    # Both definitions expose the raw_key parameter expanded by the command.
    assert "parameters = {" in batch
    assert 'raw_key = ""' in batch
    assert '"Ref::raw_key"' in locals_tf
    assert "{{Ref::raw_key}}" not in locals_tf


def test_region_is_derived_from_key_instead_of_baked_environment():
    locals_tf = _read("locals.tf")

    assert '{ name = "REGION_NAME"' not in locals_tf
    assert '{ name = "RUN_ID"' not in locals_tf
    assert "region=<name>" in locals_tf


def test_trigger_defaults_and_example_configuration():
    variables = _read("variables.tf")
    example = _read("terraform.tfvars.example")

    assert 'variable "s3_trigger_enabled"' in variables
    assert 'variable "trigger_overwrite"' not in variables
    assert "s3_trigger_enabled = true" in example


def test_trigger_is_exposed_in_outputs():
    outputs = _read("outputs.tf")

    assert "eventbridge_rule_name" in outputs
    assert "s3_trigger_enabled" in outputs
    assert "aws_region" in outputs
    assert 'aws_batch_job_definition.osm_job["manual"].name' in outputs
    assert 'aws_batch_job_definition.osm_job["event"].name' in outputs
