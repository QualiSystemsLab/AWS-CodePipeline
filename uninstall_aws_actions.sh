#!/bin/bash

v=9

aws codepipeline delete-custom-action-type --category Deploy  --provider Quali-Start-Sandbox --action-version $v
aws codepipeline delete-custom-action-type --category Deploy  --provider Quali-End-Sandbox --action-version $v
aws codepipeline delete-custom-action-type --category Test  --provider Quali-Run-Command --action-version $v
