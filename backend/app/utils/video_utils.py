import cv2
import os

def read_video(vid_path):
    cap = cv2.VideoCapture(vid_path)
    frames=[]

    while True:
        ret, frame = cap.read()

        if not ret:
            break
        frames.append(frame)

    return frames

def save_video(output_vid_frames, output_vid_path):
    if not os.path.exists(os.path.dirname(output_vid_path)):
        os.mkdir(os.path.dirname(output_vid_path))

    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    out = cv2.VideoWriter(output_vid_path, fourcc, 24.0, (output_vid_frames[0].shape[1], output_vid_frames[0].shape[0]))

    for frame in output_vid_frames:
        out.write(frame)

    out.release()


