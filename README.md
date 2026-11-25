# CPU Scheduling Visualizer and Performance Analyzer

A Streamlit simulator for FCFS, non-preemptive SJF, SRTF, both priority variants, and Round Robin. Edit the workload, generate a random case, or load the included CSV. The dashboard shows the CPU timeline and context switches, compares performance on the same input, and exports timestamped CSV results.

## Run on Windows

Open PowerShell in the project folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://localhost:8501 while Streamlit is running.

## Deploy from GitHub

Upload the contents of this folder to the root of a GitHub repository. In Streamlit Community Cloud, create an app, select the repository and branch, and enter `app.py` as the entry point. Share the resulting app URL with your evaluator and verify that they can access it. GitHub Pages serves static files and cannot run the Streamlit server.

## Simulation conventions

The simulation starts at time zero. Equal arrivals follow input order. A tie in preemptive rank leaves the current job running. At an RR boundary, arrivals are queued before the expired job is requeued. Context switches count direct handoffs between different jobs and consume zero simulated time. Utilization and throughput use the time from zero through final completion.
