# ==============================================================================
# build_db.R - R Runner for Transit Consolidation Database Pipeline
# ==============================================================================
# Use this script in RStudio or terminal to rebuild and validate transit.db.
#
# Usage in RStudio:
#   source("build_db.R")
#
# Usage in terminal:
#   Rscript build_db.R [path/to/data]
# ==============================================================================

# Default data directory (override via commandArgs or change here)
args <- commandArgs(trailingOnly = TRUE)
data_dir <- if (length(args) > 0) args[1] else "data"
db_path  <- "transit.db"

cat("================================================================\n")
cat(" Transit Consolidation Database Pipeline (R Runner)\n")
cat("================================================================\n\n")

# Detect Python interpreter (.venv or system)
venv_py <- if (.Platform$OS.type == "windows") {
  file.path(".venv", "Scripts", "python.exe")
} else {
  file.path(".venv", "bin", "python")
}

python_bin <- if (file.exists(venv_py)) {
  venv_py
} else {
  # Fallback to system python3 or python
  sys_py <- Sys.which("python3")
  if (sys_py == "") Sys.which("python") else sys_py
}

if (python_bin == "") {
  stop("Python executable not found. Please install Python or set up .venv.")
}

cat(sprintf("Using Python interpreter: %s\n", python_bin))
cat(sprintf("Source data directory:    %s\n", data_dir))
cat(sprintf("Target SQLite database:   %s\n\n", db_path))

# Check data directory exists
if (!dir.exists(data_dir)) {
  cat(sprintf("Notice: Data directory '%s' not found locally.\n", data_dir))
  cat("Please specify path: Rscript build_db.R path/to/data\n")
  cat("Or update 'data_dir' variable in build_db.R.\n\n")
} else {
  # Step 1: Run build_db.py
  cat("--> Step 1: Building transit.db...\n")
  build_cmd <- sprintf('"%s" build_db.py "%s" -o "%s" --force', python_bin, data_dir, db_path)
  status_build <- system(build_cmd)

  if (status_build != 0) {
    stop("Database build failed. Check error output above.")
  }

  # Step 2: Run coverage verification
  cat("\n--> Step 2: Running integrity verification (check_coverage.py)...\n")
  check_cmd <- sprintf('"%s" check_coverage.py "%s" "%s"', python_bin, db_path, data_dir)
  status_check <- system(check_cmd)

  cat("\n================================================================\n")
  cat(" Database build complete!\n")
  cat("================================================================\n\n")
}

# Example: Connecting to the database in R
cat("Tip: Connect directly to the database in R using:\n")
cat("  library(DBI)\n")
cat("  library(RSQLite)\n")
cat('  con <- dbConnect(RSQLite::SQLite(), "transit.db")\n')
cat('  df  <- dbGetQuery(con, "SELECT * FROM master_panel WHERE event_time BETWEEN -3 AND 3")\n')
cat("  dbDisconnect(con)\n\n")
