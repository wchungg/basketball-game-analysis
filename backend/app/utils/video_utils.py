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
    os.makedirs(os.path.dirname(output_vid_path), exist_ok=True)

    if not output_vid_frames:
        raise ValueError("Cannot save a video with no frames.")

    frame_size = (output_vid_frames[0].shape[1], output_vid_frames[0].shape[0])
    file_extension = os.path.splitext(output_vid_path)[1].lower()

    codec_candidates = ["mp4v"] if file_extension == ".mp4" else ["XVID"]
    out = None

    for codec in codec_candidates:
        fourcc = cv2.VideoWriter_fourcc(*codec)
        candidate = cv2.VideoWriter(output_vid_path, fourcc, 24.0, frame_size)
        if candidate.isOpened():
            out = candidate
            break
        candidate.release()

    if out is None:
        raise ValueError(f"Could not create video writer for {output_vid_path}.")

    for frame in output_vid_frames:
        out.write(frame)

    out.release()
