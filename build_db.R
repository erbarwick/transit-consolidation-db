# ==============================================================================
# build_db.R - Self-Bootstrapping R Runner for Transit Consolidation Database
# ==============================================================================
# Use this script in RStudio or the terminal to build and validate transit.db.
#
# This script is completely self-bootstrapping:
#   1. Detects or creates a Python virtual environment (.venv) automatically.
#   2. Installs required dependencies (pandas, openpyxl, etc.) if missing.
#   3. Locates source data (data/, data_extracted/data/, or data.zip).
#   4. Rebuilds transit.db and exports web assets (docs/data/).
#   5. Runs comprehensive coverage and integrity checks.
#
# Usage in RStudio:
#   source("build_db.R")
#
# Usage in Terminal:
#   Rscript build_db.R [path/to/data]
# ==============================================================================

cat("================================================================\n")
cat(" Transit Consolidation Database Pipeline (R Runner)\n")
cat("================================================================\n\n")

is_windows <- .Platform$OS.type == "windows"
venv_dir   <- ".venv"
venv_py    <- if (is_windows) {
  file.path(venv_dir, "Scripts", "python.exe")
} else {
  file.path(venv_dir, "bin", "python")
}

# ------------------------------------------------------------------------------
# 1. Ensure Python Virtual Environment (.venv) Exists
# ------------------------------------------------------------------------------
if (!file.exists(venv_py)) {
  cat("[Setup] Virtual environment (.venv) not found. Initializing...\n")

  # Search for system Python
  candidates <- if (is_windows) c("py", "python", "python3") else c("python3", "python")
  sys_py <- ""
  for (cmd in candidates) {
    found <- Sys.which(cmd)
    if (found != "") {
      # Verify executable runs
      test_code <- system(sprintf('"%s" --version', found), ignore.stdout = TRUE, ignore.stderr = TRUE)
      if (test_code == 0) {
        sys_py <- found
        break
      }
    }
  }

  if (sys_py == "") {
    stop(
      "\n[ERROR] Python was not detected on your system.\n",
      "Please install Python 3 (from https://www.python.org or via Homebrew/winget),\n",
      "then re-run source('build_db.R')."
    )
  }

  cat(sprintf("[Setup] Using system Python: %s\n", sys_py))
  cat("[Setup] Creating virtual environment in .venv ...\n")
  create_status <- system(sprintf('"%s" -m venv "%s"', sys_py, venv_dir))

  if (create_status != 0 || !file.exists(venv_py)) {
    stop("\n[ERROR] Failed to create virtual environment in .venv. Check folder permissions.")
  }
  cat("[Setup] Virtual environment created successfully.\n\n")
}

python_bin <- file.path(getwd(), venv_py)
cat(sprintf("Python interpreter: %s\n", python_bin))

# ------------------------------------------------------------------------------
# 2. Check and Install Required Python Packages
# ------------------------------------------------------------------------------
cat("[Setup] Verifying required Python packages (pandas, openpyxl)...\n")
pkg_check <- system(
  sprintf('"%s" -c "import pandas, openpyxl"', python_bin),
  ignore.stdout = TRUE,
  ignore.stderr = TRUE
)

if (pkg_check != 0) {
  cat("[Setup] Installing dependencies from requirements.txt...\n")
  install_status <- system(sprintf('"%s" -m pip install -r requirements.txt', python_bin))
  if (install_status != 0) {
    stop("\n[ERROR] Failed to install Python dependencies. Please check network connectivity.")
  }
  cat("[Setup] Dependencies installed successfully.\n\n")
} else {
  cat("[Setup] All required Python dependencies are present.\n\n")
}

# Optional: integrate with R reticulate if loaded
if (requireNamespace("reticulate", quietly = TRUE)) {
  try(reticulate::use_virtualenv(venv_dir, required = FALSE), silent = TRUE)
}

# ------------------------------------------------------------------------------
# 3. Locate Source Data Directory
# ------------------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) > 0) {
  args[1]
} else if (dir.exists("data")) {
  "data"
} else if (dir.exists("data_extracted/data")) {
  "data_extracted/data"
} else if (file.exists("data.zip")) {
  cat("[Data] 'data/' folder not found, but 'data.zip' is present.\n")
  cat("[Data] Extracting data archive...\n")
  utils::unzip("data.zip")
  if (dir.exists("data")) "data" else if (dir.exists("data_extracted/data")) "data_extracted/data" else "data"
} else {
  "data"
}

db_path <- "transit.db"
docs_dir <- "docs/data"

cat(sprintf("Source data directory: %s\n", data_dir))
cat(sprintf("Target SQLite database: %s\n\n", db_path))

if (!dir.exists(data_dir)) {
  cat(sprintf("[WARNING] Data directory '%s' was not found.\n", data_dir))
  cat("To build the database, please either:\n")
  cat("  1. Place the raw case folders in a 'data/' directory,\n")
  cat("  2. Provide 'data.zip' in the root project folder, or\n")
  cat("  3. Run via command line: Rscript build_db.R path/to/your/data\n\n")
  stop("Missing source data directory.")
}

# ------------------------------------------------------------------------------
# 4. Build Database & Web Assets
# ------------------------------------------------------------------------------
cat("--> Step 1: Building transit.db and web viewer assets...\n")
build_cmd <- sprintf('"%s" build_db.py "%s" -o "%s" --force --export-docs "%s"',
                     python_bin, data_dir, db_path, docs_dir)
status_build <- system(build_cmd)

if (status_build != 0) {
  stop("\n[ERROR] Database build failed. Please review error output above.")
}

# ------------------------------------------------------------------------------
# 5. Run Verification & Integrity Checks
# ------------------------------------------------------------------------------
cat("\n--> Step 2: Running coverage & integrity checks (check_coverage.py)...\n")
check_cmd <- sprintf('"%s" check_coverage.py "%s" "%s"', python_bin, db_path, data_dir)
status_check <- system(check_cmd)

if (status_check != 0) {
  warning("\n[WARNING] Some coverage or validation checks reported issues. See report above.")
}

cat("\n================================================================\n")
cat(" Database build complete!\n")
cat("================================================================\n\n")

# ------------------------------------------------------------------------------
# Quickstart Guide for R Users
# ------------------------------------------------------------------------------
cat("To query the database in R:\n")
cat("  library(DBI)\n")
cat("  library(RSQLite)\n")
cat('  con <- dbConnect(RSQLite::SQLite(), "transit.db")\n')
cat('  df  <- dbGetQuery(con, "SELECT case_id, year, event_time, phase, ntd_upt_cal_all FROM master_panel")\n')
cat("  dbDisconnect(con)\n")
cat("  head(df)\n\n")
