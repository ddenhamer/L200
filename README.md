# FDA Patient Drug Information Agent & Evaluation Suite

A production-ready healthcare multi-agent system built using **Google's Agent Development Kit (ADK 2.x)**.

The agent empowers patients and caregivers by retrieving official FDA drug product labeling through the official **OpenFDA MCP Server**, translating clinical terminology into accessible **CEFR B1 plain English**, and verifying safety and clarity via an in-loop **LLM-as-a-Judge** approval gate.

The application is packaged inside an ADK `App` configured for **Google Cloud Agent Runtime**, featuring automatic session memory that survives network drops, resumable workflows, and full OpenTelemetry Generative AI tracing.

---

## Architecture

```
                                  Patient Query
                        (Drug Name + Medical Question)
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │            ADK App Wrapper (AgentRuntime)        │
             │   - ResumabilityConfig(is_resumable=True)        │
             │   - Automatic Session Memory & Trace Observability│
             └────────────────────────┬─────────────────────────┘
                                      │
                                      ▼
                      1. Drug Information Retrieval Agent
                         (Official OpenFDA MCPToolset)
                                      │
                                      │ writes: state["drug_info"]
                                      ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        2. Iterative Translation & Review Loop                          │
│                                (LoopAgent, max_iterations=3)                            │
│                                                                                        │
│   ┌────────────────────────────────────────┐                                           │
│   │   2a. Patient Translation Agent        │◄────────────────────────────────┐         │
│   │   - Translates to CEFR B1 English      │                                 │         │
│   │   - Plain language explanations        │                                 │         │
│   │   - Strict NO medical advice rule      │                                 │         │
│   └───────────────────┬────────────────────┘                                 │         │
│                       │ writes: state["patient_draft"]                       │         │
│                       ▼                                                      │         │
│   ┌────────────────────────────────────────┐      approve_patient_response   │         │
│   │   2b. LLM-as-a-Judge Reviewer Agent    ├─────────────────────────────┐   │         │
│   │   - Verifies English B1 readability    │     (escalate = True)       │   │         │
│   │   - Verifies NO medical advice         │                             │   │         │
│   └───────────────────┬────────────────────┘                             │   │         │
│                       │                                                  │   │         │
│                       │ reject_patient_response                          │   │         │
│                       │ (critique recorded in state, escalate = False)   │   │         │
│                       └──────────────────────────────────────────────────┘   │         │
│                                                                              │         │
└──────────────────────────────────────────────────────────────────────────────┼─────────┘
                                                                               │
                                                                               ▼
                                                            3. Patient Responder Agent
                                                               - Formatted markdown
                                                               - Doctor/Pharmacist disclaimer
                                                                               │
                                                                               ▼
                                                                     Final Patient Response
```

---

## Key Features

### 1. Official OpenFDA MCP Integration
Retrieves real-time FDA structured product labeling (SPL), boxed warnings, indications, adverse events, contraindications, and dosage instructions using ADK's `McpToolset` connecting via Stdio to `@cyanheads/openfda-mcp-server@latest`.

### 2. Patient-Friendly Translation (CEFR B1 English)
Dense clinical language (e.g. *dyspepsia*, *contraindication*, *pharmacokinetics*) is automatically rendered into clear, everyday English with short sentences (15–20 words) and clean bullet points.

### 3. Strict Safety Guardrails & In-Loop LLM-as-a-Judge
The agent strictly refuses to prescribe, diagnose, or advise patients to change medication dosages. The LLM-as-a-Judge evaluates every draft against two criteria:
- **Criterion 1 (CEFR B1 Readability):** Intermediate English readability without unexplained medical jargon.
- **Criterion 2 (No Medical Advice):** Purely educational framing grounded in FDA labeling, with mandatory advice to consult a physician or pharmacist.
- **Approval Gating:** The judge calls `approve_patient_response` to set `tool_context.actions.escalate = True` and break the loop. If rejected, it calls `reject_patient_response` with critique so the translator can self-correct.

### 4. Deployable to Google Cloud Agent Runtime
- **Automatic Session Memory:** Seamlessly uses `VertexAiSessionService` on Agent Runtime to preserve conversation history and state across network drops or client disconnects.
- **Resumability:** Configured with `ResumabilityConfig(is_resumable=True)` to resume execution from the exact sub-agent state without repeating expensive tool calls.
- **Built-in Observability & OpenTelemetry:** Fully instrumented with OpenTelemetry semantic conventions for Generative AI traces.

### 5. PII/PHI Redaction via Model Armor & Cloud DLP
- **Healthcare Safe Harbor:** Intercepts patient prompts and model responses using `ModelArmorPiiPlugin` to scrub names, SSNs, phone numbers, emails, and medical record numbers into semantic tokens (`[PERSON_NAME]`, `[DATE_OF_BIRTH]`, `[US_SSN]`).
- **Telemetry Protection:** Sanitization executes *before* model invocation, guaranteeing that OpenTelemetry Generative AI traces (`EVENT_ONLY`) and Agent Runtime session memory never store unredacted PHI.
- **Infrastructure as Code (Terraform):** Complete Terraform module in `terraform/` defining Google Cloud Sensitive Data Protection (DLP) de-identification templates and Model Armor guardrails.

---

## Project Structure

```
L200/
├── fda_patient_agent/
│   ├── __init__.py               # Exports root_agent and app (from . import agent)
│   ├── agent.py                  # Pipeline composition, App configuration, and tracing setup
│   ├── prompts.py                # System prompts for retrieval, translation, judge, and responder
│   ├── tools.py                  # OpenFDA MCPToolset, approve/reject tools, and fallback tools
│   ├── guardrails/
│   │   ├── __init__.py
│   │   └── pii_plugin.py         # Model Armor & Cloud DLP PII/PHI redaction plugin
│   └── sub_agents/
│       ├── __init__.py           # Sub-agent exports
│       ├── drug_info_agent.py    # OpenFDA retrieval agent
│       ├── translator_agent.py   # B1 English translation agent
│       └── judge_agent.py        # LLM-as-a-Judge gatekeeper agent
├── terraform/
│   ├── main.tf                   # Cloud DLP de-identify template & Model Armor template
│   ├── variables.tf              # GCP project, region, and template configurations
│   └── outputs.tf                # Template IDs and resource references
├── eval/
│   ├── patient_agent.evalset.json # ADK evaluation dataset covering common, OTC, and safety boundary cases
│   ├── test_config.json          # Rubric configuration for B1 readability & medical advice prevention
│   └── run_eval.py               # Automated evaluation benchmark script
├── tests/
│   ├── __init__.py
│   ├── test_agent.py             # Pytest suite verifying architecture, tools, and session lifecycle
│   └── test_pii_sanitizer.py     # Tests for PII/PHI redaction and plugin callbacks
├── .env.example                  # Environment configuration template
├── pyproject.toml                # Dependencies (google-adk>=2.0.0, mcp>=1.0.0,<2.0.0, pydantic)
└── README.md
```


---

## Configuration & Environment Variables

Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

### Authentication Options

**Option A: Vertex AI (Recommended for Agent Runtime)**
```bash
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

**Option B: Gemini API Key (Direct API Access)**
```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

### OpenTelemetry Tracing

These are automatically enabled in `fda_patient_agent/agent.py`:
```python
# Enable OpenTelemetry semantic conventions for Generative AI
os.environ["OTEL_SEMCONV_STABILITY_OPT_IN"] = "gen_ai_latest_experimental"
# Ensure full message content (prompts & responses) is captured in trace events
os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "EVENT_ONLY"
```

---

## Local Verification & Testing

### 1. Run Unit & Integration Tests
Execute the pytest suite:
```bash
python3 -m pytest tests/ -v
```

All 16 tests verify:
- Pipeline composition and sub-agent bindings
- `App` configuration and `ResumabilityConfig(is_resumable=True)`
- ModelArmor PII/PHI redaction plugin and semantic token replacement
- OpenTelemetry environment setup
- OpenFDA data retrieval and fallback mechanisms
- Official MCPToolset instantiation
- Judge approval escalation (`escalate = True`) and loop termination
- Judge rejection without escalation (`escalate = False`)
- Session lifecycle and memory handling via `InMemoryRunner`

### 2. Run the LLM-as-a-Judge Evaluation Suite
Execute the automated evaluation runner:
```bash
python3 eval/run_eval.py
```

This runs test cases across:
1. **Lisinopril:** Prescription hypertension medication and cough adverse reaction.
2. **Ibuprofen:** OTC NSAID warnings regarding stomach ulcers and asthma risk.
3. **Metformin:** Safety boundary test checking that the agent refuses to give dosing advice for a missed dose and instructs consulting a physician.

---

## Infrastructure Provisioning (Terraform)

Provision the Google Cloud Sensitive Data Protection (DLP) and Model Armor templates:

```bash
cd terraform
terraform init
terraform apply -var="project_id=YOUR_PROJECT_ID" -var="region=us-central1"
```

This outputs `model_armor_template_id`, which can be set in your `.env`:
```bash
export MODEL_ARMOR_TEMPLATE_ID="fda-patient-agent-model-armor"
```

---

## Deployment to Agent Runtime

Deploy directly to Google Cloud Agent Runtime (Vertex AI Agent Engine) using the ADK CLI:

```bash
# 1. Authenticate with Google Cloud
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# 2. Deploy to Agent Runtime
adk deploy agent_engine \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --agent=fda_patient_agent \
  --display_name="FDA Patient Drug Advocate"
```

### What Agent Runtime Handles Automatically
- **Session Memory:** Agent Runtime backs sessions with Google Cloud's managed session service (`VertexAiSessionService`), maintaining memory across connection drops.
- **Resumability:** If an invocation is interrupted during a tool call or review step, the agent resumes seamlessly without repeating completed actions.
- **Tracing & Observability:** All agent events, model calls, and tool interactions are automatically exported to Google Cloud Trace.
- **Data Protection:** Paired with `ModelArmorPiiPlugin`, sensitive health identifiers are sanitized prior to reaching session memory or trace logs.


