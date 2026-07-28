$env:PYTHONPATH = "$PSScriptRoot\.python-packages;$PSScriptRoot"
& "C:\Program Files\Microsoft SDKs\Azure\CLI2\python.exe" -m uvicorn app.main:app --reload --port 8000
