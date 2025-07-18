import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys

# Project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)
# Now, import from core
from core.file_handler import format_credit_policy_excel

# ========================================================================
# USER CONFIGURATION
# ========================================================================
INPUT_FILE = r"D:\3. Slickbooks\2025 New Effort\Bookkeeping Tools\AR Tool\Demo_Company__Global__-_Receivable_Invoice_Detail.xlsx"
OUTPUT_FILE = r"D:\3. Slickbooks\2025 New Effort\Bookkeeping Tools\AR Tool\Credit Policy.xlsx"
CREDIT_POLICY = 30 # Credit policy in Days
WACC = 0.10 # Weighted Average Cost of Capital
DAYS_IN_A_YEAR = 360 # Days in a year for financial calculations
TOP_CLIENTS_CUTOFF = 0.25 # First 25% of clients by invoice amount are considered High Value
INTENSE_SCHEDULE = 'Reminders in -7, -1, +1, and then every 7 Days from Due Date'
NORMAL_SCHEDULE = 'Reminders in -1, and then every 15 Days from Due Date'
# ========================================================================


# Standalone main function for command line execution
def main():
    try:
        print("Starting invoice analysis...")
        
        # Step 1: Load and validate input file
        if not os.path.exists(INPUT_FILE):
            raise FileNotFoundError(f"Input file not found at: {INPUT_FILE}")
        
        print(f"Reading input file: {INPUT_FILE}")
        df = pd.read_excel(INPUT_FILE, skiprows=4)  # Skip first 4 rows
        
        # Step 2: Data cleaning
        print("Cleaning data...")
        df.columns = df.columns.str.strip().str.replace(' ', '_')
        
        # Filter for only Paid invoices
        if 'Status' in df.columns:
            df = df[df['Status'] == 'Paid']
            print(f"Filtered to {len(df)} paid invoices")
            
            # Add validation here
            if len(df) == 0:
                raise ValueError("No paid invoices found after filtering - check your Status column values")
        else:
            print("Warning: 'Status' column not found - skipping paid invoice filtering")

        # Date conversion
        date_columns = ['Invoice_Date', 'Due_Date', 'Last_Payment_Date']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce', format='%d %b %Y')
            else:
                print(f"Warning: Column '{col}' not found in dataframe")

        # Step 3: Filter and calculate metrics
        print("Calculating payment metrics...")
        df = df.dropna(subset=['Last_Payment_Date'])
        
        df['Is_Late'] = df['Last_Payment_Date'] > df['Due_Date']
        df['Days_Late'] = np.where(
            df['Is_Late'],
            (df['Last_Payment_Date'] - df['Due_Date']).dt.days,
            0
        )
        df['Late_Impact'] = np.where(
            df['Is_Late'],
            df['Days_Late'] * df['Invoice_Total'] * WACC * (1/DAYS_IN_A_YEAR),
            0
        )
        # Rounding to 2 decimal places
        df['Late_Impact'] = df['Late_Impact'].round(2)

        # Step 4: Group by contact
        print("Aggregating by contact...")
        contact_df = df.groupby('Contact').agg(
            Total_Invoice_Sum=('Invoice_Total', 'sum'),
            Late_Payment_Impact_Amount=('Late_Impact', 'sum'),
            Number_of_Delays=('Is_Late', 'sum')
        ).reset_index()

        # Step 5: High-value classification
        threshold = contact_df['Total_Invoice_Sum'].quantile(1 - TOP_CLIENTS_CUTOFF)
        contact_df['High_Value'] = np.where(
            contact_df['Total_Invoice_Sum'] >= threshold,
            'Yes',
            'No'
        )

        # Step 6: Impact analysis
        max_impact = contact_df['Late_Payment_Impact_Amount'].max()
        contact_df['Relative_Impact'] = contact_df['Late_Payment_Impact_Amount'].apply(
            lambda x: round((x / max_impact) * 100, 2) if max_impact > 0 else 0
        )
        # Late fee is applicable if there are more than 1 delay
        contact_df['Late_Fee_Applicable'] = contact_df['Number_of_Delays'] > 1

        # Step 7: Credit policy calculations
        contact_df['Reduction_in_Term_Days'] = contact_df.apply(
            lambda x: np.ceil((x['Relative_Impact'] * x['Number_of_Delays'] * (1/100)) / 5) * 5,
            axis=1
        )

        # Ensure reduction doesn't exceed original credit policy
        contact_df['Reduction_in_Term_Days'] = contact_df['Reduction_in_Term_Days'].clip(upper=CREDIT_POLICY)

        # Calculate revised credit policy
        contact_df['Revised_Credit_Policy'] = CREDIT_POLICY - contact_df['Reduction_in_Term_Days']

        # Ensure revised policy doesn't go below 0 days
        contact_df['Revised_Credit_Policy'] = contact_df['Revised_Credit_Policy'].clip(lower=0)
        
        # Step 8: Risk assessment
        contact_df['Risk'] = np.where(
            (contact_df['High_Value'] == 'No') & (contact_df['Number_of_Delays'] > 0),
            'High',
            'Normal'
        )
        contact_df['Schedule'] = np.where(
            (contact_df['Risk'] == 'High') & (contact_df['High_Value'] == 'No'), # Only non-High Value Contacts can be Intense
            INTENSE_SCHEDULE,
            NORMAL_SCHEDULE
        )

        # Final output columns - Can also Add 'Late_Payment_Impact_Amount', 'Relative_Impact', 
        output_columns = [
            'Contact', 'High_Value', 
            'Late_Fee_Applicable', 'Number_of_Delays', 'Reduction_in_Term_Days', 'Revised_Credit_Policy',
            'Risk', 'Schedule'
        ]
        contact_df = contact_df[output_columns]

        # Step 9: Save initial results (without formatting)
        temp_output = OUTPUT_FILE.replace('.xlsx', '_temp.xlsx')
        print(f"Saving initial results to: {temp_output}")
        contact_df.to_excel(temp_output, index=False)
        
        # Step 10: Apply formatting using the imported function
        print("Applying formatting...")
        format_credit_policy_excel(temp_output)
        
        # Replace the original file with the formatted one
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)
        os.rename(temp_output, OUTPUT_FILE)
        
        print("Processing completed successfully!")
        print(f"Formatted output file created at: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("Processing failed. Please check error message.")
        sys.exit(1)

if __name__ == "__main__":
    main()


# Processing function for Streamlit
def process_invoices(
    df,
    credit_terms,
    wacc,
    days_in_year,
    top_clients_cutoff,
    intense_schedule,
    normal_schedule
):
    """Process invoices dataframe and return results"""
    print("Cleaning data...")
    # Step 2: Data cleaning
    print("Cleaning data...")
    df.columns = df.columns.str.strip().str.replace(' ', '_')
    
    # Filter for only Paid invoices
    if 'Status' in df.columns:
        df = df[df['Status'] == 'Paid']
        print(f"Filtered to {len(df)} paid invoices")
        
        # Add validation here
        if len(df) == 0:
            raise ValueError("No paid invoices found after filtering - check your Status column values")
    else:
        print("Warning: 'Status' column not found - skipping paid invoice filtering")

    # Date conversion
    date_columns = ['Invoice_Date', 'Due_Date', 'Last_Payment_Date']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', format='%d %b %Y')
        else:
            print(f"Warning: Column '{col}' not found in dataframe")

    # Step 3: Filter and calculate metrics
    print("Calculating payment metrics...")
    df = df.dropna(subset=['Last_Payment_Date'])
    
    df['Is_Late'] = df['Last_Payment_Date'] > df['Due_Date']
    df['Days_Late'] = np.where(
        df['Is_Late'],
        (df['Last_Payment_Date'] - df['Due_Date']).dt.days,
        0
    )
    df['Late_Impact'] = np.where(
        df['Is_Late'],
        df['Days_Late'] * df['Invoice_Total'] * wacc * (1/days_in_year),
        0
    )
    # Rounding to 2 decimal places
    df['Late_Impact'] = df['Late_Impact'].round(2)

    # Step 4: Group by contact
    print("Aggregating by contact...")
    contact_df = df.groupby('Contact').agg(
        Total_Invoice_Sum=('Invoice_Total', 'sum'),
        Late_Payment_Impact_Amount=('Late_Impact', 'sum'),
        Number_of_Delays=('Is_Late', 'sum')
    ).reset_index()

    # Step 5: High-value classification
    threshold = contact_df['Total_Invoice_Sum'].quantile(1 - top_clients_cutoff)
    contact_df['High_Value'] = np.where(
        contact_df['Total_Invoice_Sum'] >= threshold,
        'Yes',
        'No'
    )

    # Step 6: Impact analysis
    max_impact = contact_df['Late_Payment_Impact_Amount'].max()
    contact_df['Relative_Impact'] = contact_df['Late_Payment_Impact_Amount'].apply(
        lambda x: round((x / max_impact) * 100, 2) if max_impact > 0 else 0
    )
    # Late fee is applicable if there are more than 1 delay
    contact_df['Late_Fee_Applicable'] = contact_df['Number_of_Delays'] > 1

    # Step 7: Credit terms calculations
    contact_df['Reduction_in_Term_Days'] = contact_df.apply(
        lambda x: np.ceil((x['Relative_Impact'] * x['Number_of_Delays'] * (1/100)) / 5) * 5,
        axis=1
    )

    # Ensure reduction doesn't exceed original credit terms
    contact_df['Reduction_in_Term_Days'] = contact_df['Reduction_in_Term_Days'].clip(upper=credit_terms)

    # Calculate revised credit terms
    contact_df['Revised_Credit_Terms'] = credit_terms - contact_df['Reduction_in_Term_Days']

    # Ensure revised terms doesn't go below 0 days
    contact_df['Revised_Credit_Terms'] = contact_df['Revised_Credit_Terms'].clip(lower=0)
    
    # Step 8: Risk assessment
    contact_df['Risk'] = np.where(
        (contact_df['High_Value'] == 'No') & (contact_df['Number_of_Delays'] > 0), # Only non-High Value Contacts can be High Risk
        'High',
        'Normal'
    )
    contact_df['Schedule'] = np.where(
        (contact_df['Risk'] == 'High') & (contact_df['High_Value'] == 'No'), # Only non-High Value Contacts can be Intense
        intense_schedule,
        normal_schedule
    )
    
    output_columns = [
        'Contact', 'High_Value', 
        'Late_Fee_Applicable', 'Number_of_Delays', 'Reduction_in_Term_Days', 'Revised_Credit_Terms',
        'Risk', 'Schedule'
    ]
    return contact_df[output_columns]

