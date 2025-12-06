#!/bin/bash
# Server experiment runner with comprehensive logging
# Usage: ./run_experiment_with_logging.sh

# Create timestamp for this run
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="output/graph_batch"
mkdir -p "$LOG_DIR"

# Define log files
CONSOLE_LOG="$LOG_DIR/console_output_$TIMESTAMP.log"
ERROR_LOG="$LOG_DIR/error_output_$TIMESTAMP.log"
COMBINED_LOG="$LOG_DIR/combined_output_$TIMESTAMP.log"

echo "🚀 Starting experiment with comprehensive logging..."
echo "📝 Console output: $CONSOLE_LOG"
echo "❌ Error output: $ERROR_LOG" 
echo "📋 Combined output: $COMBINED_LOG"
echo ""

# Run the experiment with output redirection
python run_graph_llm_batch.py 2>&1 | tee "$COMBINED_LOG"

# Also create separate streams
python run_graph_llm_batch.py > "$CONSOLE_LOG" 2> "$ERROR_LOG"

echo ""
echo "✅ Experiment completed!"
echo "📁 All logs saved in: $LOG_DIR"
echo ""
echo "📋 Next steps:"
echo "  1. python sort_debug_logs.py"
echo "  2. python analyze_economic_debug.py"
echo "  3. Review logs: $COMBINED_LOG"
