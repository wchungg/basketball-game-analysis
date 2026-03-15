# from fastapi import FastAPI
# import uvicorn
from ultralytics import YOLO 

# app = FastAPI()

model = YOLO("models/player_detector.pt")

results = model.track("video_data/turnover.mp4", save=True)
print(results)
print("================")
for box in results[0].boxes:
    print(box)

# @app.get("/")
# def read_root():
#     return {"message": "FastAPI YOLO backend running"}


# if __name__ == "__main__":
#     uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)