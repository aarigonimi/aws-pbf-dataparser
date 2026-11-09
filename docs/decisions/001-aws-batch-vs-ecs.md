# ADR 001: Use AWS Batch for regional PBF runs

## Decision

Use AWS Batch to queue and execute containerized regional imports. The job
definition declares compute, timeout, retry rules, IAM roles and logging.

## Context

The verified Quebec parse took 5,530.778 seconds, with Batch runtime about
5,922.575 seconds. These are long-running batch workloads with variable input
sizes and explicit resource needs.

## Trade-offs

Lambda is a poor fit for a single uninterrupted parse of this duration and for
the large local scratch requirement. ECS `RunTask` could run the container, but
would require additional orchestration for queueing, retries and job status.
Batch supplies those batch-oriented controls. This project has not benchmarked
the same workload on Lambda or ECS `RunTask`; this decision is based on fit,
not a comparative performance or cost test.
