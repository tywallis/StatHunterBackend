# Use the official AWS Lambda Python base image
FROM public.ecr.aws/lambda/python:3.11

ENV PYBASEBALL_CACHE=/tmp
ENV MPLCONFIGDIR=/tmp
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

# Copy function code
COPY app.py ${LAMBDA_TASK_ROOT}

# Copy loaders
COPY loaders ${LAMBDA_TASK_ROOT}/loaders

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Set the CMD to your handler
CMD ["app.lambda_handler"]