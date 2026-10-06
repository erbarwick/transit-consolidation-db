CASE FOLDER STRUCTURE GUIDE
============================
When adding a new consolidation case, copy this entire '_case_template' folder 
and rename it to match the case name:
  e.g., "CON-017 Agency Name" or "Agency Name (SHORT)"

Expected files in this root folder:
-----------------------------------
1. *_ntd.xlsx
   - Monthly and annual NTD service metrics workbook.
   - Sheets expected:
     * 'UPT'   - Unlinked Passenger Trips (wide monthly table)
     * 'VRM'   - Vehicle Revenue Miles (wide monthly table)
     * 'VRH'   - Vehicle Revenue Hours (wide monthly table)
     * 'VOMS'  - Vehicles Operated in Maximum Service
     * 'Annual'- Annual NTD totals (optional)
     * 'INFO'  - Agency reporter IDs and notes (optional)

2. *_opexp.xlsx
   - Annual operating expenses workbook.
   - Sheet expected:
     * 'OpExp' - Rows by agency and columns by calendar year.

3. *_annual_financial.xlsx
   - Detailed financial metrics workbook from NTD annual forms.
   - Sheets expected:
     * 'Annual_Metrics' - Detailed metrics breakdown.
     * 'INFO'           - Metadata.

Subfolders:
-----------
- ACS/           : American Community Survey demographic files.
- LEHD/          : Longitudinal Employer-Household Dynamics (LODES & QWI).
- Combined Data/ : Human-curated master panels (if available).

Remember to also add a row to 'cases_metadata.csv' in the project root!
