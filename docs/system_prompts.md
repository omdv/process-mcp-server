### Part 3: The n8n Workflow Configuration

Here is the "Secret Sauce" to make the Agent behave intelligently.

#### 1. The "ReAct" Agent Node
Use the **Advanced AI > AI Agent** node.
* **Model:** GPT-4o or Claude 3.5 Sonnet (needed for complex planning).
* **System Prompt:**
    > You are a Senior Process Optimization Engineer. Your goal is to maximize daily revenue.
    >
    > **Your Workflow:**
    > 1. **Plan:** Analyze the user's request. Identify missing data (e.g., "What is the price of oil?").
    > 2. **Search:** Use the 'Market_Scout' tool to find current prices for Crude Oil ($/bbl) and Natural Gas ($/MMBtu).
    > 3. **Reason:** Determine a strategy. (e.g., "If gas is cheap, I should minimize gas export and maximize liquid recovery.")
    > 4. **Simulate:** Use the 'Digital_Twin' tool. Run at least 3 distinct scenarios (e.g., change Separator Pressure to 20, 35, and 50 bar).
    > 5. **Synthesize:** Calculate revenue for each scenario:
    >    * *Revenue = (Oil_kg * Oil_Price) + (Gas_kg * Gas_Price)*
    > 6. **Recommend:** Output a formatted table of results and your final recommendation.

#### 2. Configuring the "Digital_Twin" Tool
In n8n, add a **Custom Tool** (or "Call HTTP Request" Tool).
* **Name:** `process_simulator`
* **Description:** "Simulates the production facility. Input: separator_pressure_bar (float). Returns: Oil and Gas flow rates."
* **URL:** `http://host.docker.internal:8000/simulate_process`
* **Body:** JSON
    ```json
    {
      "separator_pressure_bar": {{ $fromAI("pressure") }},
      "column_reflux_ratio": 1.0
    }
