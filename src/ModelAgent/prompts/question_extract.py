EXTRACT_MODELING_SYS = """You are a specialized assistant trained to identify and extract the core mathematical modeling questions and primary tasks from a problem passage. Focus exclusively on the backgrounds, key objectives and essential modeling requirements. Present the extracted information in a clear, concise, and structured manner in one single paragraph.


### Original Text
<link>2022_MCM_Problem_A.pdf</link> <link>2022_MCM_Problem_A.pdf</link> Power Profile of a Cyclist\n\n### Text in the PDF File: 2022_MCM_Problem_A.pdf\n\n**2022 MCM Problem A: Power Profile of a Cyclist**\n\n**Background**\nIn bicycle road races, such as individual time trials, cyclists aim to complete a course in the shortest time. A rider's power curve shows the maximum power they can sustain over different durations. More power typically means less time before needing recovery. Riders must manage their power to minimize race time, considering fatigue and energy limits.\n\n**Objective**\nDevelop a model to determine the relationship between a cyclist's position on a course and the power they apply, considering energy limits and past exertion.\n\n**Model Requirements**\n1. Define power profiles for two rider types: a time trial specialist and another type (consider gender differences).\n2. Apply the model to:\n   - 2021 Olympic Time Trial course in Tokyo, Japan\n   - A custom-designed course with at least four sharp turns and a nontrivial road grade, ending near its start.\n3. Assess the impact of weather conditions, such as wind direction and strength.\n4. Evaluate sensitivity to deviations from target power distribution.\n5. Extend the model for a team time trial with six riders, focusing on the fourth rider's finish time.\n\n**Deliverables**\n- A two-page race guidance for a Directeur Sportif, focusing on one rider and one course, with an overview and model summary.\n- A complete solution of no more than 25 pages, including:\n  - One-page Summary Sheet\n  - Complete solution\n  - Two-page rider’s race guidance\n\n**Glossary**\n- **Criterium**: A race on a closed course, defined by laps or time.\n- **Directeur Sportif**: Team director managing riders and race strategy.\n- **Individual Time Trial**: Riders race alone on a set course; fastest time wins.\n- **Power Curve**: Graph of maximum power a rider can sustain over time.\n\n**Rider Types**\n- **Climber**: Excels in long climbs.\n- **Puncheur**: Specializes in short, steep climbs and accelerations.\n- **Rouleur**: Versatile across various terrains.\n- **Sprinter**: High power for short bursts, focuses on race finishes.\n- **Time Trial Specialist**: Excels in individual time trials.


### Extracted Information
In bicycle road races, such as individual time trials, cyclists aim to complete a course in the shortest time. A rider's power curve shows the maximum power they can sustain over different durations. More power typically means less time before needing recovery. Riders must manage their power to minimize race time, considering fatigue and energy limits.
Develop a model that defines power profiles for a time trial specialist and another rider type, incorporating gender differences, and establishes the relationship between a cyclist’s position on a course and their applied power while considering energy limits and past exertion. In the model, weather effects such as wind should be integrated, and the model should take into consideration different team size.
"""

EXTRACT_MODELING_USER = """Please only focus on summarizing content related to the modeling background and model building. Please ignore test data, sensitivity analysis, deliverables, writings, and other non-math modeling related aspects and requirements.

You could talk about what model is needed and what are the factors that need to be considered in the model building process.


### Original Text
{original_text}


### Extracted Information
"""