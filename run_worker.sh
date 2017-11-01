#!/bin/bash

export AWS_KEY_NAME=PROMPT
export AWS_KEY=PROMPT

export CLOUDSHELL_URL=https://demo.quali.com:3443
export CLOUDSHELL_DOMAIN=Quali Product
export CLOUDSHELL_USER=PROMPT
export CLOUDSHELL_PASSWORD=PROMPT

export AWS_REGION=us-west-2
export JOB_WORKER_VERSION=9
export RUN_COMMAND_ACTION_NAME=Quali-Run-Command
export START_SANDBOX_ACTION_NAME=Quali-Start-Sandbox
export END_SANDBOX_ACTION_NAME=Quali-End-Sandbox

pip install boto3
pip install requests

python quali_job_worker.py
