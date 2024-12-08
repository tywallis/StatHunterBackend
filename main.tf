provider "aws" {
  region = "us-east-1"
}

resource "aws_ecr_repository" "stathunter_lambda" {
  name = "stathunter-lambda-repo"
}

resource "aws_iam_role" "stathunter_lambda_role" {
  name = "stathunter-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "stathunter_lambda_policy" {
  role       = aws_iam_role.stathunter_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "stathunter_lambda" {
  function_name = "stathunter_lambda_function"
  role          = aws_iam_role.stathunter_lambda_role.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.stathunter_lambda.repository_url}:latest"
}

resource "aws_lambda_function_url" "stathunter_lambda_url" {
  function_name = aws_lambda_function.stathunter_lambda.function_name
  authorization_type = "NONE"
}

output "stathunter_lambda_function_url" {
  value = aws_lambda_function_url.stathunter_lambda_url.function_url
}