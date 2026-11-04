# Phase 2 install
1. Copy backend/app/services/*, backend/app/routers/inspect.py, backend/scripts/test_muse.py, backend/tests/test_inspector.py into your project (same paths).
2. requirements.txt: add  httpx, pillow, python-multipart
3. app/main.py: 
     from app.routers import inspect
     app.include_router(inspect.router)
4. Optional .env: SAM_ENABLED=false (default; SAM client is not implemented yet)
5. cd backend && python scripts/test_muse.py [photo.jpg]
6. pytest
