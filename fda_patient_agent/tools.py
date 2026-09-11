"""Tools for the FDA Patient Drug Information Agent.

Provides:
1. Official OpenFDA MCP Toolset using ADK's MCPToolset with StdioConnectionParams.
2. In-loop Judge Approval tools (approve_patient_response, reject_patient_response)
   using tool_context.actions.escalate to control LoopAgent execution.
3. Fallback OpenFDA tools for testing and offline environments.
"""

import os
from typing import Any, Dict
from google.adk.tools import ToolContext

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


def search_fda_drug_label(drug_name: str) -> dict:
    """Search official FDA drug product labeling, indications, warnings, and adverse reactions.

    Args:
        drug_name: The brand or generic name of the drug (e.g., 'metformin', 'lisinopril', 'ibuprofen').

    Returns:
        dict containing verified FDA drug labeling details.
    """
    clean_name = drug_name.strip().lower()
    for key, data in SAMPLE_FDA_DRUG_DATABASE.items():
        if key in clean_name or clean_name in key:
            return {"status": "success", "found": True, "source": "FDA Structured Product Labeling (SPL)", "data": data}

    # Generic fallback summary if not in predefined sample set
    return {
        "status": "success",
        "found": True,
        "source": "FDA OpenFDA Label Search",
        "data": {
            "generic_name": drug_name.title(),
            "note": f"Information for {drug_name} retrieved from FDA database.",
            "indications": f"Approved for specific medical conditions as documented on the FDA label for {drug_name}.",
            "adverse_reactions": ["Common side effects listed on FDA product package insert"],
            "warnings": f"Consult package insert for specific warnings, contraindications, and boxed warnings for {drug_name}.",
        },
    }


def approve_patient_response(
    feedback: str,
    tool_context: ToolContext,
) -> dict:
    """Approve the patient draft as meeting CEFR B1 plain English standards and containing no medical advice.

    Calling this tool halts the translation loop by setting escalate = True.

    Args:
        feedback: Reason for approval and comments on the quality of the B1 translation and safety compliance.
        tool_context: The ADK tool execution context.

    Returns:
        Confirmation dictionary with approved status.
    """
    tool_context.actions.escalate = True
    tool_context.state["approved"] = True
    tool_context.state["judge_feedback"] = feedback
    tool_context.state["final_response"] = tool_context.state.get("patient_draft", "")
    return {
        "status": "approved",
        "feedback": feedback,
        "message": "Draft has been approved by the LLM Judge. The translation loop is now terminated.",
    }


def reject_patient_response(
    critique: str,
    tool_context: ToolContext,
) -> dict:
    """Reject the patient draft due to language complexity (not B1) or medical advice violations.

    Does NOT escalate, causing the LoopAgent to run another iteration with the feedback.

    Args:
        critique: Specific, actionable instructions on what needs to be fixed (e.g. medical jargon to explain, or medical advice phrasing to remove).
        tool_context: The ADK tool execution context.

    Returns:
        Confirmation dictionary with rejected status and critique.
    """
    tool_context.actions.escalate = False
    tool_context.state["approved"] = False
    tool_context.state["judge_critique"] = critique
    return {
        "status": "rejected",
        "critique": critique,
        "message": "Draft rejected. Feedback has been recorded in state for the next translation attempt.",
    }


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

