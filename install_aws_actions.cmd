pip install awscli

call aws codepipeline create-custom-action-type --cli-input-json file://QualiStartSandboxAction.json
call aws codepipeline create-custom-action-type --cli-input-json file://QualiEndSandboxAction.json
call aws codepipeline create-custom-action-type --cli-input-json file://QualiRunCommandAction.json
