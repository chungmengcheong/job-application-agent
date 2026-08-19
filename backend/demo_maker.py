"""Utility program to create files for demo API response and input to the LLM."""
import json
from pathlib import Path

from backend.paths import (
    ADDITIONAL_EXPERIENCE_FILE,
    JOB_DESCRIPTION_DEMO_FILE,
    OUTPUT_FROM_LLM_CURRENT_FILE,
    REPO_ROOT,
    RESPONSE_REVIEW_ADD_INFO_DEMO_FILE,
    RESPONSE_REVIEW_DEMO_FILE,
    RESUME_BASELINE_FILE,
    USER_RESPONSE_FILE,
)
from backend.redline import redline_diff as create_resume_diff


def create_prompt_json_input():
    """Create the JSON input for the LLM."""
    input_dict = {}

    input_dict["Job_Description"] = JOB_DESCRIPTION_DEMO_FILE.read_text()
    input_dict["Resume"] = RESUME_BASELINE_FILE.read_text()
    input_dict["Additional_Info"] = ADDITIONAL_EXPERIENCE_FILE.read_text()
    if OUTPUT_FROM_LLM_CURRENT_FILE.exists():
        input_dict["Fit"] = OUTPUT_FROM_LLM_CURRENT_FILE.read_text()
        input_dict["Gap_Map"] = OUTPUT_FROM_LLM_CURRENT_FILE.read_text()
    if USER_RESPONSE_FILE.exists():
        input_dict["qa_pairs"] = USER_RESPONSE_FILE.read_text()

    json_file = REPO_ROOT / "LLM_JSON_input.json"
    json_file.write_text(json.dumps(input_dict, indent=4))


def create_call1_api_response(path_file: Path):
    """Create the Call 1 (analysis and questions) demo API response JSON."""
    if not OUTPUT_FROM_LLM_CURRENT_FILE.exists():
        print(f"Error: OUTPUT_FROM_LLM_CURRENT_FILE does not exist.")
        return

    LLM_response = json.loads(OUTPUT_FROM_LLM_CURRENT_FILE.read_text())
    api_response_dict = {
        "Fit": LLM_response["Fit"],
        "Gap_Map": LLM_response["Gap_Map"],
        "Questions": LLM_response["Questions"],
    }

    path_file.write_text(json.dumps(api_response_dict, indent=4))


def create_call2_api_response(path_file: Path):
    """Create the Call 2 (revised analysis and tailored resume) demo API response JSON."""
    if not OUTPUT_FROM_LLM_CURRENT_FILE.exists():
        print(f"Error: OUTPUT_FROM_LLM_CURRENT_FILE does not exist.")
        return

    LLM_response = json.loads(OUTPUT_FROM_LLM_CURRENT_FILE.read_text())
    api_response_dict = {
        "Fit": LLM_response["Fit"],
        "Gap_Map": LLM_response["Gap_Map"],
    }

    revised_resume = LLM_response["Tailored_Resume"]
    baseline_resume = RESUME_BASELINE_FILE.read_text()
    api_response_dict["Tailored_Resume"] = create_resume_diff(baseline_resume, revised_resume)

    path_file.write_text(json.dumps(api_response_dict, indent=4))


if __name__ == "__main__":
    print("Demo file maker")
    print("1. Create JSON input for LLM ")
    print("2. Create Call 1 API response (analysis and questions)")
    print("3. Create Call 2 API response (revised analysis and tailored resume)")
    print()
    choice = input("What do you want to do? ")

    match choice:
        case "1":
            create_prompt_json_input()
        case "2":
            create_call1_api_response(RESPONSE_REVIEW_DEMO_FILE)
        case "3":
            create_call2_api_response(RESPONSE_REVIEW_ADD_INFO_DEMO_FILE)
        case _:
            print("Invalid choice")


