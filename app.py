from flask import Flask, request, render_template, url_for
import pandas as pd
import google.generativeai as genai
import io
import re
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO

app = Flask(__name__)

# Gemini setup
genai.configure(api_key="your-api-key")
model = genai.GenerativeModel("gemini-1.5-flash")

global_excel_data = {}

def extract_code(text):
    match = re.search(r"```python(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

def sheets_code_hint():
    return """
The sheets dictionary is like:
{
  'BROKER AUM': pd.DataFrame(...),
  'SCHEME_DIM': pd.DataFrame(...),
  ...
}
Use 'sheets' variable to access data.
Store your final output in a variable called `result`.
If you create a chart, store the plot in a variable called `fig` using matplotlib.
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    global global_excel_data
    result_html = ""
    query = ""
    code = ""

    uploaded_filename = ""

    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file:
                uploaded_filename = file.filename  # ✅ Save filename
                global_excel_data = pd.read_excel(file, sheet_name=None)
                result_html += "<p style='color:green;'>✅ Excel file uploaded successfully.</p>"

        elif 'query' in request.form:
            query = request.form['query']
            if not global_excel_data:
                result_html += "<p style='color:red;'>❌ Upload Excel file first.</p>"
            else:
                sheet_summaries = []
                for name, df in global_excel_data.items():
                    schema = [f"{col}: {df[col].dtype}" for col in df.columns]
                    sheet_summaries.append(f"Sheet: {name}\n" + "\n".join(schema))

                prompt = f"""
                    You are a Python data analyst.

                    {sheets_code_hint()}

                    Sheets available:
                    {chr(10).join(sheet_summaries)}

                    User Query:
                    {query}

                    Write a single Python code block using only Pandas and matplotlib (only if visualization is required) to answer the user query using the `sheets` dictionary.

                    Do not use any other libraries like numpy, scipy, seaborn, or plotly.

                    Only create a matplotlib chart and store it in a variable named `fig` if the user explicitly asks for a plot, chart, graph, or visualization. Otherwise, do not create any plots.

                    Store the final result in a variable named `result`. Do not include explanations. Only return executable code.


                    """
                try:
                    response = model.generate_content(prompt)
                    code = extract_code(response.text)

                    sheets = global_excel_data
                    local_vars = {"sheets": sheets}
                    exec(code, {"pd": pd, "plt": plt, "sns": sns}, local_vars)

                    result = local_vars.get("result")
                    fig = local_vars.get("fig")

                    if isinstance(result, pd.DataFrame):
                        result_html += result.to_html(index=False)
                    elif result is not None:
                        result_html += f"<pre>{result}</pre>"

                    chart_keywords = ["plot", "chart", "graph", "visualize"]
                    wants_chart = any(word in query.lower() for word in chart_keywords)

                    if fig and wants_chart:
                        buf = BytesIO()
                        fig.savefig(buf, format="png")
                        buf.seek(0)
                        image_base64 = base64.b64encode(buf.read()).decode("utf-8")
                        result_html += f'<h3>Chart:</h3><img src="data:image/png;base64,{image_base64}"/>'
                        plt.close(fig)
                    elif fig and not wants_chart:
                        plt.close(fig)

                except Exception as e:
                    result_html += f"<p style='color:red;'>❌ Error running Gemini code: {e}</p>"

    return render_template("index.html", query=query, result_html=result_html, code=code, uploaded_filename=uploaded_filename)


if __name__ == '__main__':
    app.run(debug=True)
