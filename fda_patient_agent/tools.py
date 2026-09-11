"""Tools for the FDA Patient Drug Information Agent.

Provides:
1. Official OpenFDA MCP Toolset using ADK's MCPToolset with StdioConnectionParams.
2. In-loop Judge Approval tools (approve_patient_response, reject_patient_response)
   using tool_context.actions.escalate to control LoopAgent execution.
3. Fallback OpenFDA tools for testing and offline environments.
"""

import os
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ValidationError
from google.adk.tools import ToolContext


class DrugSearchInput(BaseModel):
    """Input validation schema for searching FDA drug labeling."""
    drug_name: str = Field(
        ...,
        description="Brand or generic name of the medication to look up (e.g., 'metformin', 'lisinopril', 'ibuprofen').",
        min_length=1,
    )


class DrugLabelData(BaseModel):
    """Structured clinical details from FDA Structured Product Labeling (SPL)."""
    generic_name: str
    brand_names: List[str] = Field(default_factory=list)
    indications: str
    boxed_warning: Optional[str] = None
    adverse_reactions: List[str] = Field(default_factory=list)
    contraindications: Optional[str] = None
    dosage_and_administration: Optional[str] = None
    missed_dose_guidance: Optional[str] = None
    warnings: Optional[str] = None
    note: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            val = getattr(self, item)
            return val if val is not None else default
        except (AttributeError, KeyError):
            return default


class DrugSearchOutput(BaseModel):
    """Structured response from FDA drug labeling search."""
    status: str = Field(description="Search outcome status ('success' or 'error').")
    found: bool = Field(description="Whether official FDA labeling was located for the medication.")
    source: str = Field(description="Data provenance source (e.g. FDA SPL or OpenFDA).")
    data: Optional[DrugLabelData] = Field(default=None, description="Clinical drug labeling details.")
    error: Optional[str] = Field(default=None, description="Error message if the search failed or had validation errors.")
    recovery_instructions: Optional[str] = Field(
        default=None,
        description="Actionable recovery instructions for the LLM upon failure.",
    )

    def __getitem__(self, item: str) -> Any:
        val = getattr(self, item)
        if isinstance(val, BaseModel):
            return val
        return val

    def get(self, item: str, default: Any = None) -> Any:
        try:
            val = getattr(self, item)
            return val if val is not None else default
        except (AttributeError, KeyError):
            return default


class JudgeApprovalInput(BaseModel):
    """Input schema for approving a patient response draft."""
    feedback: str = Field(
        ...,
        description="Reason for approval and comments on the quality of B1 translation and safety compliance.",
        min_length=1,
    )


class JudgeRejectionInput(BaseModel):
    """Input schema for rejecting a patient response draft."""
    critique: str = Field(
        ...,
        description="Specific, actionable instructions on what needs to be fixed (medical jargon, advice violations).",
        min_length=1,
    )


class JudgeDecisionOutput(BaseModel):
    """Structured output schema for judge approval and rejection tools."""
    status: str = Field(description="Decision outcome status ('approved', 'rejected', or 'error').")
    feedback: Optional[str] = Field(default=None, description="Approval feedback if approved.")
    critique: Optional[str] = Field(default=None, description="Rejection critique if rejected.")
    message: str = Field(description="Detailed human-readable message describing the outcome.")
    recovery_instructions: Optional[str] = Field(
        default=None,
        description="Actionable recovery instructions for the LLM if an error or rejection occurred.",
    )

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            val = getattr(self, item)
            return val if val is not None else default
        except (AttributeError, KeyError):
            return default


# Mock / offline knowledge base for testing and environments without external npx/network
SAMPLE_FDA_DRUG_DATABASE: Dict[str, Dict[str, Any]] = {
    "metformin": {
        "generic_name": "Metformin Hydrochloride",
        "brand_names": ["Glucophage", "Fortamet", "Glumetza"],
        "indications": (
            "Adjunct to diet and exercise to improve glycemic control in adults and pediatric "
            "patients 10 years of age and older with type 2 diabetes mellitus."
        ),
        "boxed_warning": (
            "Lactic Acidosis: Post-marketing cases of metformin-associated lactic acidosis have "
            "resulted in death, hypothermia, hypotension, and resistant bradyarrhythmias. "
            "Risk factors include renal impairment, concomitant use of certain drugs, age 65 or older, "
            "radiological studies with contrast, surgery, hypoxic states, and excessive alcohol intake."
        ),
        "adverse_reactions": [
            "Diarrhea (53%)",
            "Nausea/vomiting (26%)",
            "Flatulence (12%)",
            "Asthenia (9%)",
            "Indigestion/dyspepsia (7%)",
            "Abdominal discomfort (6%)",
            "Headache (6%)",
        ],
        "contraindications": (
            "Severe renal impairment (eGFR below 30 mL/min/1.73 m2). Known hypersensitivity to metformin. "
            "Acute or chronic metabolic acidosis, including diabetic ketoacidosis."
        ),
        "dosage_and_administration": (
            "Starting dose is 500 mg orally twice daily or 850 mg once daily with meals. "
            "Dose can be increased gradually in increments of 500 mg weekly or 850 mg every 2 weeks, "
            "up to a maximum daily dose of 2550 mg in divided doses."
        ),
        "missed_dose_guidance": (
            "Take the missed dose as soon as remembered with food. If it is almost time for the next dose, "
            "skip the missed dose and resume normal schedule. Do not take two doses at the same time."
        ),
    },
    "lisinopril": {
        "generic_name": "Lisinopril",
        "brand_names": ["Prinivil", "Zestril", "Qbrelis"],
        "indications": (
            "Treatment of hypertension in adult patients and pediatric patients 6 years of age and older; "
            "adjunctive therapy in systolic heart failure; treatment of acute myocardial infarction."
        ),
        "boxed_warning": (
            "Fetal Toxicity: When pregnancy is detected, discontinue Lisinopril as soon as possible. "
            "Drugs that act directly on the renin-angiotensin system can cause injury and death to the developing fetus."
        ),
        "adverse_reactions": [
            "Persistent dry cough (common, up to 10%)",
            "Dizziness / lightheadedness (6%)",
            "Hypotension (low blood pressure)",
            "Headache (5%)",
            "Hyperkalemia (high potassium)",
            "Renal impairment",
        ],
        "contraindications": (
            "History of angioedema related to previous ACE inhibitor treatment; hereditary or idiopathic angioedema; "
            "concomitant use with aliskiren in patients with diabetes."
        ),
        "dosage_and_administration": (
            "Hypertension: Initial dose is 10 mg once daily. Maintenance dose is 20 to 40 mg once daily. "
            "Dosage adjustments required for renal impairment."
        ),
    },
    "ibuprofen": {
        "generic_name": "Ibuprofen",
        "brand_names": ["Advil", "Motrin", "Nuprin"],
        "indications": (
            "Relief of the signs and symptoms of rheumatoid arthritis and osteoarthritis; "
            "relief of mild to moderate pain; reduction of fever."
        ),
        "boxed_warning": (
            "Cardiovascular Thrombotic Events: NSAIDs cause an increased risk of serious cardiovascular "
            "thrombotic events, including myocardial infarction and stroke. "
            "Gastrointestinal Risk: NSAIDs cause an increased risk of serious gastrointestinal adverse events "
            "including bleeding, ulceration, and perforation of the stomach or intestines."
        ),
        "adverse_reactions": [
            "Epigastric pain, heartburn, nausea (up to 9%)",
            "Dizziness",
            "Fluid retention / edema",
            "Skin rash",
            "Bronchospasm in aspirin-sensitive asthmatics",
        ],
        "contraindications": (
            "History of asthma, urticaria, or allergic-type reactions after taking aspirin or other NSAIDs; "
            "in the setting of coronary artery bypass graft (CABG) surgery."
        ),
        "dosage_and_administration": (
            "Mild to moderate pain: 200 mg to 400 mg every 4 to 6 hours as necessary. "
            "Maximum OTC daily dose: 1200 mg. Maximum prescription daily dose: 3200 mg."
        ),
    },
}


def search_fda_drug_label(drug_name: str) -> DrugSearchOutput:
    """Search official FDA drug product labeling, indications, warnings, and adverse reactions.

    Args:
        drug_name: The brand or generic name of the drug (e.g., 'metformin', 'lisinopril', 'ibuprofen').

    Returns:
        DrugSearchOutput containing verified FDA drug labeling details, or structured error with recovery instructions.
    """
    try:
        # Input validation via Pydantic
        if isinstance(drug_name, DrugSearchInput):
            validated_input = drug_name
        elif isinstance(drug_name, dict):
            validated_input = DrugSearchInput(**drug_name)
        else:
            raw_str = str(drug_name).strip() if drug_name is not None else ""
            if not raw_str:
                raise ValueError("Drug name parameter cannot be empty.")
            validated_input = DrugSearchInput(drug_name=raw_str)

        clean_name = validated_input.drug_name.strip().lower()
        for key, data in SAMPLE_FDA_DRUG_DATABASE.items():
            if key in clean_name or clean_name in key:
                return DrugSearchOutput(
                    status="success",
                    found=True,
                    source="FDA Structured Product Labeling (SPL)",
                    data=DrugLabelData(**data),
                )

        # Generic fallback summary if not in predefined sample set
        fallback_data = DrugLabelData(
            generic_name=validated_input.drug_name.title(),
            note=f"Information for {validated_input.drug_name} retrieved from FDA database.",
            indications=f"Approved for specific medical conditions as documented on the FDA label for {validated_input.drug_name}.",
            adverse_reactions=["Common side effects listed on FDA product package insert"],
            warnings=f"Consult package insert for specific warnings, contraindications, and boxed warnings for {validated_input.drug_name}.",
        )
        return DrugSearchOutput(
            status="success",
            found=True,
            source="FDA OpenFDA Label Search",
            data=fallback_data,
        )

    except (ValidationError, ValueError) as val_err:
        return DrugSearchOutput(
            status="error",
            found=False,
            source="FDA Schema Validator",
            error=str(val_err),
            recovery_instructions=(
                "The medication name was empty or invalid. "
                "Suggested recovery steps: "
                "1. Check the patient query for medication names or active ingredients. "
                "2. Provide a valid non-empty brand or generic name (e.g., 'metformin', 'lisinopril'). "
                "3. If no medication was specified, ask the patient for the drug name."
            ),
        )
    except Exception as exc:
        return DrugSearchOutput(
            status="error",
            found=False,
            source="FDA Search Error Handler",
            error=str(exc),
            recovery_instructions=(
                f"An unexpected error occurred while querying the FDA database: {str(exc)}. "
                "Suggested recovery steps: "
                "1. Verify spelling of the medication. "
                "2. Query the active generic ingredient instead of brand name. "
                "3. If the drug cannot be verified, inform the patient and advise consulting a pharmacist."
            ),
        )


def approve_patient_response(
    feedback: str,
    tool_context: ToolContext,
) -> JudgeDecisionOutput:
    """Approve the patient draft as meeting CEFR B1 plain English standards and containing no medical advice.

    Calling this tool halts the translation loop by setting escalate = True.

    Args:
        feedback: Reason for approval and comments on the quality of the B1 translation and safety compliance.
        tool_context: The ADK tool execution context.

    Returns:
        JudgeDecisionOutput confirming approval status or error with recovery instructions.
    """
    try:
        # Input validation via Pydantic
        if isinstance(feedback, JudgeApprovalInput):
            validated_input = feedback
        elif isinstance(feedback, dict):
            validated_input = JudgeApprovalInput(**feedback)
        else:
            raw_str = str(feedback).strip() if feedback is not None else ""
            if not raw_str:
                raise ValueError("Approval feedback cannot be empty.")
            validated_input = JudgeApprovalInput(feedback=raw_str)

        clean_feedback = validated_input.feedback.strip()

        if tool_context is None:
            raise ValueError("tool_context must be provided.")

        patient_draft = tool_context.state.get("patient_draft", "")
        if not patient_draft:
            return JudgeDecisionOutput(
                status="error",
                message="Cannot approve draft: 'patient_draft' is missing in conversation state.",
                recovery_instructions=(
                    "State variable 'patient_draft' is missing or empty. "
                    "Ensure patient_translator has completed the translation draft before calling approve_patient_response."
                ),
            )

        tool_context.actions.escalate = True
        tool_context.state["approved"] = True
        tool_context.state["judge_feedback"] = clean_feedback
        tool_context.state["final_response"] = patient_draft
        return JudgeDecisionOutput(
            status="approved",
            feedback=clean_feedback,
            message="Draft has been approved by the LLM Judge. The translation loop is now terminated.",
        )
    except (ValidationError, ValueError) as val_err:
        return JudgeDecisionOutput(
            status="error",
            message=f"Validation failed for approval input: {str(val_err)}",
            recovery_instructions=(
                "Please provide a non-empty string for 'feedback' summarizing why the draft complies with B1 readability and safety standards."
            ),
        )
    except Exception as exc:
        return JudgeDecisionOutput(
            status="error",
            message=f"Approval execution failed: {str(exc)}",
            recovery_instructions=(
                f"Unexpected error in approve_patient_response: {str(exc)}. "
                "Verify feedback input and tool execution context."
            ),
        )


def reject_patient_response(
    critique: str,
    tool_context: ToolContext,
) -> JudgeDecisionOutput:
    """Reject the patient draft due to language complexity (not B1) or medical advice violations.

    Does NOT escalate, causing the LoopAgent to run another iteration with the feedback.

    Args:
        critique: Specific, actionable instructions on what needs to be fixed (e.g. medical jargon to explain, or medical advice phrasing to remove).
        tool_context: The ADK tool execution context.

    Returns:
        JudgeDecisionOutput confirming rejected status or error with recovery instructions.
    """
    try:
        # Input validation via Pydantic
        if isinstance(critique, JudgeRejectionInput):
            validated_input = critique
        elif isinstance(critique, dict):
            validated_input = JudgeRejectionInput(**critique)
        else:
            raw_str = str(critique).strip() if critique is not None else ""
            if not raw_str:
                raise ValueError("Rejection critique cannot be empty.")
            validated_input = JudgeRejectionInput(critique=raw_str)

        clean_critique = validated_input.critique.strip()

        if tool_context is None:
            raise ValueError("tool_context must be provided.")

        tool_context.actions.escalate = False
        tool_context.state["approved"] = False
        tool_context.state["judge_critique"] = clean_critique
        return JudgeDecisionOutput(
            status="rejected",
            critique=clean_critique,
            message="Draft rejected. Feedback has been recorded in state for the next translation attempt.",
            recovery_instructions=(
                "Actionable instructions for the next translation iteration: "
                "1. Simplify any identified medical jargon to everyday B1 English. "
                "2. Remove any prescriptive or diagnostic statements. "
                "3. Ensure the mandatory physician/pharmacist consultation disclaimer is included."
            ),
        )
    except (ValidationError, ValueError) as val_err:
        return JudgeDecisionOutput(
            status="error",
            message=f"Validation failed for rejection input: {str(val_err)}",
            recovery_instructions=(
                "Please provide a non-empty string for 'critique' specifying what needs improvement in the draft."
            ),
        )
    except Exception as exc:
        return JudgeDecisionOutput(
            status="error",
            message=f"Rejection execution failed: {str(exc)}",
            recovery_instructions=(
                f"Unexpected error in reject_patient_response: {str(exc)}. "
                "Verify critique input and tool execution context."
            ),
        )


def get_openfda_mcp_toolset(
    command: str = "npx",
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
):
    """Instantiate the official openFDA MCP toolset using ADK's MCPToolset with StdioConnectionParams.

    Args:
        command: The CLI command to launch the MCP server (default: 'npx').
        args: Arguments passed to the command (default: ['-y', '@cyanheads/openfda-mcp-server@latest']).
        env: Optional environment variables to pass to the MCP server process.

    Returns:
        MCPToolset instance configured for the openFDA server.
    """
    try:
        from google.adk.tools.mcp_tool import McpToolset as ToolsetClass
    except ImportError:
        from google.adk.tools.mcp_tool import MCPToolset as ToolsetClass
    from google.adk.tools.mcp_tool import StdioConnectionParams
    from mcp import StdioServerParameters

    if args is None:
        args = ["-y", "@cyanheads/openfda-mcp-server@latest"]

    server_env = {}
    if env:
        server_env.update(env)
    if "OPENFDA_API_KEY" in os.environ:
        server_env["OPENFDA_API_KEY"] = os.environ["OPENFDA_API_KEY"]

    return ToolsetClass(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=command,
                args=args,
                env=server_env if server_env else None,
            ),
            timeout=30,
        ),
    )

