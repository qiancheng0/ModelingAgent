MODELING_FACTOR_SYS = """You are an AI assistant designed to extract all **real-world grounding variables** and **factors** from a mathematical modeling implementation. Your goal is to identify all the inputs and parameters from the model that are necessary to implement, simulate, or verify the model in the real world.

## **Task**
Your task is to read a complete mathematical modeling implementation and extract all relevant real-world variables that the model depends on. You must:
1. **Identify Key Variables and Parameters**
   - These are quantities, constants, or functions that the model uses and that must be grounded in real-world data.
   - Only include variables already appearing in the modeling implementation. Do not invent new ones.
   - Only include the initial variables or constrints that are necessary to find data for. Do not include any derived intermediate variables or results.
2. **Explain Relevance and Real-World Link**
   - For each variable, explain **why** it is necessary to the model and what **real-world quantity** it corresponds to.
3. **Suggest Data Acquisition Strategy**
   - Provide a suggestion on how to **obtain real-world data** for that variable. Remember that you can only use web search tools and python code to find data. Do not suggest methods that is impractical. You can suggest using datasets, APIs, or specific search terms for web or article searches.

Your output should be a structured JSON list. Each element must be a dictionary with the following keys:
- `variable`: The description of the variable, a piece of explanation of what it is and what it represents
- `reason`: Why this variable is critical in the model, also with hints on what data we should find for this variable 
- `real_world_acquisition`: How to obtain real-world data or measurements for this variable
After the json output, please provide a brief explanation that, if you have got the data for all the variables, how you would implement the model and achieve the objective step by step.

---

## **Demonstration Example**

### **Modeling Objective and Guidlines:**
```json
{{
  "objective": "Develop a mathematical model that predicts a cyclist’s power output limits and endurance capacity based on physiological constraints.",
  "analysis": "The model should establish a relationship between power output and endurance time by accounting for both aerobic and anaerobic energy systems. It should define a critical power threshold that separates sustainable effort from anaerobic exertion, where energy is drawn from a finite anaerobic work capacity (AWC). The model must also incorporate a mechanism to describe energy depletion during high-intensity efforts and the subsequent recovery process when power output falls below the critical threshold.",
  "modeling_approaches": [
    {{
      "approach": "Energy-Based Power Duration Model",
      "application": "This model should quantify the rate at which anaerobic energy is consumed during high-power output and replenished during recovery. It must introduce a function that describes how long a cyclist can sustain a given power level based on the initial anaerobic reserves and their depletion rate. The model should also account for diminishing power capabilities as anaerobic energy decreases, ensuring a realistic progression of fatigue. Once developed, this framework can be used to generate power-duration curves, classify different rider profiles, and optimize pacing strategies for endurance performance."
    }}
  ]
}}
```

### **Modeling Implementation:**
```markdown
Considering the type of energy consumption, the body has two working states: aerobic exercise and anaerobic exercise. During aerobic exercise, the body expends energy from ATP produced by the aerobic system, the glycogen-lactic acid system, and the phosphorus system. Although aerobic breathing can continuously generate energy during exercise, its power is limited. When the required power exceeds the power limit of aerobic exercise, which is defined as the critical power \\( P_c \\), the body will expend energy from anaerobic energy sources. However, there is limit on the total amount of anaerobic energy that the body can utilize while continuously working above the critical power. The amount of energy used to measure the endurance capacity is called Anaerobic Work Capacity(AWC).

Aerobic exercise can last indefinitely, as long as the power output is below the critical power. Nevertheless anaerobic exercise can endure only a limited time and then enters the recovery phase when the rider works below the critical power to regain enough anaerobic energy. Therefore, we divide a rider's movement phase into the recovery phase(aerobic exercise) and working phase(anaerobic exercise), and conduct the following analysis on this basis.

We define \\( P \\) as the instantaneous power and \\( w \\) as the anaerobic energy. During the working phase, the variation rate of anaerobic energy \\( \\frac{{dw}}{{dt}} \\) is the difference between the critical power and the instantaneous power:
\\[
\\frac{{dw}}{{dt}} = P_c - P
\\]

According to the work of Morton,R.H. and Billat,L.V.[13], during the recovery phase, this relation is still effective, but the value of \\( \\frac{{dw}}{{dt}} \\) is positive.

Now we try to determine a power curve that shows the rider's ability to maintain certain level of power output continuously by giving the P-T function, where P is the given power and T is the time it can last.

Consider a process with a constant power of \\( P \\). The rate of energy consumption in anaerobic respiration is the difference between instantaneous power and critical power:
\\[
w(t) = w(0) - (P - P_c)t
\\]

Assume that rider can make full use of the remaining \\( AWC \\), When \\( t = T \\), \\( w(T) = 0 \\) so we can obtain the equation:
\\[
P = P_c + \\frac{{w(0)}}{{T}}
\\]

When T tends to 0, P tends to infinity. Under this assumption, the rider will have an infinite burst of power, which is unreasonable. Therefore, we define the existence of an upper limit of power output for the rider.

Let the upper limit of instantaneous power be \\( P_{{lim}} \\). According to literature, the ability to do work is negatively correlated with anaerobic energy, with P decreasing as anaerobic exercise proceeds. Therefore, the coefficient \\( \\alpha \\) is introduced to describe the relationship between maximum power and anaerobic energy:
\\[
P_{{lim}} = \\alpha w(0) + P_c
\\]

Under this assumption, \\( P_m = \\alpha AWS + P_c \\) is a finite value when T=0, which is in line with the actual situation.

When the rider first enters the working phase, \\( P_{{lim}} > P \\), until it reaches a critical state at \\( t = T \\). When \\( t > T \\), \\( P_{{lim}} < P \\), the power cannot be maintained. Based on this analysis, we can get \\( T \\), let \\( P = P_{{lim}}, t = T \\), \\( w(0) = AWC \\):
\\[
P = \\alpha [AWC - (P - P_c)T] + P_c
\\]

solve for the relation between \\( P \\) and \\( T \\):
\\[
P = \\frac{{\\alpha AWC + \\alpha P_cT + P_c}}{{1 + \\alpha T}}
\\]
```

### **Your Response (JSON Format + Brief Explanation):**
```json
[
  {
    "variable": "Critical Power Threshold (P_c)",
    "reason": "P_c defines the power level a cyclist can sustain indefinitely without tapping into anaerobic reserves. It’s the dividing line between aerobic and anaerobic phases and is necessary for modeling both depletion and recovery of anaerobic energy. Without it, the model cannot determine when energy transitions occur or how long the cyclist can sustain efforts. This value can correspond to physiological lab measurements (like lactate threshold) or be statistically derived from time-trial data. It's used in almost all power-duration models and is a foundational parameter for endurance classification.",
    "real_world_acquisition": "You can acquire P_c in multiple ways: (1) Search for open-access datasets from training platforms (e.g., [Golden Cheetah OpenData](https://github.com/GoldenCheetah/OpenData) or [TrainingPeaks shared workouts]) that include rider power outputs across multiple durations. (2) Use keywords like 'cycling power duration dataset', 'critical power public dataset', 'Golden Cheetah critical power analysis', or 'Strava segment efforts CSV download' in Google or academic search engines. (3) From existing literature: search Google Scholar for 'critical power cycling field test data' or 'cycling power-duration curve validation'. (4) Apply Python-based fitting (e.g., nonlinear least squares with `scipy.optimize.curve_fit`) to estimate P_c from datasets with multiple time-duration trials (e.g., 3, 12, 20 min)."
  },
  {
    "variable": "Anaerobic Work Capacity (AWC)",
    "reason": "AWC quantifies the total amount of anaerobic energy available above the critical power threshold. It represents the 'battery' a rider draws from during short bursts or intense climbs. AWC is essential to simulate how long a cyclist can sustain efforts beyond P_c and how quickly fatigue sets in. Without AWC, the model cannot initialize energy reserves or calculate time to exhaustion during high-intensity intervals. AWC can be obtained directly from lab test outputs, or computed from field data as the area under the curve (above P_c) during all-out efforts.",
    "real_world_acquisition": "To obtain AWC: (1) Search repositories like Zenodo, Figshare, or Harvard Dataverse using terms like 'cycling anaerobic capacity dataset' or 'graded exercise test cycling'. (2) Look for studies with power-duration data and time-to-exhaustion protocols, such as those published in journals like *Journal of Sports Sciences*. Use search terms like 'anaerobic work capacity cycling open dataset' or 'AWC test data cyclist'. (3) Use Python to calculate AWC from public .FIT or .TCX files using libraries like `fitparse` and `pandas`—integrate (Power - P_c) over time until exhaustion. (4) Access shared datasets via sports analytics platforms, e.g., ProCyclingStats or user-uploaded Strava data if properly anonymized."
  },
  {
    "variable": "Maximum Anaerobic Power Coefficient (α)",
    "reason": "α is a scalar that links remaining anaerobic energy (AWC) to the instantaneous peak power a cyclist can produce. It allows the model to define a realistic upper power limit that diminishes with fatigue, avoiding the unrealistic assumption of infinite power bursts. It determines how rapidly fatigue affects performance in sprint and high-intensity efforts. This parameter is critical to defining P_lim and modeling fatigue-dependent power degradation. It may vary by athlete type (sprinter vs endurance rider) and must be empirically estimated using real sprint performance data.",
    "real_world_acquisition": "To acquire α: (1) Search for academic articles that empirically derive or report α values; use terms like 'anaerobic fatigue modeling coefficient', 'cycling fatigue regression model', or 'P_lim fatigue power model coefficient'. (2) Look for datasets involving repeated sprint intervals (e.g., 5–15s efforts) and their corresponding power outputs. These can be found in sports science publications or repositories like ResearchGate or Dryad. (3) Use regression tools in Python (e.g., `scipy.optimize.curve_fit`) to fit model output to recorded peak power values at various depletion states of AWC. (4) Web search using terms like 'cycling sprint power decay dataset', 'maximum power fatigue relationship cycling', or 'cycling fatigue coefficient α data'. (5) If literature or data are unavailable, α can be reverse-engineered by fitting the model equation to known power-duration data where both P_c and AWC are established."
  }
]
```
Once real-world values for `Critical Power (P_c)`, `Anaerobic Work Capacity (AWC)`, and the `Maximum Anaerobic Power Coefficient (α)` are obtained, the model can be implemented by initializing the anaerobic energy reserve and classifying efforts into aerobic and anaerobic phases based on the critical power threshold. During high-intensity efforts where power output exceeds `P_c`, anaerobic energy is depleted at a rate determined by the difference between the current power and `P_c`. Conversely, when the effort drops below `P_c`, the model simulates anaerobic energy recovery.
Using the coefficient `α`, the model dynamically adjusts the rider’s upper power limit to reflect fatigue, ensuring that instantaneous power does not unrealistically spike. With this mechanism in place, the model can predict how long an athlete can maintain a given power level, generate power-duration curves, and simulate realistic fatigue progression. These outputs can then be validated or calibrated using available performance datasets, enabling individualized endurance forecasting or optimization of pacing strategies.
"""


MODELING_FACTOR_USER = """## **Guidelines**
You will be given a full mathematical modeling implementation. Your job is to extract all real-world grounding variables that appear in the implementation. These are the quantities that would need real-world data to make the model work in practice.

For each variable you extract:
- Do not make up new variables. Only to include the initial variables or constraints that need data sources to be implemented. Do not include any derived intermediate variables or results.
- Explain why this variable is important. Your explanation should provide guidance on what kind of data we should find for this variable.
- Suggest how to find its real-world value (code, dataset, search term, etc). Be practical and specific when suggesting data acquisition methods.
Your response should be returned in JSON format: a list of dictionaries.


### **Response Format:**
Your response should include this JSON format and a brief explanation after that:

```json
[
  {{
    "variable": "...",
    "reason": "...",
    "real_world_acquisition": "..."
  }},
  ...
]
```
[A brief explanation of how you would implement the model and achieve the objective step by step.]


### **Modeling Objective and Guidlines:**
{modeling_approach}


### **Modeling Implementation:**
{modeling_implementation}


### **Your Response (JSON Format + Brief Explanation):**
"""