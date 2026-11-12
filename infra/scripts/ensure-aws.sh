#!/usr/bin/env bash
# Verify the DocuSpace RDS instance and EC2 server exist, start them when they
# are stopped, and print the public IP. AWS does not store the EC2 private key;
# the workflow still uses the GitHub secret EC2_SSH_KEY.
set -euo pipefail

: "${AWS_REGION:?AWS_REGION is required}"
: "${DB_INSTANCE_IDENTIFIER:?DB_INSTANCE_IDENTIFIER is required}"
: "${EC2_NAME_TAG:?EC2_NAME_TAG is required}"

echo "Region: ${AWS_REGION}"

if ! rds_status="$(aws rds describe-db-instances \
  --region "${AWS_REGION}" \
  --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text 2> /tmp/rds-describe.err)"; then
  echo "RDS instance ${DB_INSTANCE_IDENTIFIER} is not defined."
  cat /tmp/rds-describe.err
  exit 1
fi

echo "RDS ${DB_INSTANCE_IDENTIFIER} status: ${rds_status}"

case "${rds_status}" in
  available)
    ;;
  stopped)
    echo "Starting RDS ${DB_INSTANCE_IDENTIFIER}."
    aws rds start-db-instance \
      --region "${AWS_REGION}" \
      --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
      --query 'DBInstance.DBInstanceStatus' \
      --output text
    aws rds wait db-instance-available \
      --region "${AWS_REGION}" \
      --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}"
    ;;
  starting | backing-up | configuring | modifying | rebooting)
    echo "Waiting until RDS ${DB_INSTANCE_IDENTIFIER} is available."
    aws rds wait db-instance-available \
      --region "${AWS_REGION}" \
      --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}"
    ;;
  *)
    echo "RDS ${DB_INSTANCE_IDENTIFIER} is defined but cannot be used. Status: ${rds_status}"
    exit 1
    ;;
esac

rds_status="$(aws rds describe-db-instances \
  --region "${AWS_REGION}" \
  --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text)"
rds_endpoint="$(aws rds describe-db-instances \
  --region "${AWS_REGION}" \
  --db-instance-identifier "${DB_INSTANCE_IDENTIFIER}" \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)"
echo "RDS ${DB_INSTANCE_IDENTIFIER} is ${rds_status} at ${rds_endpoint}"

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
echo "EC2 ${instance_id} status: ${instance_state}"

if [[ "${instance_state}" == "stopping" ]]; then
  aws ec2 wait instance-stopped --region "${AWS_REGION}" --instance-ids "${instance_id}"
  instance_state="stopped"
fi

if [[ "${instance_state}" == "stopped" ]]; then
  echo "Starting EC2 ${instance_id}."
  aws ec2 start-instances \
    --region "${AWS_REGION}" \
    --instance-ids "${instance_id}" \
    --query 'StartingInstances[0].CurrentState.Name' \
    --output text
  instance_state="pending"
fi

if [[ "${instance_state}" == "pending" ]]; then
  aws ec2 wait instance-running --region "${AWS_REGION}" --instance-ids "${instance_id}"
fi

echo "Waiting until EC2 ${instance_id} passes status checks."
aws ec2 wait instance-status-ok --region "${AWS_REGION}" --instance-ids "${instance_id}"

read -r public_ip key_name instance_state <<< "$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --instance-ids "${instance_id}" \
  --query 'Reservations[0].Instances[0].[PublicIpAddress,KeyName,State.Name]' \
  --output text)"

if [[ -z "${public_ip}" || "${public_ip}" == "None" ]]; then
  echo "EC2 ${instance_id} is ${instance_state} but has no public IP."
  exit 1
fi

echo "EC2 ${instance_id} is ${instance_state}."
echo "EC2 public IP: ${public_ip}"
echo "EC2 key pair name: ${key_name}"
echo "AWS does not return the private key. SSH uses the EC2_SSH_KEY GitHub secret."

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "public_ip=${public_ip}"
    echo "key_name=${key_name}"
    echo "instance_id=${instance_id}"
  } >> "${GITHUB_OUTPUT}"
fi
