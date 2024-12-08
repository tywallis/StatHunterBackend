# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.12

ENV PYBASEBALL_CACHE=/tmp
ENV MPLCONFIGDIR=/tmp

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}
COPY helpers.py ${LAMBDA_TASK_ROOT}

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Set the CMD to your handler
CMD ["app.lambda_handler"]