DATA_SYS = """### Task
You are a specialized assistant trained to write a math modeling report. You are in charge of the data section. Your output should be a markdown file regarding this section, including the following:

1. Explain how the data was collected, including:
   - The methods and tools used for data collection
   - The sources of data (e.g., databases, APIs, surveys)
   - The criteria for selecting data sources
   - The process of data validation and cleaning
   - Any challenges faced during data collection and how they were addressed

2. Provide a summary of the data collected, including:
   - The types of data collected (e.g., numerical, categorical, time series)
   - The volume of data collected (e.g., number of records, size of datasets)
   - The structure of the data (e.g., tables, files, formats)

3. Discuss the relevance and significance of the data to the problem being addressed, including:
   - How the data supports the objectives of the modeling problem
   - The potential impact of the data on the modeling outcomes

---

### Instructions
You will be provided with your target modeling method, a reference markdown file that records what data are used and the modeling process. a list of raw data files (all of them), their descriptions, and their content.

You should follow the following process when writing the data collection process:
1. Not all the data files are related to the current modeling problem. Please first select the data files that are relevant to the modeling problem, and then begin to write about this data.
2. For each relevant data, please explicitly write about the following in your writing:
    - The quality of the data
    - The statistical analysis of the data
    - The validation of the data
    - How the data should be processed to be used in the modeling process
    - How should the data be integrated in future modeling processs
3. You should first provide your thought process about what data are relevant to the current modeling problem, and then write "--- Markdown Begin ---" to indicate the beginning of your writing, in the following format:
Your Response:
<Your thought process>
--- Markdown Begin ---
<Your markdown writing>
"""

DATA_USER = """Please write the data section for the following math modeling goal. You should follow the process described in the system instruction to write this section.


### Data Collection History
{all_history}


### Data Files
{all_data}


### Report File
{report_file}


### Modeling Goal
{all_modeling}


### Modeling Implementation
{modeling_implementation}


---

Please note that in your thought and writing, you should perform the following:
1. If the report file exists, it already hints on what data are being used, correspnding to what variable in the modeling process. Please only pay attention to the data that is related to the current modeling process.
2. For each data that is related, write a subsection for it, including the following:
   - First give an introduction about this data, including what this data is, how it is related to the modeling process, what it represents, the source and way to find it, etc.
   - The state the details about the data from the five aspects we mentioned above, including: the quality of the data, the statistical analysis of the data, the validation of the data, how the data should be processed to be used in the modeling process, and how should the data be integrated in future modeling processs. Each point should be a subsubsection and be clear about it.
   - Please give a summary table about the structure and concrete content of data, show some examples of data including the number, and give a brief description of the data.
   - Finally, please give a conclusion about the data, including its value, how it could be used in the following modeling process.
3. Suppose you are writing this Data Section directly after the modeling implementation part of the report, so try  to be coherent with the writing style of the report. Make it structured, clear and rigourous.
4. Remember to use one subsection per relevant data. Make your final Data Section long and comprehensive with concrete details.

---

Your response MUST use this format:
<Your thought process>
--- Markdown Begin ---
<Your markdown writing>


Your Response:
"""
