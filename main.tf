variable region {
 default = "us-east-1"
}
 
provider aws {
 region = var.region
}
 
data aws_caller_identity current {}
 
locals {
 prefix = "stat-hunter-page-loader"
 account_id          = data.aws_caller_identity.current.account_id
 ecr_repository_name = "${local.prefix}-lambda-container"
 ecr_image_tag       = "latest"
}
 
resource aws_ecr_repository repo {
 name = local.ecr_repository_name
}
 
resource null_resource ecr_image {
 depends_on = [ aws_ecr_repository.repo ]

 triggers = {
   python_file = md5(file("${path.module}/lambdas/page_loader/index.py"))
   helper_file = md5(file("${path.module}/lambdas/page_loader/helpers.py"))
   docker_file = md5(file("${path.module}/lambdas/page_loader/Dockerfile"))
 }
 
 provisioner "local-exec" {
   command = <<EOF
           aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${local.account_id}.dkr.ecr.${var.region}.amazonaws.com
           cd ${path.module}/lambdas/page_loader
           docker build -t ${local.ecr_repository_name}:${local.ecr_image_tag} .
           docker push ${aws_ecr_repository.repo.repository_url}:${local.ecr_image_tag}
       EOF
 }
}
 
data aws_ecr_image lambda_image {
 depends_on = [
   null_resource.ecr_image
 ]
 repository_name = local.ecr_repository_name
 image_tag       = local.ecr_image_tag
}
 
resource aws_iam_role lambda {
 name = "${local.prefix}-lambda-role"
 assume_role_policy = <<EOF
{
   "Version": "2012-10-17",
   "Statement": [
       {
           "Action": "sts:AssumeRole",
           "Principal": {
               "Service": "lambda.amazonaws.com"
           },
           "Effect": "Allow"
       }
   ]
}
 EOF
}
 
data aws_iam_policy_document lambda {
   statement {
     actions = [
         "logs:CreateLogGroup",
         "logs:CreateLogStream",
         "logs:PutLogEvents"
     ]
     effect = "Allow"
     resources = [ "*" ]
     sid = "CreateCloudWatchLogs"
   }
 
   statement {
     actions = [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:BatchWriteItem",
        "dynamodb:BatchGetItem"
     ]
     effect = "Allow"
     resources = [ "*" ]
     sid = "DynamoDBAccess"
   }
}
 
resource aws_iam_policy lambda {
   name = "${local.prefix}-lambda-policy"
   path = "/"
   policy = data.aws_iam_policy_document.lambda.json
}
 
resource aws_lambda_function page_loader {
 depends_on = [
   null_resource.ecr_image
 ]
 function_name = "${local.prefix}-lambda"
 role = aws_iam_role.lambda.arn
 timeout = 300
 image_uri = "${aws_ecr_repository.repo.repository_url}@${data.aws_ecr_image.lambda_image.id}"
 package_type = "Image"
}
 
output "lambda_name" {
 value = aws_lambda_function.page_loader.id
}