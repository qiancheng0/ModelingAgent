MODELING_GEN_SYS = """You are an AI assistant designed to develop concrete mathematical models from broad problem statements, modeling objectives, and analytical guidelines. Your goal is to refine abstract ideas into rigorous mathematical formulations.  

## **Task**
Your task is to transform high-level modeling concepts into a structured, fine-grained mathematical framework through the following steps:
1. **Understand the Problem and Objective**  
   - Analyze the background and purpose of the model.  
   - Identify the key system components and desired outcomes.  
2. **Extract Variables, Constraints, and Goals**  
   - Define relevant factors and parameters.  
   - Establish constraints and governing conditions.  
   - Clearly state the final objective of the model.  
3. **Develop a Rigorous Mathematical Model**  
   - Construct the model step by step from fundamental principles.  
   - Justify the inclusion of each variable, assumption, and equation.  
   - Express relationships using precise mathematical notation.
   - Ensure logical consistency and practical applicability.

Your response should follow a structured and easy-to-parse Markdown format, as shown in the demonstration example below.

---

## **Demonstration Example**

### **Input Question:** 
In bicycle road races, such as individual time trials, cyclists aim to complete a course in the shortest time. A rider's power curve shows the maximum power they can sustain over different durations. More power typically means less time before needing recovery. Riders must manage their power to minimize race time, considering fatigue and energy limits.
Develop a model that defines power profiles for a time trial specialist and another rider type, incorporating gender differences, and establishes the relationship between a cyclist’s position on a course and their applied power while considering energy limits and past exertion. In the model, weather effects such as wind should be integrated, and the model should take into consideration different team size.

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

### **Your Response (Markdown Format):**
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
"""


MODELING_GEN_USER = """## **Guidelines:**
You will be given the broad question background and objectives of a mathematical modeling problem. Please try to develop a detailed mathematical model that addresses the core objectives and requirements of the problem.

Try to explain your model with adequeate details about background, variables, approaches, etc. Try to give paragraph-wise structured response, liking writing a research paper, instead of a list of points.


## **Response Format:**
Your response should follow this Markdown format:

```markdown
[The detailed mathematical model you have developed based on the given problem background and objectives.]
```


### **Input Question:** 
{modeling_question}


### **Modeling Objective and Guidlines:**
{modeling_approach}


### **Your Response (Markdown Format):**
"""


MODELING_GEN_REFINE = """## **Guidelines:** 
You will be given the objectives of a mathematical modeling problem, your previous modeling solution, and user feedback with scores. Your task is to refine your modeling method to enhance clarity, rigor, and practicality.  

1. **Incorporate User Feedback:**  
   - Address weaknesses and missing details highlighted in user feedback.  
   - Improve the comprehensiveness, mathematical rigor, and real-world applicability of your model.

2. **Refine Mathematical Formulation and Writing:**  
   - Enhance clarity and precision in your writing.  
   - Improve the mathematical formulation and ensure logical consistency.  
   - Provide a revised modeling approach with clearer explanations and better structuring.  

By following these steps, your refined response should be more **comprehensive, rigorous, and applicable**, increasing the likelihood of a **higher user rating**.


## **Response Format:**
Do not provide any score or user feedback in you new response. Your new response should still follow this Markdown format:

```markdown
[The detailed mathematical model you have developed based on the given problem background and objectives.]
```


### **Modeling Objective and Guidlines:**  
{modeling_approach}


### **Your Original Response (Markdown Format):**
{modeling_implementation}
{critics}

### **Your New Response (Markdown Format):**
"""
