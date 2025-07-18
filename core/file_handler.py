
def apply_credit_policy_styling(df):
    """Apply consistent styling to the credit policy DataFrame for Streamlit display"""
    
    def apply_row_styling(row):
        """Apply all styling rules to entire row based on conditions"""
        styles = [''] * len(row)
        
        # Priority 1: High Value rows (green background, dark green text)
        if 'High_Value' in row.index and row['High_Value'] == 'Yes':
            styles = ['background-color: #90EE90; color: #006400; font-weight: bold'] * len(row)
            return styles
        
        # Priority 2: High Risk rows (red background, dark red text)
        if 'Risk' in row.index and row['Risk'] == 'High':
            styles = ['background-color: #FFB6C1; color: #8B0000; font-weight: bold'] * len(row)
            return styles
        
        # Priority 3: Late Fee highlighting (for rows that aren't High Value or High Risk)
        if 'Late_Fee_Applicable' in row.index and row['Late_Fee_Applicable']:
            late_fee_index = row.index.get_loc('Late_Fee_Applicable')
            styles[late_fee_index] = 'color: red; font-weight: bold'
        
        return styles
    
    # Apply ONLY the row-level styling - no other styling methods
    styled_df = df.style.apply(apply_row_styling, axis=1)
    
    # Apply number formatting
    styled_df = styled_df.format({
        'Reduction_in_Term_Days': '{:.0f}',
        'Revised_Credit_Policy': '{:.0f}'
    })
    
    # Apply table properties
    styled_df = styled_df.set_properties(**{
        'text-align': 'center',
        'border': '1px solid black'
    })
    
    # Apply header styling
    styled_df = styled_df.set_table_styles([{
        'selector': 'th',
        'props': [('background-color', '#2c3e50'), 
                  ('color', 'white'),
                  ('font-weight', 'bold')]
    }])
    
    return styled_df