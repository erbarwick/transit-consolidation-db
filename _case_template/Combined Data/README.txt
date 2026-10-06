COMBINED DATA & HUMAN MASTER PANELS
====================================
If the research team created a manual annual master panel for this case, 
place the workbook here:

1. *master_panel*.xlsx (or .xlsm)
   - Human-verified time-series panel created during case analysis.
   - Sheets loaded:
     * 'Panel_Annual'      - Stacked into manual_master_panel (is_human_verified = 1).
     * 'Panel_Monthly_NTD' - Stacked into panel_monthly_ntd.

2. panel_annual_*.csv (optional)
   - CSV export of the annual master panel.

Note: If no human master panel exists for a new case, the pipeline will automatically 
synthesize all master_panel indicators directly from the raw NTD, opexp, LODES, QWI, 
and ACS tables!
