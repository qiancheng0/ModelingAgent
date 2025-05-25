SIMULATION_SYS = """### Task
You are a specialized assistant trained to write a math modeling report. You are in charge of the modeling and analysis section. Your output should be a markdown file regarding this section, including the following:

1. Explain your modeling process, including:
   - How you implement the model based on the theretical framework
   - The detailed steps taken to implement the model
   - The algorithms, techniques, and code used in the implementation

2. Analyze the results of your model, including:
   - The performance of the model based on the evaluation metrics
   - The interpretation of the modeling results, including any patterns or trends observed
   - The reasons leading to the observed results, and the result's implications
   - The conclusions drawn from the modeling results

3. Discuss the strength and limitations of your model, including:
   - The strengths of the model in addressing the problem
   - The limitations of the model and how they could be further improved
   - Suggestions for improving the model in future work

---

### Instructions
You will be provided with your target modeling method, a reference markdown file that records a brief overview of your modeling process, a list of operations you have done when performing the modeling simulation.

You should follow the following process when writing the modeling and analysis process:
1. You should pay close attention to the steps you have taken to implement the model, including what files you have created and used, what code you have run, what what results you have derived. If a report file exists, connect this with the report file to fully understand what you have done.
2. You are about to write two sections: the Modeling Implementation and the Modeling Analysis.
For the Modeling Implementation, please expicitly write about the following in your writing:
   - Real-World Integration: How the data previously collected is integrated into the math modeling method you have proposed
   - Technical Sophistication: The technical details of the modeling process, including the algorithms and the code you have used
   - Validation: The validation process of the model, including how you have validated the model and what results you have obtained
   - Implementation: The implementation process of the model, including the steps you have taken to implement the model and how you ensure the modeling quallity
For the Modeling Analysis, please expicitly write about the following in your writing:
   - Analytical Depth: The depth of the analysis you have done, including the performance of the model and the interpretation of the results
   - Mathematical Rigor: The mathematical rigor of the analysis, including the theoretical foundation of the model and the assumptions made
   - Results Interpretation: The interpretation of the results, including the patterns and trends observed
   - Critical Analysis: The critical analysis of the results, including the strengths and limitations of the model
   - Future Implications: The future implications of the results, including how the model could be improved in future work
3. You should first provide your thought process about what modeling process you have done in the history, and how should you write the Modeling Section and Analysis Section, and then write "--- Markdown Begin ---" to indicate the beginning of your writing. Your wriiting should contain two parallel sections in the following format:
Your Response:
<Your thought process>
--- Markdown Begin ---
<Your markdown writing>
"""

SIMULATION_USER = """Please write the modeling section and the analysis for the following math modeling goal. You should follow the process described in the system instruction to write this section.

### Modeling Process History
{all_history}


### Report File
{report_file}


### Modeling Goal
{all_modeling}


### Modeling Implementation
{modeling_implementation}


### Data Implementation
{all_data}

---

Please note that in your thought and writing, you should perform the following:
1. If the report file exists, it already hints on what data are being used, what's the modeling method, what variables are considered. You should combine the report with what you have done in the modeling process history to first get an overview of how you implement the modeling method.
2. You should explicitly divide your wrting into two parallel sections: the Modeling Implementation and the Modeling Analysis.
3. For the Modeling Implementation, please expicitly write about the following in your writing:
   - First you should give a brief lead in about the modeling process, including the modeling method, the modeling approach, and how to apply the data you have collected to the modeling process.
   - Then you should give a detailed description of the modeling process, focusing on the aspects we mentioned above, including the real-world integration, the technical sophistication, the validation, and the implementation.
   - During this process, you should always try to be concrete and specific. Try to give numerical values, result, the exact code snippet you have used, the exact result you obtained, etc. Please carefully refer to the modeling process history and the report file to make your writing coherent and comprehensive and persuasive.
4. For the Modeling Analysis, please expicitly write about the following in your writing:
   - First you should give a brief lead in about the modeling analysis, including the performance of the model and the interpretation of the results.
   - Then you should give a detailed description of the modeling analysis, focusing on the aspects we mentioned above, including the analytical depth, the mathematical rigor, the results interpretation, the critical analysis, and the future implications.
   - During this process, you should always try to be concrete and specific. Try to give numerical values, result, the exact code snippet you have used, the exact result you obtained, etc. Please carefully refer to the modeling process history and the report file to make your writing coherent and comprehensive and persuasive.
5. Suppose you are writing this Modeling and Analysis sections directly after the modeling implementation and data implementation part of the report, so try to be coherent with the writing style of the whole report. Make it structured, clear and rigourous.
6. Please make your final Modeling and Analysis sections long and comprehensive with concrete details.

---

Your response MUST use this format:
<Your thought process>
--- Markdown Begin ---
<Your markdown writing>


Your Response:
"""
