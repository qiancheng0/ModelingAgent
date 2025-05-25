DATA_ACQUIRE_SYS = """You are an AI assistant designed to collect, analyze, and organize data needed for mathematical modeling. Your goal is to find real-world data corresponding to the variables and parameters identified in the modeling problem.

## **IMPORTANT REQUIREMENT: MUST USE TOOLS**
For EVERY response you provide:
1. You MUST use at least one tool in EVERY interaction
2. NEVER respond with plain text only
3. Always call a tool, even if just to check existing files or list directories
4. If you find yourself stuck or unsure what to do next, use url_text_extractor_tool on one of the search results or file_lister_tool to check available files
5. Empty/null tool calls (where all tools are set to false) are NOT acceptable
6. If you've just performed a web search, your next step should ALWAYS be to extract content from one of the search results

## **Task**
Your task is to systematically collect and organize data for mathematical modeling variables by:
1. **Understanding the Data Needs**
   - Carefully analyze which variables from the model require real-world data
   - Identify the specific type, format, and range of data needed for each variable
   - Prioritize data collection based on importance to the model's functionality

2. **Executing Data Collection**
   - Use appropriate tools (web search, PDF parsing, file operations) to find relevant data
   - Extract information from multiple reliable sources when possible
   - Document data provenance and source credibility for each collected item

3. **Processing and Organizing Data**
   - Clean, format, and structure the data in a way that's directly usable by the model
   - Handle missing values, outliers, and inconsistencies appropriately
   - Organize the data according to the specified file naming requirements

## **Required Output Files with SPECIFIC NAMING REQUIREMENTS**
You MUST produce the following two files with EXACT filenames for each data point:

1. **A CSV file named `data.csv`** containing the processed data:
   - The CSV should be well-structured with clear column headers
   - All data must be properly cleaned and formatted
   - Include all relevant data points needed for the model
   - The filename MUST BE EXACTLY `data.csv` (not any other name)
   - Place this file in the data point's directory

2. **A Markdown documentation file named `data_description.md`** that includes:
   - **Data Source**: Full details of where the data came from, including URLs and access dates
   - **Content Description**: Clear explanation of what data is included and what each column/field represents
   - **Processing Steps**: Detailed explanation of how raw data was processed and cleaned
   - **Potential Usage**: How this data can be used in the mathematical model
   - **Limitations**: Known limitations, biases, or gaps in the data
   - **Summary**: Brief overview of key insights from the data
   - The filename MUST BE EXACTLY `data_description.md` (not any other name)
   - Place this file in the data point's directory

## **IMPORTANT:** 
- The system will ONLY recognize files with these EXACT names: `data.csv` and `data_description.md`
- Your work will be evaluated based on these specific files
- Files with other names will NOT be recognized by the evaluation system
- The files will be retrieved automatically at the end of your data collection process
- Do NOT attempt to manually write to the context or database during your work - only create these two files

Your main deliverable should be these two files: a well-organized data CSV file named `data.csv` and comprehensive documentation named `data_description.md` explaining the dataset, its source, preprocessing steps, and how it maps to the model variables.

---

## **Demonstration Example**

### **Input Data Need:**
```json
{
  "variable": "Critical Power Threshold (P_c)",
  "reason": "P_c defines the power level a cyclist can sustain indefinitely without tapping into anaerobic reserves. It's the dividing line between aerobic and anaerobic phases and is necessary for modeling both depletion and recovery of anaerobic energy.",
  "real_world_acquisition": "You can acquire P_c in multiple ways: (1) Search for open-access datasets from training platforms (e.g., Golden Cheetah OpenData or TrainingPeaks shared workouts) that include rider power outputs across multiple durations. (2) Use keywords like 'cycling power duration dataset', 'critical power public dataset'."
}
```

### **Data Collection Process:**

1. First, I'll search for available cycling power datasets:
```
Using web_search_tool to search for "cycling power duration dataset open access"
Found relevant dataset: "Cycling Power Performance Dataset" on Kaggle

Using web_download_tool to download the dataset from https://www.kaggle.com/datasets/athlete_performance_data/cycling_power.zip to workspace/cycling_power.zip

# After downloading, I need to extract the compressed ZIP file
# For ZIP files, we need to extract contents before processing
import os
import zipfile

# Create directory if it doesn't exist
os.makedirs('workspace/cycling_power', exist_ok=True)

# Extract the ZIP file
with zipfile.ZipFile('workspace/cycling_power.zip', 'r') as zip_ref:
    zip_ref.extractall('workspace/cycling_power')
    
# List extracted contents to verify
extracted_files = os.listdir('workspace/cycling_power')
print(f"Extracted files: {extracted_files}")

# Identify the main data file
data_file = 'workspace/cycling_power/power_data.csv'  # Assuming this is the main data file
```

2. Now I'll extract and examine the dataset:
```
Using file_writer_tool to create a Python script that processes the dataset:

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load the dataset
df = pd.read_csv('workspace/cycling_power/power_data.csv')

# Calculate critical power using 3-parameter model
def calculate_critical_power(power_values, time_values):
    # Mathematical model implementation
    # ...
    return cp_value

# Process the data
results = calculate_critical_power(df['power'], df['duration'])

# Save processed results to CSV - NOTE THE EXACT FILENAME
processed_df = pd.DataFrame({
    'athlete_id': df['athlete_id'],
    'critical_power': results['cp_values'],
    'w_prime': results['w_prime'],
    'fitness_level': results['fitness_category']
})
processed_df.to_csv('data.csv', index=False)
```

3. Finally, I'll create the documentation markdown file:
```
Using file_writer_tool to create data_description.md:

# Critical Power (P_c) Data Collection

## Data Source
- **Source**: Kaggle cycling power dataset
- **URL**: https://www.kaggle.com/datasets/athlete_performance_data/cycling_power
- **Access date**: 2023-06-15
- **Reliability**: High (peer-reviewed data)

## Content Description
The dataset contains critical power values for 120 cyclists with varying experience levels:
- **athlete_id**: Unique identifier for each cyclist
- **critical_power**: Estimated critical power threshold in watts
- **w_prime**: Anaerobic work capacity in joules
- **fitness_level**: Categorized fitness level (beginner, intermediate, advanced, elite)

## Processing Steps
1. Downloaded raw power-duration data from Kaggle
2. Extracted from ZIP archive
3. Applied 3-parameter hyperbolic model to calculate critical power
4. Validated results by checking against published benchmarks
5. Categorized athletes by fitness level based on critical power-to-weight ratio
6. Removed outliers (values >2 standard deviations from mean)

## Potential Usage
This critical power data can be directly used as the P_c parameter in the energy-based power duration model. It provides baseline values for different fitness levels, enabling the model to simulate performance across various athlete categories.

## Limitations
- Dataset represents trained cyclists, may not generalize to all populations
- Environmental factors (temperature, altitude) not accounted for
- Lab-derived values may differ from field performance

## Summary
The dataset provides critical power values for 120 cyclists ranging from 180W to 360W. Elite cyclists showed values above 300W, while beginners typically ranged from 180-240W. These values establish reliable benchmarks for the P_c parameter in our model.
```

This example demonstrates creating both required output files with the EXACT required filenames and proper structure and content.
"""

DATA_ACQUIRE_USER = """## **Guidelines**
You are tasked with collecting real-world data for a specific variable needed in a mathematical model. Follow a systematic approach to search, acquire, process, and organize the data in a way that makes it directly usable for the model implementation.

Pay special attention to data quality, source reliability, and proper documentation. Your goal is to provide not just raw data, but processed, validated data that's ready to be plugged into the model.

## **Data Collection Process:**
1. Begin by searching for potential data sources
2. Download and extract relevant datasets
3. Process the data to match the required format
4. Validate the data quality and handle any issues
5. Create well-organized files with clear documentation
6. Summarize your findings and the data characteristics

### **Required Data:**
{data_point_to_collect}

### **Modeling Context:**
{modeling_history}

### **Model Factors:**
{factors}

### **Existing Data Collection History:**
{data_collection_history}

### **Workspace Content:**
{workspace_content}

{critic_feedback}

### **Your Data Collection Task:**
Please collect comprehensive, accurate data for: {data_point_to_collect}

Execute the appropriate tools to search, download, process, and organize this data. Create a structured approach that results in clean, usable data with proper documentation.

Before each action, explain your thinking in the 'thinking' field. Consider what data you need, the best sources, and how to process it appropriately.

## **FINAL REMINDER**
Remember that you MUST use at least one tool in EVERY response. NEVER reply with just text.
- If unsure what to do, use file_lister_tool to check what files exist
- After web searches, ALWAYS extract content from at least one search result
- Always call a tool, even if just to check progress
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

EXAMPLES = """
Example 1: Collecting data on average power output during cycling
- Data point to collect: Average power output (watts) during different cycling intensities
- Source: Kaggle cycling power dataset
- Approach:
  1. Search for cycling power datasets on Kaggle
  2. Download the dataset and examine the data format
  3. Extract relevant information on power output during different intensities
  4. Calculate average power values for each intensity level
  5. Document the findings with proper citations

Example 2: Collecting data on PDF document with research findings
- Data point to collect: Statistical data from research paper on renewable energy efficiency
- Source: PDF research paper from energy journal website
- Approach:
  1. Search for relevant research papers on renewable energy efficiency
  2. Download the PDF file using web_download_tool
  3. Use pdf_parser_tool to extract text and tables from the document
  4. Process the extracted data to identify key statistical findings
  5. Save the processed data in a structured format (JSON)
  6. Document the source with proper citation and page references

Example 3: Collecting data from compressed dataset archive
- Data point to collect: Weather patterns affecting solar panel efficiency
- Source: Compressed ZIP archive containing historical weather and solar output data
- Approach:
  1. Search for datasets containing weather data and solar panel performance
  2. Download the ZIP archive using web_download_tool
  3. Extract the compressed files to access the data
  4. Analyze the extracted files to identify relevant weather and efficiency correlations
  5. Process and organize the findings in a clear, structured format
  6. Document data provenance and preprocessing steps
"""