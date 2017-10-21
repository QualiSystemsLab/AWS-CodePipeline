from getpass import getpass
import json
import re
from StringIO import StringIO
from threading import Lock, Thread
from time import sleep
import boto3
import requests
import os

CLOUDSHELL_URL = os.environ['CLOUDSHELL_URL']
CLOUDSHELL_USER = os.environ['CLOUDSHELL_USER']
CLOUDSHELL_PASSWORD = os.environ['CLOUDSHELL_PASSWORD']
CLOUDSHELL_DOMAIN = os.environ['CLOUDSHELL_DOMAIN']

AWS_KEY_NAME = os.environ['AWS_KEY_NAME']
AWS_KEY = os.environ['AWS_KEY']

AWS_REGION = os.environ['AWS_REGION']
AWS_OUTPUT_FORMAT = 'json'

JOB_WORKER_OWNER = 'Custom'
JOB_WORKER_START_SANDBOX_PROVIDER = os.environ['START_SANDBOX_ACTION_NAME']
JOB_WORKER_END_SANDBOX_PROVIDER = os.environ['END_SANDBOX_ACTION_NAME']
JOB_WORKER_RUN_COMMAND_PROVIDER = os.environ['RUN_COMMAND_ACTION_NAME']
JOB_WORKER_VERSION = os.environ['JOB_WORKER_VERSION']


if CLOUDSHELL_USER == 'PROMPT':
    CLOUDSHELL_USER = raw_input('Enter CloudShell user:')

if CLOUDSHELL_PASSWORD == 'PROMPT':
    CLOUDSHELL_PASSWORD = getpass('Enter password for CloudShell user %s:' % CLOUDSHELL_USER)

if AWS_KEY_NAME == 'PROMPT':
    AWS_KEY_NAME = raw_input('Enter AWS_KEY_NAME:')

if AWS_KEY == 'PROMPT':
    AWS_KEY = getpass('Enter AWS_KEY:')


provider2category = {
    JOB_WORKER_RUN_COMMAND_PROVIDER: 'Test',
    JOB_WORKER_START_SANDBOX_PROVIDER: 'Deploy',
    JOB_WORKER_END_SANDBOX_PROVIDER: 'Deploy',
}

codepipeline = boto3.client('codepipeline')
# todo: role

loglock = Lock()
cplock = Lock()


def log(s):
    print s
    with loglock:
        with open('quali_job_worker.log', 'a') as f:
            f.write(s + '\n')
    # todo: cloudwatch


def req(method, url, token, **kwargs):
    log('Sending %s %s %s' % (method, url, kwargs))
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    if token:
        headers['Authorization'] = 'Basic %s' % token
    r = requests.request(method, url, verify=False, headers=headers,**kwargs)
    if r.status_code >= 400:
        raise Exception('%d: %s' % (r.status_code, r.text))
    log('Received %d: %s' % (r.status_code, r.text))
    return r.text


def handle_job(job, provider):
    task = ''
    try:
        task = 'log in to CloudShell server %s domain %s as %s' % (CLOUDSHELL_URL, CLOUDSHELL_DOMAIN, CLOUDSHELL_USER)
        log(task)
        token = json.loads(req('put',
                               '%s/api/login' % CLOUDSHELL_URL,
                               None,  # no token during login
                               data=json.dumps({
                                   'username': CLOUDSHELL_USER,
                                   'password': CLOUDSHELL_PASSWORD,
                                   'domain': CLOUDSHELL_DOMAIN,
                               })))

        s3keyid = job['data']['artifactCredentials']['accessKeyId']
        s3key = job['data']['artifactCredentials']['secretAccessKey']
        s3token = job['data']['artifactCredentials']['sessionToken']

        s3 = boto3.resource('s3',
                            region_name=AWS_REGION,
                            aws_access_key_id=s3keyid,
                            aws_secret_access_key=s3key,
                            aws_session_token=s3token)

        if provider == JOB_WORKER_START_SANDBOX_PROVIDER:
            bpname = job['data']['actionConfiguration']['configuration']['BlueprintName']
            if not bpname:
                raise Exception('BlueprintName was not specified')

            bpargs = job['data']['actionConfiguration']['configuration'].get('InputsJSON', '{}')
            sandbox_name = job['data']['actionConfiguration']['configuration'].get('SandboxName',
                                                                                   '%s - CodePipeline' % bpname)
            duration_minutes = int(job['data']['actionConfiguration']['configuration'].get('DurationInMinutes', '5'))
            task = 'start sandbox %s from blueprint %s with duration %d minutes' % (sandbox_name, bpname, duration_minutes)
            log(task)

            sandbox_info_json = req('post',
                                    '%s/api/v2/blueprints/%s/start' % (CLOUDSHELL_URL, bpname),
                                    token,
                                    data=json.dumps({
                                        'duration': 'PT%dM' % duration_minutes,
                                        'name': sandbox_name,
                                        'params': [
                                            {'name': arg, 'value': value}
                                            for arg, value in json.loads(bpargs).iteritems()
                                        ]
                                    }))

            bucketname = job['data']['outputArtifacts'][0]['location']['s3Location']['bucketName']
            objectkey = job['data']['outputArtifacts'][0]['location']['s3Location']['objectKey']

            bucket = s3.Bucket(bucketname)

            task = 's3 put_object keyid=%s key=%s token=%s bucket=%s object=%s' % (s3keyid, s3key, s3token, bucketname, objectkey)
            log(task)

            bucket.put_object(Body=sandbox_info_json, Key=objectkey, ServerSideEncryption='aws:kms')
            sleep(10)

            r = json.loads(sandbox_info_json)
            resid = r['id']

            sleep(30)

            task = 'Wait for sandbox Ready %s' % resid
            log(task)
            for _ in range(120):
                r = json.loads(req('get',
                                   '%s/api/v2/sandboxes/%s' % (CLOUDSHELL_URL, resid),
                                   token))
                if r['state'] == 'Ready':
                    break
                sleep(5)
            else:
                raise Exception('Sandbox did not enter state Ready within 10 minutes')

            task = 'put_job_success_result %s' % job['id']
            log(task)

        elif provider in [JOB_WORKER_END_SANDBOX_PROVIDER, JOB_WORKER_RUN_COMMAND_PROVIDER]:
            task = 'get resid from s3'
            log(task)

            bucketname = job['data']['inputArtifacts'][0]['location']['s3Location']['bucketName']
            objectkey = job['data']['inputArtifacts'][0]['location']['s3Location']['objectKey']

            bucket = s3.Bucket(bucketname)

            sio = StringIO()

            task = 'download_fileobj from s3 keyid=%s key=%s token=%s bucket=%s object=%s' % (s3keyid, s3key, s3token, bucketname, objectkey)
            log(task)

            bucket.download_fileobj(objectkey, sio)
            sleep(10)
            sandbox_info_json = sio.getvalue()
            r = json.loads(sandbox_info_json)
            resid = r['id']

            log('Got resid %s from s3' % resid)

            if provider == JOB_WORKER_END_SANDBOX_PROVIDER:
                task = 'End sandbox %s' % resid
                log(task)
                r = json.loads(req('post',
                                   '%s/api/v2/sandboxes/%s/stop' % (CLOUDSHELL_URL, resid),
                                   token
                                   ))
            elif provider == JOB_WORKER_RUN_COMMAND_PROVIDER:
                component_name = job['data']['actionConfiguration']['configuration']['ComponentName']
                command_name = job['data']['actionConfiguration']['configuration']['CommandName']
                args_json = job['data']['actionConfiguration']['configuration'].get('ArgumentsJSON', '{}')
                task = 'Run command %s.%s(%s)' % (component_name, command_name, args_json)
                body = json.dumps({
                    "params": [
                        {"name": arg, "value": value}
                        for arg, value in json.loads(args_json).iteritems()
                    ],
                    "printOutput": True
                })
                if component_name == 'SANDBOX':
                    o = json.loads(req('post',
                                       '%s/api/v2/sandboxes/%s/commands/%s/start' % (
                                       CLOUDSHELL_URL, resid, command_name),
                                       token))
                    exid = o['executionId']
                else:
                    o = json.loads(req('get',
                                       '%s/api/v2/sandboxes/%s/components' % (CLOUDSHELL_URL, resid),
                                       token))
                    for component in o:
                        if re.match(component_name, component['name']):
                            component_id = component['id']
                            break
                    else:
                        raise Exception('Component named %s not found in sandbox %s. Available components: %s' % (component_name, resid, o))
                    o = json.loads(req('post',
                                       '%s/api/v2/sandboxes/%s/components/%s/commands/%s/start' % (
                                       CLOUDSHELL_URL, resid, component_id, command_name),
                                       token,
                                       data=body))
                    exid = o['executionId']

                for _ in range(60):
                    o = json.loads(req('get',
                                       '%s/api/v2/executions/%s' % (
                                           CLOUDSHELL_URL, exid),
                                       token,
                                       data=body))
                    if o['status'] in ['Failed', 'Error', 'Completed', 'Succeeded', 'Success']:
                        break
                    sleep(5)
                else:
                    raise Exception('Command did not complete within 5 minutes')
        with cplock:
            codepipeline.put_job_success_result(
                jobId=job['id'],
                currentRevision={
                    'revision': '1',
                    'changeIdentifier': 'x732',
                }
            )

    except Exception as e:
        msg = 'Exception on task: %s: %s' % (task, str(e))
        log(msg)
        with cplock:
            codepipeline.put_job_failure_result(
                jobId=job['id'],
                failureDetails={
                    'type': 'JobFailed',
                    'message': msg,
                }
            )


while True:
    log('poll_for_jobs...')
    for provider0 in [JOB_WORKER_RUN_COMMAND_PROVIDER,
                     JOB_WORKER_START_SANDBOX_PROVIDER,
                     JOB_WORKER_END_SANDBOX_PROVIDER]:
        with cplock:
            jobs = codepipeline.poll_for_jobs(
                    actionTypeId={
                        'category': provider2category[provider0],
                        'owner': JOB_WORKER_OWNER,
                        'provider': provider0,
                        'version': JOB_WORKER_VERSION,
                    },
                    maxBatchSize=1000000,
                    queryParam={})['jobs']
        if not jobs:
            log('No %s jobs' % provider0)
        for job0 in jobs:
            log('Job %s' % json.dumps(job0))

            log('acknowledge_job %s' % job0['id'])
            with cplock:
                codepipeline.acknowledge_job(jobId=job0['id'], nonce=job0['nonce'])
            th = Thread(target=handle_job, args=(job0, provider0), name='job-%s' % job0['id'])
            th.start()

    log('Sleep 10 seconds')
    sleep(10)
