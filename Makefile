ACCOUNT_ID=864981721755
REGION=us-east-1
REPO_NAME=stathunter-lambda-repo

.PHONY: all build tag push

all: build tag push

build:
	docker build -t $(REPO_NAME) . --provenance=false

tag:
	docker tag $(REPO_NAME):latest $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO_NAME):latest

push:
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com
	docker push $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO_NAME):latest