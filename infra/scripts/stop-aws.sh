#!/usr/bin/env bash
# Stop the DocuSpace EC2 server and RDS instance, then print their status.
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${DB_INSTANCE_IDENTIFIER:?DB_INSTANCE_IDENTIFIER is required}"
: "${EC2_NAME_TAG:?EC2_NAME_TAG is required}"

echo "Region: ${AWS_REGION}"

instance_ids="$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --filters "Name=tag:Name,Values=${EC2_NAME_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
  --query 'Reservations[].Instances[].InstanceId' \
  --output text)"

if [[ -z "${instance_ids}" || "${instance_ids}" == "None" ]]; then
  echo "EC2 instance with tag Name=${EC2_NAME_TAG} is not defined."
  exit 1
fi

read -r -a instance_id_list <<< "${instance_ids}"
if [[ "${#instance_id_list[@]}" -ne 1 ]]; then
  echo "Expected one EC2 instance named ${EC2_NAME_TAG}, found: ${instance_ids}"
  exit 1
fi

instance_id="${instance_id_list[0]}"
instance_state="$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --instance-ids "${instance_id}" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text)"
echo "EC2 ${instance_id} status before stop: ${instance_state}"

if [[ "${instance_state}" == "pending" ]]; then
  aws ec2 wait instance-running --region "${AWS_REGION}" --instance-ids "${instance_id}"
  instance_state="running"
fi

if [[ "${instance_state}" == "running" ]]; then
  echo "Stopping EC2 ${instance_id}."
  aws ec2 stop-instances \
    --region "${AWS_REGION}" \
    --instance-ids "${instance_id}" \
    --query 'StoppingInstances[0].CurrentState.Name' \
    --output text
fi

if [[ "${instance_state}" != "stopped" ]]; then
  aws ec2 wait instance-stopped --region "${AWS_REGION}" --instance-ids "${instance_id}"
fi

instance_state="$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --instance-ids "${instance_id}" \
  --query 'Reservations[0].Instances[0].State.Name' \
  --output text)"

if ! rds_status="$(aws rds describe-db-instances \
  --region "${AWS_REGION}" \
  --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text 2> /tmp/rds-describe.err)"; then
  echo "RDS instance ${DB_INSTANCE_IDENTIFIER} is not defined."
  cat /tmp/rds-describe.err
  exit 1
fi

echo "RDS ${DB_INSTANCE_IDENTIFIER} status before stop: ${rds_status}"

case "${rds_status}" in
  stopped)
    ;;
  available)
    echo "Stopping RDS ${DB_INSTANCE_IDENTIFIER}."
    aws rds stop-db-instance \
      --region "${AWS_REGION}" \
      --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
      --query 'DBInstance.DBInstanceStatus' \
      --output text
    ;;
  stopping)
    ;;
  *)
    echo "RDS ${DB_INSTANCE_IDENTIFIER} cannot be stopped from status ${rds_status}."
    echo "EC2 ${instance_id} status: ${instance_state}"
    exit 1
    ;;
esac

if [[ "${rds_status}" != "stopped" ]]; then
  echo "Waiting until RDS ${DB_INSTANCE_IDENTIFIER} is stopped."
  for _ in $(seq 1 40); do
    rds_status="$(aws rds describe-db-instances \
      --region "${AWS_REGION}" \
      --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
      --query 'DBInstances[0].DBInstanceStatus' \
      --output text)"
    echo "RDS ${DB_INSTANCE_IDENTIFIER} status: ${rds_status}"
    if [[ "${rds_status}" == "stopped" ]]; then
      break
    fi
    sleep 15
  done
fi

echo "Stop report"
echo "EC2 ${instance_id}: ${instance_state}"
echo "RDS ${DB_INSTANCE_IDENTIFIER}: ${rds_status}"

if [[ "${instance_state}" != "stopped" || "${rds_status}" != "stopped" ]]; then
  echo "Resources did not reach stopped."
  exit 1
fi

echo "EC2 and RDS are stopped."
