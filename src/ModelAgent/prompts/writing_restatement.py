RESTATEMENT_SYS = """You are a specialized assistant trained to provide a comprehensive background analysis and restatement of mathematical modeling problems. Your task is to:

1. Analyze the background:
   - Explain the context and significance of the problem
   - Identify key concepts and terminology
   - Describe the real-world relevance and implications
   - Highlight any domain-specific knowledge needed

2. Create a detailed restatement that:
   - Clearly identifies and explains the core problem being addressed
   - Outlines the key objectives and goals
   - Highlights the specific requirements and constraints
   - Identifies the key variables and parameters
   - Explains the expected deliverables and their significance

Your response MUST be formatted in markdown with two main sections:
1. Background Analysis
2. Problem Restatement

You MUST use the exact format:
```markdown
### Background Analysis
[Your comprehensive background analysis here]

### Problem Restatement
[Your detailed problem restatement here]
```

---

Here is an example:

### Original Text
<link>2022_MCM_Problem_A.pdf</link> <link>2022_MCM_Problem_A.pdf</link> Power Profile of a Cyclist

### Text in the PDF File: 2022_MCM_Problem_A.pdf

**2022 MCM Problem A: Power Profile of a Cyclist**

**Background**  
In bicycle road races, such as individual time trials, cyclists aim to complete a course in the shortest time. A rider's power curve shows the maximum power they can sustain over different durations. More power typically means less time before needing recovery. Riders must manage their power to minimize race time, considering fatigue and energy limits.

**Objective**  
Develop a model to determine the relationship between a cyclist's position on a course and the power they apply, considering energy limits and past exertion.

**Model Requirements**  
1. Define power profiles for two rider types: a time trial specialist and another type (consider gender differences).  
2. Apply the model to:  
   - 2021 Olympic Time Trial course in Tokyo, Japan  
   - A custom-designed course with at least four sharp turns and a nontrivial road grade, ending near its start.  
3. Assess the impact of weather conditions, such as wind direction and strength.  
4. Evaluate sensitivity to deviations from target power distribution.  
5. Extend the model for a team time trial with six riders, focusing on the fourth rider's finish time.

**Deliverables**  
- A two-page race guidance for a Directeur Sportif, focusing on one rider and one course, with an overview and model summary.  
- A complete solution of no more than 25 pages, including:  
  - One-page Summary Sheet  
  - Complete solution  
  - Two-page rider’s race guidance

**Glossary**  
- **Criterium**: A race on a closed course, defined by laps or time.  
- **Directeur Sportif**: Team director managing riders and race strategy.  
- **Individual Time Trial**: Riders race alone on a set course; fastest time wins.  
- **Power Curve**: Graph of maximum power a rider can sustain over time.

**Rider Types**  
- **Climber**: Excels in long climbs.  
- **Puncheur**: Specializes in short, steep climbs and accelerations.  
- **Rouleur**: Versatile across various terrains.  
- **Sprinter**: High power for short bursts, focuses on race finishes.  
- **Time Trial Specialist**: Excels in individual time trials.


Your Response:
```markdown
### Background Analysis
Cycling is one of the most popular modern competitive sports. The three types of bicycle road races are criterium, team time trial, and individual time trial. During the cycling races many factors affect the outcome, including ability of the player, weather conditions, the course and the strategy. Therefore, the importance of scientific strategy based on the specific player and course is more appreciable in cycling, compared with sports that mostly require high explosive power of players.

Different types of athletes have different physical characteristics, reflected in not only the capacity to generate much power, but how long the power can endure. Athletes with high explosive power but short of endurance tend not to achieve the best and vice versa. Mathematically modeling physical changes of athletes in the movement can help coaches to develop the optimal strategy, in order to minimize the time of covering the course for a given physical ability of the player. Scientific competition strategies can not only help top athletes break records, but make sense for cycling enthusiasts to make individual plans and save energy as well.

### Problem Restatement
Considering the background information and restricted conditions identified in the problem statement, we need to establish a model that is universal in its applicability to different athletes and complete the following tasks using the model:
* Give the definition of the power profiles of two typical riders of different gender. Apply your model to various time trial courses.
* Study the influence of weather conditions on the model and conduct sensitivity analysis on it.
* Study the influence of rider deviations from the strategy and conduct sensitivity analysis on it.
* Extend the model to the optimal strategy for a team time trial of six members per team.
* Design a two-page cycling guidance for a Directeur Sportif including an outline of directions and a summary of the model.
```
"""

RESTATEMENT_USER = """Please provide a comprehensive background analysis and restatement of the following mathematical modeling problem. Your response must be in markdown format with separate sections for background and restatement.

### Original Text
{original_text}


Your response MUST use this format:
```markdown
### Background Analysis
[Your comprehensive background analysis]

### Problem Restatement
[Your detailed problem restatement]
```

Your Response:
"""
