import streamlit as st
from components.agents_tab import render_agents_tab
from components.execution_tab import render_execution_tab
from components.tasks_tab import render_tasks_tab
from components.tools_tab import render_tools_tab
from utils.session import init_session_state


# set up streamlit page
st.set_page_config(
    page_title="AIBTC Crews",
    layout="wide",
)

# initialize session state
init_session_state()


# Display logo full width
st.image(
    "https://aibtc.dev/logos/aibtcdev-primary-logo-white-wide-1000px.png",
    use_column_width=True,
)

# initialize crew selections
available_crews = list(st.session_state.crew_mapping.keys())

# Display crew selection
crew_selection = st.selectbox("Select your crew:", available_crews)

# Main layout with tabs
tab1, tab2, tab3, tab4 = st.tabs(["Run 🏃", "Agents", "Tools", "Tasks"])

with tab1:
    render_execution_tab(crew_selection)

with tab2:
    render_agents_tab(crew_selection)

with tab3:
    render_tools_tab(crew_selection)

with tab4:
    render_tasks_tab(crew_selection)

# custom css styling
# at the end to prevent pushing content down

custom_styles = """
<style>
/* set max page width */
.main .block-container {
    max-width: 800px;
    padding-top: 2rem;
    padding-right: 1rem;
    padding-left: 1rem;
    padding-bottom: 3rem;
    margin: 0 auto;
}

/* hide navigation menu */
header[data-testid="stHeader"] {
    display: none;
    visibility: hidden;
}

/* custom tab styling */
button[data-baseweb="tab"] {
    margin: 0;
    width: 100%;
}
button[data-baseweb="tab"] > div[data-testid="stMarkdownContainer"] > p {
  font-size: 24px !important;
  font-weight: bold !important;
}

/* custom text input styling */
.stTextInput > div > div > input {
    background-color: #000000;
}

/* custom select box styling */

/* select box label */
.stSelectbox label > div > p {
    font-size: 1.5rem !important;
    font-weight: bold !important;
    color: white !important;
}

/* select box container */
.stSelectbox [data-baseweb="select"] {
    background-color: #000000 !important;
}

/* select box selected item when closed */
.stSelectbox [data-baseweb="select"] > div {
    background-color: #000000 !important;
    color: white !important;
    font-size: 1rem !important;
}

/* select box dropdown options container */
.stSelectbox [role="listbox"] {
    background-color: #000000 !important;
}
</style>
"""
st.write(custom_styles, unsafe_allow_html=True)
