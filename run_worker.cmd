set AWS_KEY_NAME=PROMPT
set AWS_KEY=PROMPT

set CLOUDSHELL_URL=https://demo.quali.com:3443
set CLOUDSHELL_DOMAIN=Quali Product
set CLOUDSHELL_USER=PROMPT
set CLOUDSHELL_PASSWORD=PROMPT

set AWS_REGION=us-west-2
set JOB_WORKER_VERSION=9
set RUN_COMMAND_ACTION_NAME=Quali-Run-Command
set START_SANDBOX_ACTION_NAME=Quali-Start-Sandbox
set END_SANDBOX_ACTION_NAME=Quali-End-Sandbox

pip install boto3
pip install requests

python quali_job_worker.py
