from diagrams import Diagram
from diagrams.aws.analytics import Athena, GlueDataCatalog
from diagrams.aws.compute import Lambda
from diagrams.aws.ml import Comprehend
from diagrams.aws.security import SecretsManager
from diagrams.aws.storage import S3
from diagrams.onprem.client import Users

with Diagram(
    "Youtube Comment Sentiment Analysis", show=False, filename="img/architecture"
):
    # Resources
    lambda_function = Lambda("Lambda Function")
    s3_bucket = S3("S3 Bucket")
    secrets_manager = SecretsManager("AWS Secrets Manager")
    comprehend = Comprehend("AWS Comprehend")
    glue_data_catalog = GlueDataCatalog("Glue Data Catalog")
    athena = Athena("Athena")
    users = Users("Users")

    # Relationships
    lambda_function >> [s3_bucket, comprehend, secrets_manager]
    users >> athena >> glue_data_catalog >> s3_bucket
