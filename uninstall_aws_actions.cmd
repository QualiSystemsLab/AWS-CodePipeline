set v=9

call aws codepipeline delete-custom-action-type --category Deploy  --provider Quali-Start-Sandbox --action-version %v%
call aws codepipeline delete-custom-action-type --category Deploy  --provider Quali-End-Sandbox --action-version %v%
call aws codepipeline delete-custom-action-type --category Test  --provider Quali-Run-Command --action-version %v%
