# COVID19-Simulation

This repository contains the simulation code for the research paper. It simulates the spread of COVID-19 under various scenarios using LLM-driven agents.

## 🚀 Quick Start

### 1. Environment Setup

It is recommended to use Anaconda or Miniconda to manage dependencies.

```bash
# Create and activate environment (example)
conda create -n covid-sim python=3.9
conda activate covid-sim

# Install dependencies
pip install -r requirements.txt
```
*(Note: If requirements.txt is not present, please install necessary packages like `openai`, `numpy`, `pandas`, etc.)*

### 2. API Configuration

To run the simulation, you need to configure the LLM API keys.

1.  Copy the example configuration file:
    ```bash
    cp llm_config_example.py llm_config.py
    ```
2.  Edit `llm_config.py` and enter your API Key(s):
    ```python
    LLM_CONFIGS = [
        {
            "name": "Account_1",
            "api_key": "sk-YOUR_REAL_API_KEY_HERE",
            "base_url": "https://api.deepseek.com/v1", # Or other provider
            "model": "deepseek-chat",
            "proxy": None, # Set proxy if needed
        },
        # ... Add more accounts for higher concurrency
    ]
    ```
3.  Verify your configuration:
    ```bash
    python llm_config.py
    ```

### 3. Running Scenarios

The project includes several pre-configured scenarios:

*   **Baseline Scenario (No Intervention)**:
    ```bash
    python run_scenario_A_baseline.py
    ```

*   **Healthcare Intervention Scenario**:
    ```bash
    python run_scenario_B_health.py
    ```

*   **Remote Work Scenario**:
    ```bash
    python run_scenario_C_remote.py
    ```

## 📁 Project Structure

*   `covid_abs/`: Core simulation logic and agent definitions.
*   `tools/`: Utility scripts for logging, visualization, and data processing.
*   `llm_config.py`: (Ignored by Git) Local configuration for API keys.
*   `llm_config_example.py`: Template for API configuration.
*   `run_*.py`: Entry points for different simulation scenarios.

## ⚠️ Notes

*   **API Costs**: Running large-scale simulations may consume significant API tokens. Please monitor your usage.
*   **Proxy**: If you are in a region with restricted API access, please configure the `proxy` field in `llm_config.py`.

## License

[License Information]
