import sys
import os
import streamlit as st
import requests
import json

# Add current directory to python path for local imports
sys.path.append(os.path.dirname(__file__))

# FastAPI URL (assuming it runs alongside or is mocked in the same file if just Streamlit)
# For this implementation, we will import the agent directly for a standalone Streamlit app
# so it's independently runnable without spinning up uvicorn.
from agent.agent import EngineeringAgent
from schemas.models import AskRequest, CurrentSituation

# ── Streamlit App ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Engineering RAG+LLM Agent", layout="wide")
st.title("Module 5: Engineering RAG + LLM Agent")

@st.cache_resource
def get_agent():
    return EngineeringAgent()

agent = get_agent()

# Layout
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Current Well / Situation")
    
    with st.form("situation_form"):
        well_id = st.text_input("Well ID", "15/9-F-9A")
        depth = st.number_input("Depth (m)", value=2830.0)
        torque = st.number_input("Torque (kNm)", value=18.0)
        wob = st.number_input("WOB (kN)", value=120.0)
        rop = st.number_input("ROP (m/hr)", value=8.0)
        flow = st.number_input("Flow (L/min)", value=420.0)
        pressure = st.number_input("Pressure (bar)", value=310.0)
        rpm = st.number_input("RPM", value=90.0)
        formation = st.text_input("Formation", "Sandstone")
        hazard = st.selectbox("Current Hazard Focus", ["none", "stuck_pipe", "mud_loss", "overpressure", "torque_spike", "cementing"], index=2)
        
        event_seq_str = st.text_input("Event Timeline (comma separated)", "NORMAL, TORQUE INCREASE, ROP DECREASE, FLOW ANOMALY")
        
        st.form_submit_button("Update Situation")

with col2:
    st.subheader("Chat with Engineering Agent")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("evidence"):
                with st.expander("View Evidence Used"):
                    for e in msg["evidence"]:
                        st.markdown(f"**{e.citation_id}**: {e.raw_text}")
    
    if prompt := st.chat_input("Ask a question about the current situation..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Prepare Request
        sit = CurrentSituation(
            well_id=well_id,
            depth=depth,
            torque=torque,
            wob=wob,
            rop=rop,
            flow=flow,
            pressure=pressure,
            rpm=rpm,
            formation=formation,
            hazard=hazard if hazard != "none" else None
        )
        seq = [s.strip() for s in event_seq_str.split(",")] if event_seq_str else []
        req = AskRequest(question=prompt, current_situation=sit, event_sequence=seq)
        
        with st.chat_message("assistant"):
            with st.spinner("Retrieving historical evidence and consulting LLM..."):
                try:
                    response = agent.ask(req)
                    st.markdown(response.answer)
                    
                    if response.evidence:
                        with st.expander("View Evidence Used"):
                            for e in response.evidence:
                                st.markdown(f"**{e.citation_id}**: {e.raw_text}")
                    
                    # Save to history
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response.answer,
                        "evidence": response.evidence
                    })
                    
                except Exception as e:
                    st.error(f"Error: {e}")

