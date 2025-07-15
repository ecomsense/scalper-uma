@echo on
cmd /k "cd /d ..\..\Scripts & .\activate & cd /d .\..\scalper-uma & uvicorn src.main:app --host 0.0.0.0 --port 8000"
