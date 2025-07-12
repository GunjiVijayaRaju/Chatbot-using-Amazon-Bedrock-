# Agents for Amazon Bedrock Test UI

A generic Streamlit UI for testing generative AI agents built using Agents for Amazon Bedrock. For more information, refer to the blog post [Developing a Generic Streamlit UI to Test Amazon Bedrock Agents](https://blog.avangards.io/developing-a-generic-streamlit-ui-to-test-amazon-bedrock-agents).

# Prequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- [Python 3](https://www.python.org/downloads/)

# Running Locally

1. Run the following `pip` command to install the dependencies:

   ```
   pip install -r requirements.txt
   ```

2. Set the following environment variables either directly or using a `.env` file:
   - `BEDROCK_AGENT_ID` - The ID of the agent.
   - `BEDROCK_AGENT_ALIAS_ID` - The ID of the agent alias. The default `TSTALIASID` will be used if it is not set.
   - The [AWS environment variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) that provides the credentials to your account. The principal must have the necessary permissions to invoke the Bedrock agent.
3. (Optional) Set the following environment variables similarly to customize the UI:
   - `BEDROCK_AGENT_TEST_UI_TITLE` - The page title. The default `Agents for Amazon Bedrock Test UI` will used if it is not set.
   - `BEDROCK_AGENT_TEST_UI_ICON` - The favicon, such as `:bar_chart:`. The default Streamlit icon will be used if it is not set.
4. AWS Bedrock Agent Setup Instructions Set Environment Variables
```bash
BEDROCK_AGENT_ID=xxxxxx
BEDROCK_AGENT_ALIAS_ID=XXXX
REGION=xxx
LAMBDA_FUNCTION_NAME=xxxxxx
S3_BUCKET=xxxxxxxxxxxxxxx
GITHUB_PREFIX=xxxxxxxxxxxx
UPLOAD_PREFIX=xxxxxxxxxxxxxx
KB_NAME=xxxxxxxxxx
AGENT_NAME=xxxxxxxxxxxxxx
```


5. Create S3 Bucket
- Create an S3 bucket with the name `${S3_BUCKET}`.
- Enable versioning (optional).
- Upload the knowledge base data to:  
  `s3://${S3_BUCKET}/${UPLOAD_PREFIX}/`


6. Create Lambda Function
- Create a Lambda function with the name `${LAMBDA_FUNCTION_NAME}`.
- Runtime: Python 3.x
- Upload the `azure-github-lambda-code.zip` file as the Lambda source code.
- Set the handler and execution role appropriately.
- Assign the following IAM permissions to the Lambda execution role:
  - `AmazonS3FullAccess`
  - `AmazonBedrockFullAccess`
  - `AWSLambdaBasicExecutionRole`

7. Create Amazon Bedrock Knowledge Base
- Use AWS Console or API to create a Knowledge Base.
- Name the knowledge base: `${KB_NAME}`
- Use data source from S3:
  - S3 URI: `s3://${S3_BUCKET}/${UPLOAD_PREFIX}/`
- Select appropriate embeddings model and data ingestion configurations.
- Note the `knowledgeBaseId`.


8. Create Bedrock Agent
- Name the agent: `${AGENT_NAME}`
- During agent creation, configure the following:
  - Associate the previously created Knowledge Base `${KB_NAME}`.
  - Provide instructions and configuration settings.
- Note the following IDs after creation:
  - `agentId`
  - `agentAliasId`


9. ### ✅ Final Notes

- Ensure the Lambda function has necessary IAM permissions to access:
  - Amazon Bedrock APIs
  - Amazon S3 APIs

- Store the following details for future reference:
  - `S3_BUCKET`
  - `LAMBDA_FUNCTION_NAME`
  - `KB_NAME`
  - `AGENT_NAME`
  - `agentId`
  - `agentAliasId`



10. Run the following command to start the Streamlit app:

   ```
   streamlit run app.py --server.port=8080 --server.address=localhost
   ```
