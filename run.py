import uvicorn

if __name__ == "__main__":
    print("\n  YT Studio running at http://127.0.0.1:8000\n")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)
