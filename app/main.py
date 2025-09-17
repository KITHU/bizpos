from fastapi import FastAPI

app = FastAPI(
    title="BizPos API",
    description="Welcome to BizPos. A modern POS and Inventory Management System",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"message": "👋 Welcome to BizPos APIs!"}
