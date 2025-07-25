import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import tempfile
import io


print("\n=== SYS PATH ===")
for path in sys.path:
    print(path)

print("\n=== CURRENT DIR ===")
print("Current directory:", os.path.dirname(os.path.abspath(__file__)))
print("Project root:", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# --- FIXED PATH CALCULATION ---
# Get current directory of this script
current_dir = os.path.dirname(os.path.abspath(__file__))

# Calculate project root: go up 2 levels (tools/ap_report → tools → project_root)
project_root = os.path.dirname(os.path.dirname(current_dir))

print(f"Calculated project root: {project_root}")
print(f"Project root exists: {os.path.exists(project_root)}")
print(f"Core directory exists: {os.path.exists(os.path.join(project_root, 'core'))}")

# Add project root to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)  # Use insert(0, ...) to add at the beginning
    print(f"Added project root to sys.path: {project_root}")

print("\n=== UPDATED SYS PATH ===")
for i, path in enumerate(sys.path):
    print(f"{i}: {path}")

# Now import from core and local
try:
    from core.file_handler import apply_credit_policy_styling
    from ap_workflow import process_invoices
    print("✅ Successfully imported modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    st.error(f"Import error: {e}")
    st.stop()

st.set_page_config(layout="wide")
st.title("🧮 Accounts Receivable Analysis Tool")

# Configuration sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    credit_terms = st.number_input("Credit Terms (Days)", value=30, min_value=0)
    top_clients_cutoff = st.slider("Top Clients Cutoff (%)", 0, 100, 25, step=5, key="top_clients_cutoff_slider") / 100.0
    
    st.markdown("---")
    # Advanced Configuration Section
    with st.expander("🔧 Advanced Configuration", expanded=False):
        wacc = st.number_input("WACC (Your cost of raising funds in decimals)", value=0.10, step=0.01, min_value=0.0, max_value=1.0)
        days_in_year = st.number_input("Days in a Year", value=360, min_value=1)
        st.markdown("---")
        st.markdown("**Reminder Schedules**")
        intense_schedule = st.text_input("Intense Schedule", 
                                        value='Intense: Reminders in -7, -1, +1, and then every 7 Days from Due Date')
        normal_schedule = st.text_input("Normal Schedule", 
                                       value='Normal: Reminders in -1, and then every 15 Days from Due Date')

# --- 1. TITLE ---
st.markdown(
    "<h2 style='font-size: 2em; margin-bottom: 0;'>📤 Upload Receivable Invoice Detail (Excel)</h2>",
    unsafe_allow_html=True,
)

# --- 2. XERO SUB-TITLE & 3-STEP INSTRUCTIONS ---
st.markdown("#### For Xero Users")
st.markdown(
    """
1.  In Xero → **Accounting → Reports → All Reports**.  
2.  Search for **“Receivable Invoice Detail”** → choose a date range → **Export → Excel**.  
3.  Make sure the exported file contains the columns: **Contact, Invoice Date, Due Date, Last Payment Date, Status, Invoice Total**.
"""
)

uploaded_file = st.file_uploader(" ", type=["xlsx"])

# Extra space before the expander
st.markdown("<br>", unsafe_allow_html=True)

# --- 3. ACCORDION FOR NON-XERO USERS ---
with st.expander("🔽 Don't have Xero? Follow the instructions below", expanded=False):
    st.markdown("#### For Non-Xero Users")
    st.markdown(
        """
1.  Export your invoice ledger from your accounting software as **.xlsx**.  
2.  Ensure the sheet includes: **Contact, Invoice_Date, Due_Date, Last_Payment_Date, Status, Invoice_Total**.  
3.  Rename any columns that differ so they exactly match the names above (case-insensitive, underscores for spaces).
4. Alternatively, you can download the template below and fill it out with your data.
"""
    )

    # ---------- TEMPLATE DOWNLOAD ----------
    st.write("")  # tiny spacer
    template = pd.DataFrame(
        columns=[
            "Contact",
            "Invoice_Date",
            "Due_Date",
            "Last_Payment_Date",
            "Status",
            "Invoice_Total",
        ]
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        template.to_excel(writer, index=False, sheet_name="Template")
    buffer.seek(0)

    st.download_button(
        label="📥 Download blank template (Excel)",
        data=buffer,
        file_name="non_xero_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

if uploaded_file:
    try:
        # Read input file
        df = pd.read_excel(uploaded_file, skiprows=4)
        
        with st.spinner("🔍 Analyzing data..."):
            # Process with user configurations
            result = process_invoices(
                df=df,
                credit_terms=credit_terms,
                wacc=wacc,
                days_in_year=days_in_year,
                top_clients_cutoff=top_clients_cutoff,
                intense_schedule=intense_schedule,
                normal_schedule=normal_schedule
            )
        
        st.success("✅ Analysis Complete!")
        
        # Apply styling
        with st.spinner("🎨 Formatting results..."):
            styled_result = apply_credit_policy_styling(result)
        
        # Display styled results
        st.subheader("Credit Policy Analysis")
        st.dataframe(styled_result, use_container_width=True)
        
        # Download options
        st.subheader("📥 Download Results")
        
        col1, col2 = st.columns(2)
        with col1:
            # CSV download
            csv = result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download as CSV",
                data=csv,
                file_name="credit_policy_analysis.csv",
                mime="text/csv",
                help="Download as CSV file"
            )
        
        with col2:
            # Excel download
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                    result.to_excel(tmp.name, index=False)
                    tmp.seek(0)  # Go back to beginning of file
                    excel_bytes = tmp.read()
                    
                st.download_button(
                    label="Download as Excel",
                    data=excel_bytes,
                    file_name="credit_policy_analysis.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download as Excel file"
                )
            finally:
                # Ensure temp file is always cleaned up
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)

    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.stop()