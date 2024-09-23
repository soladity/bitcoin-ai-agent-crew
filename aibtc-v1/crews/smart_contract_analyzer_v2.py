import inspect
import streamlit as st
from crewai import Agent, Task
from crewai_tools import tool, Tool
from utils.crews import AIBTC_Crew, display_token_usage
from utils.scripts import BunScriptRunner, get_timestamp


taskListFormat = """
## {description of analysis}

- {item 1}: {description of item 1}
- {item 2}: {description of item 2}
- {item 3}: {description of item 3}
"""

taskReportFormat = """
## Summary of Findings

{short summary of findings}

## Detailed Analysis

{detailed analysis of findings}

## References to Specific Code Segments

{references to specific code segments}
"""

analysisFormat = """
# Contract analysis for {contract_name}

## General Concept

{general concept of the contract}

## RED Functions

{list of RED functions}

## ORANGE Functions

{list of ORANGE functions}

## YELLOW Functions

{list of YELLOW functions}

## GREEN Functions

{list of GREEN functions}

## Missing Functions

{list of missing functions}
"""

reviewFormat = """
## Complex Logic Review

{review of complex logic}

## Fee Validation

{validation of fees and token transfers}

## Input Validation

{validation of user-provided inputs}

## Pause and Resume Mechanisms

{analysis of pause and resume mechanisms}

## Final Analysis

{final analysis of the contract}
"""


class SmartContractAnalyzerV2(AIBTC_Crew):
    def __init__(self):
        super().__init__("Smart Contract Analyzer V2")

    def setup_agents(self, llm):
        # contract retrieval agent
        contract_retrieval_agent = Agent(
            role="Contract Retrieval Expert",
            goal="To retrieve the contract code for analysis.",
            backstory=(
                "You are a contract retrieval agent with expertise in fetching contract code and functions for analysis.",
                "Your role is crucial in providing the necessary data for the audit team to perform their tasks effectively.",
                "You always use the fully qualified contract name (ADDRESS.CONTRACT_NAME) to ensure accurate retrieval.",
            ),
            tools=[AgentTools.get_contract_source_code],
            verbose=True,
            allow_delegation=False,
            llm=llm,
        )
        self.add_agent(contract_retrieval_agent)

        # contract analysis agent
        contract_analysis_agent = Agent(
            role="Contract Analysis Expert",
            goal="To analyze the contract code and functions to understand the purpose and function of a smart contract.",
            backstory=(
                "You are a contract analysis agent with expertise in dissecting smart contract codebases and identifying potential risks.",
                "Your role is critical in assessing the security and functionality of the contracts under audit.",
            ),
            tools=[],
            verbose=True,
            allow_delegation=False,
            llm=llm,
        )
        self.add_agent(contract_analysis_agent)

        # contract report writer
        contract_report_writer = Agent(
            role="Contract Report Writer",
            goal="To compile the findings from the contract analysis into a comprehensive audit report.",
            backstory=(
                "You are a contract report writer with experience in summarizing complex technical information into clear and concise reports.",
                "Your role is essential in documenting the audit results and recommendations for the contract developers.",
            ),
            tools=[],
            verbose=True,
            allow_delegation=False,
            llm=llm,
        )

    def setup_tasks(self):
        #
        # STAGE 1: PREP THE INFORMATION
        #

        # get the contract code
        get_contract_code = Task(
            description="Retrieve the contract code for analysis.",
            expected_output="The contract code for analysis in raw format with no modifications or additional output.",
            agent=self.agents[0],  # contract retrieval agent
            context=[],
        )
        self.add_task(get_contract_code)

        # what is the general purpose of the contract
        general_concept = Task(
            description="Given the contract code, what is the general concept of the contract?",
            expected_output=(
                "A summary of the contract's purpose and functionality.",
                "This should follow the strict format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(general_concept)

        # check for functions that use traits
        trait_functions = Task(
            description="Identify functions that take traits as arguments and note what each function does.",
            expected_output=(
                "A list of functions that take traits as arguments with descriptions of what each function does.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(trait_functions)

        # check for functions that use as-contract
        as_contract_functions = Task(
            description="Identify all instances where `as-contract` is used with `contract-call?` and note the functions involved.",
            expected_output=(
                "Documentation of all instances where `as-contract` is used with `contract-call?`, including function names.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(as_contract_functions)

        # check for green functions
        green_functions = Task(
            description=(
                "Help identify and categorize functions that would be considered GREEN in terms of risk.",
                "GREEN - harmless, do not participate in anything super important, in most cases it will be just a read-only function that returns value stored on-chain",
            ),
            expected_output=(
                "A list of functions categorized as GREEN based on their risk levels.",
                "This should follow the strict Markdown format defined below:",
                taskListFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(green_functions)

        # check for yellow functions
        yellow_functions = Task(
            description=(
                "Help identify and categorize functions that would be considered YELLOW in terms of risk.",
                "YELLOW - can change value of variable of map entry, but they are not used to anything critical. In most cases it will functions that can modify meta-data stored on chain.",
            ),
            expected_output=(
                "A list of functions categorized as YELLOW based on their risk levels.",
                "This should follow the strict Markdown format defined below:",
                taskListFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )

        # check for orange functions
        orange_functions = Task(
            description=(
                "Help identify and categorize functions that would be considered ORANGE in terms of risk.",
                "ORANGE - functions without side-effects used by functions with side-effects and functions with side-effects that can alter contract behavior but not in a way that can lead to theft, funds loss or contract lock.",
            ),
            expected_output=(
                "A list of functions categorized as ORANGE based on their risk levels.",
                "This should follow the strict Markdown format defined below:",
                taskListFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(orange_functions)

        # check for missing functions
        missing_functions = Task(
            description="Help identify and categorize functions that are missing from the GREEN, YELLOW, and ORANGE categories, if any.",
            expected_output=(
                "A list of functions that are missing from the GREEN, YELLOW, and ORANGE categories.",
                "This should follow the strict Markdown format defined below:",
                taskListFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[
                get_contract_code,
                green_functions,
                yellow_functions,
                orange_functions,
            ],
        )
        self.add_task(missing_functions)

        #
        # STAGE 2 - ANALYZE THE CATEGORIES
        #

        analyze_green_contracts = Task(
            description=(
                "Analyze the GREEN functions for correctness and consider the following:",
                "Functions that are read-only should not have any side-effects.",
                "Example: A function that returns the balance of an account should not modify the balance.",
            ),
            expected_output=(
                "An analysis of GREEN functions with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code, green_functions],
        )
        self.add_task(analyze_green_contracts)

        analyze_yellow_contracts = Task(
            description=(
                "Analyze the YELLOW functions for proper authorization and access control and consider the following:",
                "Functions that can be called by people who shouldn't be able to call them must be fixed.",
                "Example: Function that allows to change token URI can be executed successfully by anyone, but only admin should be allowed to do that.",
                "Functions secured using `tx-sender` or `contract-caller` value must be triple checked. If values they change aren't critical (used to secure other functions) they are OK.",
            ),
            expected_output=(
                "An analysis of YELLOW functions with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code, yellow_functions],
        )
        self.add_task(analyze_yellow_contracts)

        analyze_orange_contracts = Task(
            description=(
                "Analyze the ORANGE functions for for proper authorization, access control and security vulnerabilities, and consider the following:",
                "Functions with side-effects (minting, transferring, burning STX/FT/NFT) must be secured properly.",
                "Who can perform each action should be documented and verified as part of the report.",
                "Functions secured using `tx-sender` or `contract-caller` value must be triple checked.",
            ),
            expected_output=(
                "An analysis of ORANGE functions with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code, orange_functions],
        )
        self.add_task(analyze_orange_contracts)

        analyze_red_contracts = Task(
            description=(
                "Analyze the provided functions as RED functions for critical security issues and consider the following:",
                "Functions that can lead to theft, funds loss or contract lock must be secured properly.",
                "Who can perform each action should be documented and verified as part of the report.",
                "Functions secured using `tx-sender` or `contract-caller` value must be triple checked.",
            ),
            expected_output=(
                "An analysis of RED functions with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code, trait_functions, as_contract_functions],
        )
        self.add_task(analyze_red_contracts)

        #
        # STAGE 3 - ANALYZE COMMON ISSUES
        #

        review_complex_logic = Task(
            description=(
                "Review complex logic identified in previous stages for potential flaws and consider the following:",
                "Complex logic should be broken down into smaller, more manageable parts.",
                "Edge cases and potential vulnerabilities should be identified and addressed.",
            ),
            expected_output=(
                "An analysis of complex logic segments with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(review_complex_logic)

        review_fee_validation = Task(
            description=(
                "Review the validation of fees and token transfers for potential issues and consider the following:",
                "Fees and token transfers should be validated to prevent zero or unintended values.",
                "Edge cases and potential vulnerabilities should be identified and addressed.",
            ),
            expected_output=(
                "An analysis of fee validation and token transfer logic with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(review_fee_validation)

        review_input_validation = Task(
            description=(
                "Review the validation of user-provided inputs for potential vulnerabilities and consider the following:",
                "User inputs should be properly validated to prevent vulnerabilities.",
                "Edge cases and potential vulnerabilities should be identified and addressed.",
            ),
            expected_output=(
                "An analysis of input validation logic with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(review_input_validation)

        review_pause_resume = Task(
            description=(
                "Review the mechanisms for pausing and resuming contract operations for potential issues and consider the following:",
                "Pause functionality should include a way to resume to prevent permanent contract lockout.",
                "Edge cases and potential vulnerabilities should be identified and addressed.",
            ),
            expected_output=(
                "An analysis of pause and resume mechanisms with any reported issues and recommended fixes.",
                "Do not include any contract code, only the analysis and recommendations.",
                "This should follow the strict Markdown format defined below:",
                taskReportFormat,
            ),
            agent=self.agents[1],  # contract analysis agent
            context=[get_contract_code],
        )
        self.add_task(review_pause_resume)

        #
        # STAGE 4 - ASSEMBLE THE FINAL ANALYSIS
        #

        # compile analysis information
        compile_analysis = Task(
            description="Compile the findings from the contract analysis into a comprehensive audit report.",
            expected_output=(
                "A detailed audit report summarizing the findings from the contract analysis.",
                "This should follow the strict Markdown format defined below:",
                analysisFormat,
            ),
            agent=self.agents[2],  # contract report writer
            context=[
                general_concept,
                green_functions,
                yellow_functions,
                orange_functions,
                missing_functions,
                analyze_green_contracts,
                analyze_yellow_contracts,
                analyze_orange_contracts,
                analyze_red_contracts,
            ],
        )
        self.add_task(compile_analysis)

        # compile review information
        compile_review = Task(
            description="Compile the findings from the contract review into a comprehensive audit report.",
            expected_output=(
                "A detailed audit report summarizing the findings from the contract review.",
                "This should follow the strict Markdown format defined below:",
                reviewFormat,
            ),
            agent=self.agents[2],  # contract report writer
            context=[
                review_complex_logic,
                review_fee_validation,
                review_input_validation,
                review_pause_resume,
            ],
        )
        self.add_task(compile_review)

        # final report
        final_report = Task(
            description="Finalize the audit report with all the compiled information.",
            expected_output=(
                "The finalized audit report ready for delivery to the contract developers.",
                "This should be a well-structured and detailed report that includes all the findings and recommendations.",
                "The report format should match the provided template.",
                analysisFormat,
                reviewFormat,
                "## Additional Comments",
            ),
            agent=self.agents[2],  # contract report writer
            context=[compile_analysis, compile_review],
        )
        self.add_task(final_report)

    @staticmethod
    def get_task_inputs():
        return ["contract_code"]

    @classmethod
    def get_all_tools(cls):
        return AgentTools.get_all_tools()

    def render_crew(self):
        st.subheader("Smart Contract Analyzer V2 🧠")
        st.markdown("Analyze Stacks smart contracts with enhanced AI capabilities.")

        with st.form("analysis_form"):
            contract_identifier = st.text_input(
                "Contract Identifier",
                help="Enter the full contract identifier including address and name.",
                placeholder="e.g. SP000000000000000000002Q6VF78.pox",
            )
            submitted = st.form_submit_button("Analyze Contract")

        if submitted and contract_identifier:
            # Validate contract_identifier
            parsed_address, parsed_name = parse_contract_identifier(contract_identifier)

            if parsed_address and parsed_name:
                contract_address = parsed_address
                contract_name = parsed_name
            else:
                st.error(
                    "Invalid contract identifier format. Please use 'address.name' format."
                )
                st.stop()

            if not contract_address or not contract_name:
                st.error(
                    "Both contract address and name are required. Please use 'address.name' format."
                )
                st.stop()

            st.subheader("Analysis Progress")
            try:
                # create containers for real-time updates
                st.write("Step Progress:")
                st.session_state.crew_step_container = st.empty()
                st.write("Task Progress:")
                st.session_state.crew_task_container = st.empty()

                # reset callback lists
                st.session_state.crew_step_callback = []
                st.session_state.crew_task_callback = []

                # get LLM from session state
                llm = st.session_state.llm

                # Create an instance of SmartContractAnalyzerV2
                smart_contract_analyzer_crew_class = SmartContractAnalyzerV2()
                smart_contract_analyzer_crew_class.setup_agents(llm)
                smart_contract_analyzer_crew_class.setup_tasks()
                smart_contract_analyzer_crew = (
                    smart_contract_analyzer_crew_class.create_crew()
                )

                # Provide the contract_name as input to the crew
                inputs = {"contract_name": contract_identifier}

                with st.spinner("Analyzing..."):
                    result = smart_contract_analyzer_crew.kickoff(inputs=inputs)

                st.success("Analysis complete!")

                display_token_usage(result.token_usage)

                st.subheader("Analysis Results")

                result_str = str(result.raw)
                st.markdown(result_str)

                timestamp = get_timestamp()

                st.download_button(
                    label="Download Analysis Report (Text)",
                    data=result_str,
                    file_name=f"{timestamp}_smart_contract_analysis.txt",
                    mime="text/plain",
                )
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.error("Please check your inputs and try again.")
        else:
            st.write(
                "Enter Contract Address and Contract Name, then click 'Analyze Contract' to see results."
            )


#########################
# Agent Tools
#########################


class AgentTools:

    @staticmethod
    @tool("Get contract source code")
    def get_contract_source_code(contract_name: str):
        """Get the source code for a given contract name. The fully qualified name with ADDRESS.CONTRACT_NAME must be provided as the argument."""
        # see if the contract name is in the format { contract_name: value }
        if isinstance(contract_name, dict) and "contract_name" in contract_name:
            contract_name = contract_name["contract_name"]
        return BunScriptRunner.bun_run(
            "stacks-contracts", "get-contract-source-code.ts", contract_name
        )

    @classmethod
    def get_all_tools(cls):
        members = inspect.getmembers(cls)
        tools = [
            member
            for name, member in members
            if isinstance(member, Tool)
            or (hasattr(member, "__wrapped__") and isinstance(member.__wrapped__, Tool))
        ]
        return tools


#########################
# Helper Functions
#########################


def parse_contract_identifier(identifier):
    parts = identifier.split(".")
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, None
