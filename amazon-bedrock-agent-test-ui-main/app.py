from dotenv import load_dotenv
import json
import os
import re
from services import bedrock_agent_runtime
import streamlit as st
import uuid
import boto3
import time

load_dotenv()


# --- Constants ---
REGION = os.getenv("REGION", "us-east-1")
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME")
S3_BUCKET = os.getenv("S3_BUCKET")
GITHUB_PREFIX = os.getenv("GITHUB_PREFIX", "github/")
UPLOAD_PREFIX = os.getenv("UPLOAD_PREFIX", "manual-upload/")
KB_NAME = os.getenv("KB_NAME")
AGENT_NAME = os.getenv("AGENT_NAME")

# --- AWS Clients ---
lambda_client = boto3.client("lambda", region_name=REGION)
bedrock = boto3.client("bedrock-agent", region_name=REGION)
bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)

# Get config from environment variables
agent_id = os.environ.get("BEDROCK_AGENT_ID","")
agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "TSTALIASID")  # TSTALIASID is the default test alias ID
ui_title = os.environ.get("BEDROCK_AGENT_TEST_UI_TITLE", "Welcome to Enterprise Agent")
ui_icon = os.environ.get("BEDROCK_AGENT_TEST_UI_ICON")


def init_session_state():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.citations = []
    st.session_state.trace = {}
    st.session_state.should_sync = False
    st.session_state.trace_info = ""
    st.session_state.knowledge_base_id = None
    st.session_state.agent_id = None
    st.session_state.agent_alias_id = None


# General page configuration and initialization
st.set_page_config(page_title=ui_title, page_icon=ui_icon, layout="wide")
st.title(ui_title)
if len(st.session_state.items()) == 0:
    init_session_state()

# Sidebar button to reset session state
with st.sidebar:
    if st.button("Reset Session"):
        init_session_state()

###########$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$#########

def load_existing_resources():
    if not st.session_state.knowledge_base_id:
        kbs = bedrock.list_knowledge_bases()["knowledgeBaseSummaries"]
        print("knowledgebases details------------------>",kbs)
        kb = next((k for k in kbs if k["name"] == KB_NAME), None)
        print("knowledge base details------------------>",kb)
        if kb:
            st.session_state.knowledge_base_id = kb["knowledgeBaseId"]

    if not st.session_state.agent_id:
        agents = bedrock.list_agents()["agentSummaries"]
        agent = next((a for a in agents if a["agentName"] == AGENT_NAME), None)
        if agent:
            st.session_state.agent_id = agent["agentId"]
            aliases = bedrock.list_agent_aliases(agentId=agent["agentId"])["agentAliasSummaries"]
            if aliases:
                latest_alias = sorted(aliases, key=lambda x: x.get("updatedAt", ""), reverse=True)[0]
                st.session_state.agent_alias_id = latest_alias["agentAliasId"]

def sync_knowledge_base():
    if st.session_state.knowledge_base_id:
        ingestion_jobs = bedrock.list_data_sources(knowledgeBaseId=st.session_state.knowledge_base_id)
        data_sources = ingestion_jobs.get("dataSourceSummaries", [])
        if data_sources:
            source_id = data_sources[0]["dataSourceId"]
            bedrock.start_ingestion_job(
                knowledgeBaseId=st.session_state.knowledge_base_id,
                dataSourceId=source_id
            )
            status = "STARTING"
            while status not in ["COMPLETE", "FAILED"]:
                jobs = bedrock.list_ingestion_jobs(
                    knowledgeBaseId=st.session_state.knowledge_base_id,
                    dataSourceId=source_id
                )["ingestionJobSummaries"]
                if not jobs:
                    st.error("❌ No ingestion jobs found after sync.")
                    return False
                latest = jobs[0]
                status = latest["status"]
                if status == "COMPLETE":
                    st.success("✅ Sync completed successfully.")
                    st.session_state.chat_session_id = str(uuid.uuid4())
                    return True
                elif status == "FAILED":
                    st.error("❌ Sync failed.")
                    return False
                else:
                    time.sleep(2)
        else:
            st.error("❌ No data source ID found for ingestion.")
    else:
        st.error("❌ No Knowledge Base ID found.")
    return False

# --- Load Bedrock Resources ---
load_existing_resources()

# --- Sidebar UI ---
with st.sidebar:
    st.title("📚 Knowledge Ingestion & Management")
    source_type = st.radio("Select Source", ["GitHub / Azure DevOps URL", "Upload File/Folder"])

    if source_type == "GitHub / Azure DevOps URL":
        github_url = st.text_input("Repo/File/Folder URL")
        if github_url:
            # Add a button to trigger upload and sync explicitly
            if st.button("Fetch and Upload from GitHub/Azure DevOps URL"):
                st.session_state.github_url_to_upload = github_url
                st.session_state.should_sync = True

    else:
        uploaded_files = st.file_uploader("Upload files or folders", accept_multiple_files=True)
        if uploaded_files:
            # Add a button to trigger upload and sync explicitly
            if st.button("Upload Files and Sync Knowledge Base"):
                st.session_state.files_to_upload = uploaded_files
                st.session_state.should_sync = True

    if st.session_state.trace_info:
        st.divider()
        st.subheader("🧠 Agent Trace")
        st.code(st.session_state.trace_info)

# --- Handle upload and sync only once when flagged ---
if st.session_state.should_sync:
    if "github_url_to_upload" in st.session_state and st.session_state.github_url_to_upload:
        with st.sidebar:
            with st.spinner("⏳ Triggering Lambda to fetch GitHub/Azure content..."):
                response = lambda_client.invoke(
                    FunctionName=LAMBDA_FUNCTION_NAME,
                    Payload=json.dumps({"url": st.session_state.github_url_to_upload})
                )
                result = json.load(response["Payload"])
                if result.get("statusCode") == 200:
                    st.success("✅ Content uploaded to S3 under github/")
                    with st.sidebar:
                        with st.spinner("🔄 Syncing Knowledge Base..."):
                            sync_knowledge_base()
                else:
                    st.error(f"❌ Lambda failed: {result.get('body', 'No message')}")
            # Clear after done
            st.session_state.github_url_to_upload = None

    elif "files_to_upload" in st.session_state and st.session_state.files_to_upload:
        with st.sidebar:
           with st.spinner("🚀 Uploading files to S3..."):
                for file in st.session_state.files_to_upload:
                    s3.upload_fileobj(
                        file,
                        Bucket=S3_BUCKET,
                        Key=f"{GITHUB_PREFIX}{file.name}"
                    )
                st.success(f"✅ Files uploaded to S3 under {GITHUB_PREFIX}")
        with st.sidebar:
            with st.spinner("🔄 Syncing Knowledge Base..."):
                sync_knowledge_base()
        # Clear after done
        st.session_state.files_to_upload = None

    # Reset flag
    st.session_state.should_sync = False


######################$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$##########


# Messages in the conversation
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"], unsafe_allow_html=True)

# Chat input that invokes the agent
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.empty():
            with st.spinner():
                knowledgeBaseId=st.session_state.knowledge_base_id

                response = bedrock_agent_runtime.invoke_agent(
                    agent_id,
                    agent_alias_id,
                    st.session_state.session_id,
                    prompt,
                    knowledgeBaseId
                )
            output_text = response["output_text"]

            # Check if the output is a JSON object with the instruction and result fields
            try:
                # When parsing the JSON, strict mode must be disabled to handle badly escaped newlines
                # TODO: This is still broken in some cases - AWS needs to double sescape the field contents
                output_json = json.loads(output_text, strict=False)
                if "instruction" in output_json and "result" in output_json:
                    output_text = output_json["result"]
            except json.JSONDecodeError as e:
                pass

            # Add citations
            if len(response["citations"]) > 0:
                citation_num = 1
                output_text = re.sub(r"%\[(\d+)\]%", r"<sup>[\1]</sup>", output_text)
                num_citation_chars = 0
                citation_locs = ""
                for citation in response["citations"]:
                    for retrieved_ref in citation["retrievedReferences"]:
                        citation_marker = f"[{citation_num}]"
                        citation_locs += f"\n<br>{citation_marker} {retrieved_ref['location']['s3Location']['uri']}"
                        citation_num += 1
                output_text += f"\n{citation_locs}"

            st.session_state.messages.append({"role": "assistant", "content": output_text})
            st.session_state.citations = response["citations"]
            st.session_state.trace = response["trace"]
            st.markdown(output_text, unsafe_allow_html=True)

trace_types_map = {
    "Pre-Processing": ["preGuardrailTrace", "preProcessingTrace"],
    "Orchestration": ["orchestrationTrace"],
    "Post-Processing": ["postProcessingTrace", "postGuardrailTrace"]
}

trace_info_types_map = {
    "preProcessingTrace": ["modelInvocationInput", "modelInvocationOutput"],
    "orchestrationTrace": ["invocationInput", "modelInvocationInput", "modelInvocationOutput", "observation", "rationale"],
    "postProcessingTrace": ["modelInvocationInput", "modelInvocationOutput", "observation"]
}

# Sidebar section for trace
with st.sidebar:
    st.title("Trace")

    # Show each trace type in separate sections
    step_num = 1
    for trace_type_header in trace_types_map:
        st.subheader(trace_type_header)

        # Organize traces by step similar to how it is shown in the Bedrock console
        has_trace = False
        for trace_type in trace_types_map[trace_type_header]:
            if trace_type in st.session_state.trace:
                has_trace = True
                trace_steps = {}

                for trace in st.session_state.trace[trace_type]:
                    # Each trace type and step may have different information for the end-to-end flow
                    if trace_type in trace_info_types_map:
                        trace_info_types = trace_info_types_map[trace_type]
                        for trace_info_type in trace_info_types:
                            if trace_info_type in trace:
                                trace_id = trace[trace_info_type]["traceId"]
                                if trace_id not in trace_steps:
                                    trace_steps[trace_id] = [trace]
                                else:
                                    trace_steps[trace_id].append(trace)
                                break
                    else:
                        trace_id = trace["traceId"]
                        trace_steps[trace_id] = [
                            {
                                trace_type: trace
                            }
                        ]

                # Show trace steps in JSON similar to the Bedrock console
                for trace_id in trace_steps.keys():
                    with st.expander(f"Trace Step {str(step_num)}", expanded=False):
                        for trace in trace_steps[trace_id]:
                            trace_str = json.dumps(trace, indent=2)
                            st.code(trace_str, language="json", line_numbers=True, wrap_lines=True)
                    step_num += 1
        if not has_trace:
            st.text("None")

    st.subheader("Citations")
    if len(st.session_state.citations) > 0:
        citation_num = 1
        for citation in st.session_state.citations:
            for retrieved_ref_num, retrieved_ref in enumerate(citation["retrievedReferences"]):
                with st.expander(f"Citation [{str(citation_num)}]", expanded=False):
                    citation_str = json.dumps(
                        {
                            "generatedResponsePart": citation["generatedResponsePart"],
                            "retrievedReference": citation["retrievedReferences"][retrieved_ref_num]
                        },
                        indent=2
                    )
                    st.code(citation_str, language="json", line_numbers=True, wrap_lines=True)
                citation_num = citation_num + 1
    else:
        st.text("None")
