FROM public.ecr.aws/lambda/python:3.12

# Copy requirements.txt
COPY src/dynamo_loader/requirements.txt ${LAMBDA_TASK_ROOT}

# Install the specified packages
RUN pip install -r requirements.txt

# Copy function code
COPY src/dynamo_loader/app.py ${LAMBDA_TASK_ROOT}

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "src.dynamo_loader.app.lambda_handler" ]