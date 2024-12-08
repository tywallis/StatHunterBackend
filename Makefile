ACCOUNT_ID=864981721755
REGION=us-east-1
REPO_NAME=stathunter-lambda-repo
FUNCTION_NAME=stathunter_lambda_function

.PHONY: all docker lambda

all: docker lambda

docker: build tag push

build:
	docker build -t $(REPO_NAME) . --provenance=false

tag:
	docker tag $(REPO_NAME):latest $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO_NAME):latest

push:
	aws ecr get-login-password --region $(REGION) | docker login --username AWS --password-stdin $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com
	docker push $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO_NAME):latest

lambda:
	aws lambda update-function-code --function-name $(FUNCTION_NAME) --image-uri $(ACCOUNT_ID).dkr.ecr.$(REGION).amazonaws.com/$(REPO_NAME):latest